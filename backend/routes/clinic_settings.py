"""Auto-extracted from server.py."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
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

# ============== CLINIC CONFIG ROUTES ==============

@router.get("/clinic/config")
async def get_clinic_config(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('id,name,schedule_start,schedule_end,slot_duration,working_days,working_hours,timezone').eq('id', clinic_id).single().execute()

        members = sdb.table('clinic_members').select('id,first_name,last_name,role,specialty').eq('clinic_id', clinic_id).eq('is_active', True).execute()

        doctors = [m for m in (members.data or []) if m["role"] in ("doctor", "clinic_admin")]

        return {
            "clinic": clinic.data,
            "members": members.data or [],
            "doctors": doctors,
            "current_member": ctx["member"],
        }
    except Exception as e:
        logger.error(f"Clinic config error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener configuracion")

# ============== CLINIC SETTINGS ROUTES ==============

class ClinicSettingsUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: Optional[str] = None
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    slot_duration: Optional[int] = None
    working_days: Optional[list] = None
    working_hours: Optional[dict] = None  # {"1": {"start":"08:00","end":"17:00"}, ...} keyed by isoweekday 1-7
    prescription_footer: Optional[str] = None
    prescription_validity_days: Optional[int] = None

class MemberInvite(BaseModel):
    email: str
    first_name: str
    last_name: str
    role: str = "doctor"
    specialty: Optional[str] = None
    password: Optional[str] = None  # If empty, a random temp password is generated

class MemberUpdate(BaseModel):
    role: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None

class MemberPasswordReset(BaseModel):
    password: str

@router.get("/clinic/settings")
async def get_clinic_settings(ctx=Depends(require_clinic_member)):
    """Get full clinic settings (admin only)"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('*').eq('id', clinic_id).single().execute()
        return clinic.data
    except Exception as e:
        logger.error(f"Get clinic settings error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener configuración")

