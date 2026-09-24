"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request, Response
from pydantic import BaseModel

router = APIRouter()

from core import (
    sdb, supabase_admin, supabase_user, logger, now_iso,
    generate_password, generate_slug, enrich_member, get_auth_users_map,
    get_plan_limits, parse_presentations,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
)

# ============== AUTH ROUTES ==============

from server import limiter


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(payload: LoginRequest, request: Request, response: Response):
    from services.audit import log_audit
    from services.db_rate_limit import check_rate_limit, rate_limit_key
    from core import ACCESS_TOKEN_COOKIE

    # DB-backed rate limit by IP+email (multi-pod safe). slowapi @limiter is
    # already in memory (single-pod fast rejection). This second layer catches
    # attackers who bypass memory limits by hitting a different pod.
    try:
        await check_rate_limit(
            rate_limit_key(request, "login", extra=payload.email.lower()),
            limit=10, window_sec=300,  # 10 attempts / 5min / (ip+email)
        )
    except HTTPException:
        await log_audit(action="login_rate_limited", entity="auth", actor_email=payload.email, request=request)
        raise
    try:
        sb_response = supabase_user.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        if not sb_response.session:
            await log_audit(
                action="login_failed",
                entity="auth",
                actor_email=payload.email,
                meta={"reason": "no_session"},
                request=request,
            )
            raise HTTPException(status_code=401, detail="Credenciales invalidas")

        user_id = sb_response.user.id
        access_token = sb_response.session.access_token
        refresh_token = sb_response.session.refresh_token
        # Read the "must change password" flag from user_metadata (set by
        # admin invite/reset). Sent to the frontend so it can gate routes.
        from core import user_needs_password_reset
        pw_reset = user_needs_password_reset(sb_response.user)

        # Fix #5: also set the access token as an httpOnly Secure SameSite=Strict
        # cookie. The frontend still uses the Authorization header today (no
        # breaking change), but the cookie is a parallel safety net: if XSS
        # ever steals localStorage, the cookie remains unreadable to JS.
        # SameSite=Strict provides inherent CSRF protection.
        response.set_cookie(
            key=ACCESS_TOKEN_COOKIE,
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=3600,  # 1h, matches Supabase access token lifetime
            path="/",
        )

        # Check user type in Supabase tables
        sa = sdb.table('super_admins').select('id').eq('user_id', user_id).execute()
        if sa.data:
            await log_audit(
                action="login_success",
                entity="auth",
                actor_user_id=user_id,
                actor_email=payload.email,
                actor_role="super_admin",
                request=request,
            )
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                user_type="super_admin",
                user_id=user_id,
                email=payload.email,
                password_needs_reset=pw_reset,
            )

        cm = sdb.table('clinic_members').select('clinic_id,role').eq('user_id', user_id).eq('is_active', True).execute()
        if cm.data:
            await log_audit(
                action="login_success",
                entity="auth",
                actor_user_id=user_id,
                actor_email=payload.email,
                actor_role=cm.data[0].get('role'),
                clinic_id=cm.data[0].get('clinic_id'),
                request=request,
            )
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                user_type="clinic_member",
                user_id=user_id,
                email=payload.email,
                clinic_id=cm.data[0].get("clinic_id"),
                password_needs_reset=pw_reset,
            )

        # No role — clear the cookie we just set
        response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
        await log_audit(
            action="login_denied",
            entity="auth",
            actor_user_id=user_id,
            actor_email=payload.email,
            meta={"reason": "no_role"},
            request=request,
        )
        raise HTTPException(status_code=403, detail="No tienes acceso al sistema")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        await log_audit(
            action="login_failed",
            entity="auth",
            actor_email=payload.email,
            meta={"error": str(e)[:200]},
            request=request,
        )
        raise HTTPException(status_code=401, detail="Error de autenticacion")


@router.post("/auth/logout")
async def logout(response: Response):
    """Clear the auth cookie + Supabase session.

    Frontend should ALSO drop its localStorage token. The cookie deletion
    here handles Fix #5; the supabase_user.auth.sign_out() invalidates the
    refresh token server-side.
    """
    from core import ACCESS_TOKEN_COOKIE
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    try:
        supabase_user.auth.sign_out()
    except Exception:
        pass
    return {"ok": True, "message": "Sesion cerrada correctamente"}

