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

# ============== BRANCH ROUTES ==============

class BranchCreate(BaseModel):
    name: str
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    is_main: bool = False
    is_active: bool = True

@router.get("/clinic/branches")
async def list_branches(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('branches').select('*').eq('clinic_id', clinic_id).order('is_main', desc=True).order('name').execute()
        branches = result.data or []
        for b in branches:
            mb = sdb.table('member_branches').select('member_id', count='exact').eq('branch_id', b['id']).execute()
            b['member_count'] = mb.count or 0
        return branches
    except Exception as e:
        logger.error(f"List branches error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar sucursales")

@router.post("/clinic/branches")
async def create_branch(data: BranchCreate, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('plan,max_users').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')
        plan = sdb.table('plans').select('max_branches').eq('code', plan_code).maybe_single().execute()
        max_branches = plan.data.get('max_branches', 1) if plan.data else 1
        current = sdb.table('branches').select('id', count='exact').eq('clinic_id', clinic_id).execute()
        if (current.count or 0) >= max_branches:
            raise HTTPException(status_code=400, detail=f"Has alcanzado el límite de sucursales de tu plan ({max_branches}). Actualiza a un plan superior.")

        now = now_iso()
        branch_id = str(uuid.uuid4())
        if data.is_main:
            sdb.table('branches').update({"is_main": False, "updated_at": now}).eq('clinic_id', clinic_id).eq('is_main', True).execute()
        doc = {
            "id": branch_id, "clinic_id": clinic_id,
            "name": data.name, "code": data.code,
            "address": data.address, "city": data.city, "state": data.state,
            "phone": data.phone, "email": data.email,
            "schedule_start": data.schedule_start, "schedule_end": data.schedule_end,
            "is_main": data.is_main, "is_active": data.is_active,
            "created_at": now, "updated_at": now,
        }
        sdb.table('branches').insert(doc).execute()
        return {"id": branch_id, "message": "Sucursal creada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create branch error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear sucursal")

@router.put("/clinic/branches/{branch_id}")
async def update_branch(branch_id: str, data: BranchCreate, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        now = now_iso()
        if data.is_main:
            sdb.table('branches').update({"is_main": False, "updated_at": now}).eq('clinic_id', clinic_id).eq('is_main', True).execute()
        update = {k: v for k, v in data.model_dump().items() if v is not None}
        update["updated_at"] = now
        sdb.table('branches').update(update).eq('id', branch_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Sucursal actualizada"}
    except Exception as e:
        logger.error(f"Update branch error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar sucursal")

@router.get("/clinic/branches/{branch_id}/members")
async def list_branch_members(branch_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        mb = sdb.table('member_branches').select('member_id,is_primary').eq('branch_id', branch_id).execute()
        assigned = {r['member_id']: r['is_primary'] for r in (mb.data or [])}
        all_members = sdb.table('clinic_members').select('id,first_name,last_name,role,is_active').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        result = []
        for m in (all_members.data or []):
            result.append({**m, "assigned": m['id'] in assigned, "is_primary": assigned.get(m['id'], False)})
        return result
    except Exception as e:
        logger.error(f"List branch members error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/clinic/branches/{branch_id}/members")
async def set_branch_members(branch_id: str, data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    try:
        members = data.get('members', [])
        sdb.table('member_branches').delete().eq('branch_id', branch_id).execute()
        for m in members:
            sdb.table('member_branches').insert({
                "branch_id": branch_id, "member_id": m['member_id'],
                "is_primary": m.get('is_primary', False),
            }).execute()
        return {"message": "Miembros actualizados"}
    except Exception as e:
        logger.error(f"Set branch members error: {e}")
        raise HTTPException(status_code=500, detail="Error")

