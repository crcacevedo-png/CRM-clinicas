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

# ============== AUTH ROUTES ==============

@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        response = supabase_user.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        if not response.session:
            raise HTTPException(status_code=401, detail="Credenciales invalidas")

        user_id = response.user.id

        # Check user type in Supabase tables
        sa = sdb.table('super_admins').select('id').eq('user_id', user_id).execute()
        if sa.data:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="super_admin",
                user_id=user_id,
                email=request.email
            )

        cm = sdb.table('clinic_members').select('clinic_id').eq('user_id', user_id).eq('is_active', True).execute()
        if cm.data:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="clinic_member",
                user_id=user_id,
                email=request.email,
                clinic_id=cm.data[0].get("clinic_id")
            )

        raise HTTPException(status_code=403, detail="No tienes acceso al sistema")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Error de autenticacion")

@router.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    try:
        supabase_user.auth.sign_out()
    except Exception:
        pass
    return {"message": "Sesion cerrada correctamente"}

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