@router.get("/auth/me")
async def auth_me(user=Depends(get_current_user)):
    """Return identity + role payload for the authenticated user."""
    from core import user_needs_password_reset
    pw_reset = user_needs_password_reset(user)
    sa = sdb.table('super_admins').select('id,first_name,last_name,email').eq('user_id', user.id).maybe_single().execute()
    sa_data = getattr(sa, 'data', None) if sa else None
    if sa_data:
        return {
            "user_id": user.id,
            "email": user.email,
            "user_type": "super_admin",
            "name": f"{sa_data.get('first_name','')} {sa_data.get('last_name','')}".strip(),
            "clinic_id": None,
            "role": "super_admin",
            "password_needs_reset": pw_reset,
        }
    cm = sdb.table('clinic_members').select('id,clinic_id,role,first_name,last_name,specialty').eq('user_id', user.id).eq('is_active', True).maybe_single().execute()
    cm_data = getattr(cm, 'data', None) if cm else None
    if cm_data:
        return {
            "user_id": user.id,
            "email": user.email,
            "user_type": "clinic_member",
            "name": f"{cm_data.get('first_name','')} {cm_data.get('last_name','')}".strip(),
            "clinic_id": cm_data.get('clinic_id'),
            "member_id": cm_data.get('id'),
            "role": cm_data.get('role'),
            "specialty": cm_data.get('specialty'),
            "password_needs_reset": pw_reset,
        }
    raise HTTPException(status_code=403, detail="Usuario sin acceso")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
@limiter.limit("10/minute")
async def change_password(payload: ChangePasswordRequest, request: Request, user=Depends(get_current_user)):
    """Self-service password change. Verifies current password, applies policy,
    clears the `password_needs_reset` flag on success.
    """
    from services.password_policy import validate_password
    from services.audit import log_audit
    from core import supabase_user, mark_password_needs_reset

    # 1) Verify current password by attempting sign-in — cheapest path with
    # correct rate-limit awareness. supabase_user.auth.sign_in returns 400
    # if wrong; we don't persist that session.
    try:
        verify = supabase_user.auth.sign_in_with_password({
            "email": user.email,
            "password": payload.current_password,
        })
        if not verify or not verify.session:
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta a la actual")

    # 2) Enforce the policy on the new password
    # Fetch display name for personal-token check
    display_name = None
    try:
        cm = sdb.table('clinic_members').select('first_name,last_name').eq('user_id', user.id).maybe_single().execute()
        cm_data = getattr(cm, 'data', None) if cm else None
        if cm_data:
            display_name = f"{cm_data.get('first_name','')} {cm_data.get('last_name','')}".strip()
        else:
            sa = sdb.table('super_admins').select('first_name,last_name').eq('user_id', user.id).maybe_single().execute()
            sa_data = getattr(sa, 'data', None) if sa else None
            if sa_data:
                display_name = f"{sa_data.get('first_name','')} {sa_data.get('last_name','')}".strip()
    except Exception:
        pass
    validate_password(payload.new_password, email=user.email, name=display_name)

    # 3) Persist the change via admin API and clear the reset flag
    try:
        supabase_admin.auth.admin.update_user_by_id(user.id, {"password": payload.new_password})
        mark_password_needs_reset(user.id, needs=False)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"change_password persist error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar contraseña")

    try:
        await log_audit(
            action="password_self_changed",
            entity="auth",
            actor_user_id=user.id,
            actor_email=user.email,
            request=request,
        )
    except Exception:
        pass

    return {"ok": True, "message": "Contraseña actualizada correctamente"}


# ============== FORGOT / RESET PASSWORD (public, token-based) ==============