@router.put("/clinic/settings")
async def update_clinic_settings(data: ClinicSettingsUpdate, ctx=Depends(require_clinic_member)):
    """Update clinic settings (admin only)"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden editar configuración")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        # Use exclude_unset so fields the client did not send are not touched.
        # Fields explicitly sent as null (e.g. working_hours -> null to disable per-day) are kept.
        update = data.model_dump(exclude_unset=True)
        update["updated_at"] = now_iso()
        sdb.table('clinics').update(update).eq('id', clinic_id).execute()
        return {"message": "Configuración actualizada"}
    except Exception as e:
        logger.error(f"Update clinic settings error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar configuración")

@router.post("/clinic/settings/logo")
async def upload_clinic_logo(file: UploadFile = File(...), ctx=Depends(require_clinic_member)):
    """Upload clinic logo"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        contents = await file.read()
        # Magic-bytes validation (defeats Content-Type spoofing)
        try:
            from services.input_sanitizer import validate_image_upload
            detected_mime = validate_image_upload(contents, max_bytes=2 * 1024 * 1024)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        ext_map = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/heic': 'heic', 'image/heif': 'heif', 'image/gif': 'gif'}
        ext = ext_map.get(detected_mime, 'png')
        path = f"{clinic_id}/logo.{ext}"
        supabase_admin.storage.from_('patient-files').upload(path, contents, {"content-type": detected_mime, "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 31536000)
        logo_url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('clinics').update({"logo_url": logo_url, "updated_at": now_iso()}).eq('id', clinic_id).execute()
        return {"logo_url": logo_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload logo error: {e}")
        raise HTTPException(status_code=500, detail="Error al subir logo")

@router.get("/clinic/members")
async def list_clinic_members(ctx=Depends(require_clinic_member)):
    """List all clinic members"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('clinic_members').select('id,user_id,first_name,last_name,role,specialty,license_number,phone,is_active,created_at').eq('clinic_id', clinic_id).order('created_at').execute()
        members = result.data or []
        # Get emails from auth
        for m in members:
            if m.get('user_id'):
                try:
                    u = supabase_admin.auth.admin.get_user_by_id(m['user_id'])
                    m['email'] = u.user.email if u and u.user else ''
                except Exception:
                    m['email'] = ''
            else:
                m['email'] = ''
        return members
    except Exception as e:
        logger.error(f"List members error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar miembros")

@router.post("/clinic/members/invite")
async def invite_member(data: MemberInvite, ctx=Depends(require_clinic_member)):
    """Invite a new member to the clinic"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden invitar miembros")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        # Check plan limits
        clinic = sdb.table('clinics').select('max_users').eq('id', clinic_id).single().execute()
        current_count = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        if (current_count.count or 0) >= (clinic.data.get('max_users') or 999):
            raise HTTPException(status_code=400, detail="Límite de usuarios alcanzado para su plan")

        # Create auth user or get existing
        # If admin provided a custom password, use it (with validation); else generate temp
        custom_pw = (data.password or "").strip()
        if custom_pw:
            from services.password_policy import validate_password
            validate_password(custom_pw, email=data.email, name=f"{data.first_name} {data.last_name}")
            temp_password = custom_pw
        else:
            temp_password = generate_password()
        try:
            auth_user = supabase_admin.auth.admin.create_user({
                "email": data.email,
                "password": temp_password,
                "email_confirm": True,
            })
            user_id = auth_user.user.id
        except Exception:
            # User may already exist
            users = supabase_admin.auth.admin.list_users()
            user_id = None
            for u in users:
                if u.email == data.email:
                    user_id = u.id
                    break
            if not user_id:
                raise HTTPException(status_code=400, detail="Error al crear usuario")

        # Check if already a member.
        # Note: to avoid email enumeration, the response message stays uniform
        # ("Miembro listo") for both fresh invites and reactivations. The audit
        # log captures the distinction (member_invited vs member_reactivated).
        existing = sdb.table('clinic_members').select('id,is_active').eq('clinic_id', clinic_id).eq('user_id', user_id).maybe_single().execute()
        if existing and existing.data:
            sdb.table('clinic_members').update({
                "is_active": True, "role": data.role,
                "first_name": data.first_name, "last_name": data.last_name,
                "specialty": data.specialty, "updated_at": now_iso(),
            }).eq('id', existing.data['id']).execute()
            try:
                from services.audit import log_audit, actor_from_ctx
                await log_audit(
                    action="member_reactivated" if not existing.data.get('is_active') else "member_reinvited",
                    entity="clinic_member",
                    entity_id=existing.data['id'],
                    **actor_from_ctx(ctx),
                    new_values={"email": data.email, "role": data.role},
                )
            except Exception:
                pass
            return {"message": "Miembro listo", "id": existing.data['id']}

        member_id = str(uuid.uuid4())
        sdb.table('clinic_members').insert({
            "id": member_id, "clinic_id": clinic_id, "user_id": user_id,
            "role": data.role, "first_name": data.first_name,
            "last_name": data.last_name, "specialty": data.specialty,
            "is_active": True, "created_at": now_iso(), "updated_at": now_iso(),
        }).execute()

        # Force the invited member to change password on first login
        from core import mark_password_needs_reset
        mark_password_needs_reset(user_id, needs=True)
        try:
            from services.audit import log_audit, actor_from_ctx
            await log_audit(
                action="member_invited",
                entity="clinic_member",
                entity_id=member_id,
                **actor_from_ctx(ctx),
                new_values={"email": data.email, "role": data.role, "name": f"{data.first_name} {data.last_name}"},
            )
        except Exception:
            pass
        return {"message": "Miembro invitado exitosamente", "id": member_id, "temp_password": temp_password}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite member error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al invitar miembro")

@router.put("/clinic/members/{member_id}")
async def update_member(member_id: str, data: MemberUpdate, ctx=Depends(require_clinic_member)):
    """Update a clinic member"""
    clinic_id = ctx["member"]["clinic_id"]
    current_role = ctx["member"]["role"]
    current_id = ctx["member"]["id"]

    # Only admin can change roles; members can edit their own profile
    is_self = member_id == current_id
    if not is_self and current_role != "clinic_admin":
        raise HTTPException(status_code=403, detail="No tiene permiso")
    try:
        update = {}
        if data.role is not None and current_role == "clinic_admin" and not is_self:
            update["role"] = data.role
        if data.first_name is not None: update["first_name"] = data.first_name
        if data.last_name is not None: update["last_name"] = data.last_name
        if data.specialty is not None: update["specialty"] = data.specialty
        if data.license_number is not None: update["license_number"] = data.license_number
        if data.phone is not None: update["phone"] = data.phone
        update["updated_at"] = now_iso()

        sdb.table('clinic_members').update(update).eq('id', member_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Miembro actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update member error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar miembro")

@router.put("/clinic/members/{member_id}/toggle")
async def toggle_member(member_id: str, ctx=Depends(require_clinic_member)):
    """Activate/deactivate a member"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    if member_id == ctx["member"]["id"]:
        raise HTTPException(status_code=400, detail="No puede desactivarse a sí mismo")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('clinic_members').select('id,is_active').eq('id', member_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        new_status = not existing.data.get('is_active', True)
        sdb.table('clinic_members').update({"is_active": new_status, "updated_at": now_iso()}).eq('id', member_id).execute()
        try:
            from services.audit import log_audit, actor_from_ctx
            await log_audit(
                action="member_activated" if new_status else "member_deactivated",
                entity="clinic_member",
                entity_id=member_id,
                **actor_from_ctx(ctx),
            )
        except Exception:
            pass
        return {"is_active": new_status, "message": "Miembro activado" if new_status else "Miembro desactivado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle member error: {e}")
        raise HTTPException(status_code=500, detail="Error")


from server import limiter


@router.put("/clinic/members/{member_id}/password")
@limiter.limit("10/minute")
async def reset_member_password(member_id: str, data: MemberPasswordReset, request: Request, ctx=Depends(require_clinic_member)):
    """Set/reset a clinic member's Supabase Auth password.

    Restricted to clinic_admin. Admin cannot change own password through this
    endpoint (must use their own profile/auth flow) to prevent accidental lockout.
    """
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar contraseñas")
    if member_id == ctx["member"]["id"]:
        raise HTTPException(status_code=400, detail="No puede cambiar su propia contraseña aquí; use su perfil")
    pw = (data.password or "").strip()
    clinic_id = ctx["member"]["clinic_id"]
    try:
        member = sdb.table('clinic_members').select('id,user_id,first_name,last_name').eq('id', member_id).eq('clinic_id', clinic_id).maybe_single().execute()
        mdata = getattr(member, 'data', None) if member else None
        if not mdata:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        user_id = mdata.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="El miembro no tiene cuenta de autenticación")

        # Fetch email of the target user for personal-token check
        try:
            target_user = supabase_admin.auth.admin.get_user_by_id(user_id)
            target_email = target_user.user.email if target_user and target_user.user else None
        except Exception:
            target_email = None
        from services.password_policy import validate_password
        validate_password(pw, email=target_email,
                          name=f"{mdata.get('first_name','')} {mdata.get('last_name','')}")

        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": pw})

        # Force the affected user to change password on next login
        from core import mark_password_needs_reset
        mark_password_needs_reset(user_id, needs=True)

        # Audit log (sensitive: someone changed a credential)
        try:
            from services.audit import log_audit, actor_from_ctx
            await log_audit(
                action="member_password_reset",
                entity="clinic_member",
                entity_id=member_id,
                **actor_from_ctx(ctx),
                meta={"target_user_id": user_id, "target_name": f"{mdata.get('first_name','')} {mdata.get('last_name','')}".strip()},
            )
        except Exception:
            pass

        # Send email notification to the affected user (best-effort, async)
        try:
            from services.email_service import send_email
            from services.email_templates import password_reset
            # Resolve target email + names
            target_user = supabase_admin.auth.admin.get_user_by_id(user_id)
            target_email = getattr(getattr(target_user, "user", target_user), "email", None)
            if target_email:
                tpl = password_reset(
                    user_name=f"{mdata.get('first_name','')} {mdata.get('last_name','')}".strip() or "Usuario",
                    new_password=pw,
                    login_url=os.environ.get('FRONTEND_URL', 'https://app.cortexiamedical.com'),
                    set_by=f"{ctx['member'].get('first_name','')} {ctx['member'].get('last_name','')}".strip() or "Administrador",
                )
                await send_email(to=target_email, subject=tpl["subject"], html=tpl["html"], text=tpl["text"])
        except Exception as _e:
            logger.warning(f"reset_member_password: email notification failed: {_e}")

        return {"message": "Contraseña actualizada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset member password error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar contraseña")

