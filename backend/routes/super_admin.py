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

# ============== DASHBOARD ROUTES ==============

@router.get("/admin/dashboard")
async def get_dashboard_stats(user=Depends(require_super_admin)):
    try:
        active = sdb.table('clinics').select('id', count='exact').eq('is_active', True).execute()
        inactive = sdb.table('clinics').select('id', count='exact').eq('is_active', False).execute()
        users_count = sdb.table('clinic_members').select('id', count='exact').execute()
        patients_count = sdb.table('patients').select('id', count='exact').execute()

        recent = sdb.table('clinics').select('*').order('created_at', desc=True).limit(10).execute()
        recent_clinics = recent.data or []

        for clinic in recent_clinics:
            uc = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            pc = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            clinic["users_count"] = uc.count or 0
            clinic["patients_count"] = pc.count or 0

        return {
            "active_clinics": active.count or 0,
            "inactive_clinics": inactive.count or 0,
            "total_users": users_count.count or 0,
            "total_patients": patients_count.count or 0,
            "recent_clinics": recent_clinics
        }
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadisticas")

# ============== CLINIC ROUTES ==============

@router.get("/admin/clinics")
async def list_clinics(
    search: Optional[str] = None,
    country: Optional[str] = None,
    plan: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_super_admin)
):
    try:
        query = sdb.table('clinics').select('*')

        if search:
            query = query.ilike('name', f'%{search}%')
        if country:
            query = query.eq('country', country)
        if plan:
            query = query.eq('plan', plan)
        if status:
            query = query.eq('is_active', status == "active")

        result = query.order('created_at', desc=True).execute()
        clinics = result.data or []

        for clinic in clinics:
            uc = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            pc = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            clinic["users_count"] = uc.count or 0
            clinic["patients_count"] = pc.count or 0

        return clinics
    except Exception as e:
        logger.error(f"List clinics error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar clinicas")