def _resolve_user_for_reset(email: str) -> dict | None:
    """Return {user_id, email, name} if the email belongs to a super admin or an
    ACTIVE clinic member; else None. Clinic member emails live in Supabase Auth."""
    email_l = (email or "").strip().lower()
    if not email_l:
        return None
    try:
        sa = sdb.table('super_admins').select('user_id,first_name,last_name,email').ilike('email', email_l).execute()
        if sa.data:
            r = sa.data[0]
            return {"user_id": r["user_id"], "email": r.get("email") or email_l,
                    "name": f"{r.get('first_name','')} {r.get('last_name','')}".strip() or "Administrador"}
    except Exception as e:
        logger.warning(f"forgot: super_admin lookup failed: {e}")
    try:
        users = supabase_admin.auth.admin.list_users()
        match = next((u for u in users if (getattr(u, 'email', '') or '').lower() == email_l), None)
    except Exception as e:
        logger.warning(f"forgot: auth list_users failed: {e}")
        match = None
    if match:
        try:
            cm = sdb.table('clinic_members').select('first_name,last_name').eq('user_id', match.id).eq('is_active', True).maybe_single().execute()
            d = getattr(cm, 'data', None)
            if d:
                return {"user_id": match.id, "email": match.email,
                        "name": f"{d.get('first_name','')} {d.get('last_name','')}".strip() or "Usuario"}
        except Exception as e:
            logger.warning(f"forgot: clinic_member lookup failed: {e}")
    return None


class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/auth/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Send a secure reset link if the email belongs to a known active user.
    If unknown, returns 404 with a clear message (product decision)."""
    import os
    from services.audit import log_audit
    from services.db_rate_limit import check_rate_limit, rate_limit_key
    from services.password_tokens import create_reset_token
    from services.email_service import send_email
    from services.email_templates import password_reset_link

    await check_rate_limit(
        rate_limit_key(request, "forgot", extra=(payload.email or '').lower()),
        limit=5, window_sec=900,
    )

    info = _resolve_user_for_reset(payload.email)
    if not info:
        await log_audit(action="password_forgot_unknown", entity="auth", actor_email=payload.email, request=request)
        raise HTTPException(status_code=404, detail="Este correo no está registrado. Hable con su administrador.")

    raw = create_reset_token(info["user_id"], info["email"], purpose="reset", ttl_minutes=60)
    reset_url = f"{os.environ.get('FRONTEND_URL', '')}/restablecer-password?token={raw}"
    tpl = password_reset_link(user_name=info["name"], reset_url=reset_url, minutes=60)
    try:
        await send_email(to=info["email"], subject=tpl["subject"], html=tpl["html"], text=tpl["text"])
    except Exception as e:
        logger.warning(f"forgot: email send failed: {e}")
    await log_audit(action="password_forgot_requested", entity="auth",
                    actor_user_id=info["user_id"], actor_email=info["email"], request=request)
    return {"ok": True, "message": "Te enviamos un correo con instrucciones para restablecer tu contraseña."}


@router.get("/auth/reset-token/validate")
async def validate_reset_token(token: str):
    """Check a reset/welcome token without consuming it (for the reset page)."""
    from services.password_tokens import peek_token
    r = peek_token(token)
    if not r:
        return {"valid": False}
    return {"valid": True, "email": r.get("email"), "purpose": r.get("purpose")}


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/auth/reset-password")
@limiter.limit("10/minute")
async def reset_password(payload: ResetPasswordRequest, request: Request):
    """Set a new password using a valid single-use token."""
    from services.password_policy import validate_password
    from services.password_tokens import peek_token, mark_token_used
    from services.audit import log_audit
    from core import mark_password_needs_reset

    r = peek_token(payload.token)
    if not r:
        raise HTTPException(status_code=400, detail="El enlace es inválido o expiró. Solicita uno nuevo.")

    validate_password(payload.new_password, email=r.get("email"))

    try:
        supabase_admin.auth.admin.update_user_by_id(r["user_id"], {"password": payload.new_password})
        mark_token_used(r["id"])
        mark_password_needs_reset(r["user_id"], needs=False)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reset_password persist error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar la contraseña")

    try:
        await log_audit(action="password_reset_completed", entity="auth",
                        actor_user_id=r["user_id"], actor_email=r.get("email"), request=request)
    except Exception:
        pass
    return {"ok": True, "message": "Contraseña actualizada. Ya puedes iniciar sesión."}

