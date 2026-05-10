"""Auto-extracted from server.py."""
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
        clinic = sdb.table('clinics').select('id,name,schedule_start,schedule_end,slot_duration,working_days,timezone').eq('id', clinic_id).single().execute()

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
        update = {k: v for k, v in data.model_dump().items() if v is not None}
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
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo máximo 2MB")
        ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
        path = f"{clinic_id}/logo.{ext}"
        supabase_admin.storage.from_('patient-files').upload(path, contents, {"content-type": file.content_type or "image/png", "upsert": "true"})
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
                except:
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
            if len(custom_pw) < 8:
                raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
            temp_password = custom_pw
        else:
            temp_password = f"Temp{uuid.uuid4().hex[:8]}!"
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

        # Check if already a member
        existing = sdb.table('clinic_members').select('id,is_active').eq('clinic_id', clinic_id).eq('user_id', user_id).maybe_single().execute()
        if existing and existing.data:
            if existing.data.get('is_active'):
                raise HTTPException(status_code=400, detail="El usuario ya es miembro de esta clínica")
            else:
                sdb.table('clinic_members').update({
                    "is_active": True, "role": data.role,
                    "first_name": data.first_name, "last_name": data.last_name,
                    "specialty": data.specialty, "updated_at": now_iso(),
                }).eq('id', existing.data['id']).execute()
                return {"message": "Miembro reactivado", "id": existing.data['id']}

        member_id = str(uuid.uuid4())
        sdb.table('clinic_members').insert({
            "id": member_id, "clinic_id": clinic_id, "user_id": user_id,
            "role": data.role, "first_name": data.first_name,
            "last_name": data.last_name, "specialty": data.specialty,
            "is_active": True, "created_at": now_iso(), "updated_at": now_iso(),
        }).execute()
        return {"message": "Miembro invitado exitosamente", "id": member_id, "temp_password": temp_password}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite member error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al invitar miembro: {str(e)}")

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
        return {"is_active": new_status, "message": "Miembro activado" if new_status else "Miembro desactivado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle member error: {e}")
        raise HTTPException(status_code=500, detail="Error")


@router.put("/clinic/members/{member_id}/password")
async def reset_member_password(member_id: str, data: MemberPasswordReset, ctx=Depends(require_clinic_member)):
    """Set/reset a clinic member's Supabase Auth password.

    Restricted to clinic_admin. Admin cannot change own password through this
    endpoint (must use their own profile/auth flow) to prevent accidental lockout.
    """
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar contraseñas")
    if member_id == ctx["member"]["id"]:
        raise HTTPException(status_code=400, detail="No puede cambiar su propia contraseña aquí; use su perfil")
    pw = (data.password or "").strip()
    if len(pw) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        member = sdb.table('clinic_members').select('id,user_id').eq('id', member_id).eq('clinic_id', clinic_id).maybe_single().execute()
        mdata = getattr(member, 'data', None) if member else None
        if not mdata:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        user_id = mdata.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="El miembro no tiene cuenta de autenticación")

        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": pw})
        return {"message": "Contraseña actualizada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset member password error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar contraseña")