@router.post("/admin/clinics")
async def create_clinic(data: ClinicCreate, user=Depends(require_super_admin)):
    try:
        # 1. Create user in Supabase Auth
        try:
            auth_response = supabase_admin.auth.admin.create_user({
                "email": data.admin_email,
                "password": data.admin_password,
                "email_confirm": True
            })
            if not auth_response.user:
                raise HTTPException(status_code=400, detail="Error al crear usuario en Supabase")
            admin_user_id = auth_response.user.id
        except Exception as e:
            logger.error(f"Supabase user creation error: {e}")
            raise HTTPException(status_code=400, detail=f"Error al crear usuario: {str(e)}")

        # 2. Create clinic
        clinic_id = str(uuid.uuid4())
        now = now_iso()
        limits = get_plan_limits(data.plan)
        tz = data.timezone or 'America/Guatemala'

        clinic_doc = {
            "id": clinic_id,
            "name": data.name,
            "slug": generate_slug(data.name),
            "country": data.country,
            "city": data.city or "",
            "address": data.address or "",
            "phone": data.phone or "",
            "email": data.email or "",
            "timezone": tz,
            "schedule_start": "08:00:00",
            "schedule_end": "17:00:00",
            "slot_duration": 30,
            "working_days": [1, 2, 3, 4, 5],
            "plan": data.plan,
            "max_users": limits["max_users"],
            "max_patients": limits["max_patients"],
            "max_storage_mb": limits["max_storage_mb"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinics').insert(clinic_doc).execute()

        # 3. Create clinic member
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": admin_user_id,
            "clinic_id": clinic_id,
            "role": "clinic_admin",
            "first_name": data.admin_name,
            "last_name": data.admin_lastname,
            "phone": data.admin_phone or "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinic_members').insert(member_doc).execute()

        return {
            "message": "Clinica creada exitosamente",
            "clinic": clinic_doc,
            "admin_credentials": {
                "email": data.admin_email,
                "password": data.admin_password
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear clinica")

@router.get("/admin/clinics/{clinic_id}")
async def get_clinic(clinic_id: str, user=Depends(require_super_admin)):
    try:
        try:
            result = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        except Exception:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")
        if not result.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        clinic = result.data

        # Get members
        members_result = sdb.table('clinic_members').select('*').eq('clinic_id', clinic_id).execute()
        auth_map = get_auth_users_map()
        members = [enrich_member(m, auth_map) for m in (members_result.data or [])]

        # Get stats
        patients_count = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).execute()

        stats = {
            "total_patients": patients_count.count or 0,
            "total_appointments": 0,
            "total_prescriptions": 0,
            "members_count": len(members)
        }

        return {
            "clinic": clinic,
            "members": members,
            "stats": stats,
            "activity": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener clinica")

@router.put("/admin/clinics/{clinic_id}")
async def update_clinic(clinic_id: str, data: ClinicUpdate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = now_iso()

        if "name" in update_data:
            update_data["slug"] = generate_slug(update_data["name"])

        if "plan" in update_data:
            limits = get_plan_limits(update_data["plan"])
            update_data.update(limits)

        sdb.table('clinics').update(update_data).eq('id', clinic_id).execute()

        updated = sdb.table('clinics').select('*').eq('id', clinic_id).single().execute()

        # Audit: capture which sensitive fields changed
        try:
            from services.audit import log_audit, actor_from_super_admin
            sensitive_keys = ('plan', 'is_active', 'max_users', 'max_patients', 'max_storage_mb', 'max_branches', 'country', 'currency')
            before = {k: existing.data.get(k) for k in sensitive_keys if k in existing.data}
            after = {k: update_data.get(k, existing.data.get(k)) for k in sensitive_keys if k in update_data or k in existing.data}
            changes = {k: {"from": before.get(k), "to": after.get(k)} for k in sensitive_keys if before.get(k) != after.get(k)}
            if changes:
                # Special-case plan change → its own action for easy filtering
                if "plan" in changes:
                    await log_audit(
                        action="clinic_plan_change",
                        entity="clinic",
                        entity_id=clinic_id,
                        clinic_id=clinic_id,
                        **actor_from_super_admin(user),
                        old_values={"plan": changes["plan"]["from"]},
                        new_values={"plan": changes["plan"]["to"]},
                    )
                if "is_active" in changes:
                    await log_audit(
                        action="clinic_activated" if changes["is_active"]["to"] else "clinic_deactivated",
                        entity="clinic",
                        entity_id=clinic_id,
                        clinic_id=clinic_id,
                        **actor_from_super_admin(user),
                    )
                # Generic update event with all sensitive changes
                await log_audit(
                    action="clinic_update",
                    entity="clinic",
                    entity_id=clinic_id,
                    clinic_id=clinic_id,
                    **actor_from_super_admin(user),
                    meta={"changes": changes},
                )
        except Exception:
            pass

        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar clinica")

@router.post("/admin/clinics/{clinic_id}/members")
async def add_clinic_member(clinic_id: str, data: ClinicMemberCreate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinics').select('id').eq('id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        # Create user in Supabase Auth
        try:
            auth_response = supabase_admin.auth.admin.create_user({
                "email": data.email,
                "password": data.password,
                "email_confirm": True
            })
            if not auth_response.user:
                raise HTTPException(status_code=400, detail="Error al crear usuario")
            new_user_id = auth_response.user.id
        except Exception as e:
            logger.error(f"Supabase user creation error: {e}")
            raise HTTPException(status_code=400, detail=f"Error al crear usuario: {str(e)}")

        now = now_iso()
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": new_user_id,
            "clinic_id": clinic_id,
            "role": data.role,
            "first_name": data.name,
            "last_name": data.lastname,
            "phone": data.phone or "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinic_members').insert(member_doc).execute()

        return {
            "message": "Usuario creado exitosamente",
            "credentials": {
                "email": data.email,
                "password": data.password
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add member error: {e}")
        raise HTTPException(status_code=500, detail="Error al agregar miembro")

# ============== USER ROUTES ==============

@router.get("/admin/users")
async def list_users(
    search: Optional[str] = None,
    clinic_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_super_admin)
):
    try:
        query = sdb.table('clinic_members').select('*')

        if search:
            from services.input_sanitizer import sanitize_postgrest_search
            ss = sanitize_postgrest_search(search)
            query = query.or_(f'first_name.ilike.%{ss}%,last_name.ilike.%{ss}%')
        if clinic_id:
            query = query.eq('clinic_id', clinic_id)
        if role:
            query = query.eq('role', role)
        if status:
            query = query.eq('is_active', status == "active")

        result = query.order('created_at', desc=True).execute()
        members = result.data or []

        auth_map = get_auth_users_map()
        enriched = []
        for m in members:
            enriched_m = enrich_member(m, auth_map)
            # Add clinic name
            clinic = sdb.table('clinics').select('name').eq('id', m.get('clinic_id', '')).maybe_single().execute()
            enriched_m["clinic_name"] = clinic.data["name"] if clinic.data else "N/A"
            enriched.append(enriched_m)

        # If searching by email, filter in Python
        if search:
            search_lower = search.lower()
            enriched = [u for u in enriched if (
                search_lower in u.get("name", "").lower() or
                search_lower in u.get("lastname", "").lower() or
                search_lower in u.get("email", "").lower()
            )]

        return enriched
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar usuarios")

@router.put("/admin/users/{member_id}")
async def update_user(member_id: str, data: UserUpdate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinic_members').select('id').eq('id', member_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = now_iso()

        sdb.table('clinic_members').update(update_data).eq('id', member_id).execute()

        updated = sdb.table('clinic_members').select('*').eq('id', member_id).single().execute()
        auth_map = get_auth_users_map()
        return enrich_member(updated.data, auth_map)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar usuario")

from server import limiter


@router.post("/admin/users/{member_id}/reset-password")
@limiter.limit("10/minute")
async def reset_user_password(member_id: str, request: Request, user=Depends(require_super_admin)):
    try:
        member = sdb.table('clinic_members').select('user_id,clinic_id,first_name,last_name,email').eq('id', member_id).maybe_single().execute()
        if not member.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        new_password = generate_password()

        try:
            supabase_admin.auth.admin.update_user_by_id(
                member.data["user_id"],
                {"password": new_password}
            )
        except Exception as e:
            logger.error(f"Reset password error: {e}")
            raise HTTPException(status_code=400, detail="Error al resetear contrasena")

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="member_password_reset",
                entity="clinic_member",
                entity_id=member_id,
                clinic_id=member.data.get("clinic_id"),
                **actor_from_super_admin(user),
                meta={
                    "target_email": member.data.get("email"),
                    "target_name": f"{member.data.get('first_name','')} {member.data.get('last_name','')}".strip(),
                    "by": "super_admin",
                },
            )
        except Exception:
            pass

        return {
            "message": "Contrasena reseteada exitosamente",
            "new_password": new_password
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="Error al resetear contrasena")



@router.post("/admin/migrations/run")
async def admin_run_migrations(user=Depends(require_super_admin)):
    """Force-apply any pending DDL migrations.

    Useful when Supabase was down at startup and the auto-runner skipped them.
    Idempotent — safe to call multiple times.
    """
    from services.migrations import run_pending_migrations
    return run_pending_migrations()

