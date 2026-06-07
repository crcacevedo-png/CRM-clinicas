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
    from core import ACCESS_TOKEN_COOKIE
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
                email=payload.email
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
                clinic_id=cm.data[0].get("clinic_id")
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
        }
    raise HTTPException(status_code=403, detail="Usuario sin acceso")

