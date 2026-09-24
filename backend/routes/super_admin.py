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
        active = sdb.table('clinics').select('id', count='exact').eq('is_active', True).is_('deleted_at', 'null').execute()
        inactive = sdb.table('clinics').select('id', count='exact').eq('is_active', False).is_('deleted_at', 'null').execute()
        users_count = sdb.table('clinic_members').select('id', count='exact').is_('deleted_at', 'null').execute()
        patients_count = sdb.table('patients').select('id', count='exact').execute()

        recent = sdb.table('clinics').select('*').is_('deleted_at', 'null').order('created_at', desc=True).limit(10).execute()
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
        query = sdb.table('clinics').select('*').is_('deleted_at', 'null')

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
        # Enforce password policy on the initial admin's password.
        from services.password_policy import validate_password
        validate_password(data.admin_password, email=data.admin_email, name=data.admin_name)
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

        # Force the newly-created admin to change password on first login
        from core import mark_password_needs_reset
        mark_password_needs_reset(admin_user_id, needs=True)

        # Welcome email with a secure set-password link (best-effort; never blocks)
        welcome_email_sent = False
        try:
            import os
            from services.password_tokens import create_reset_token
            from services.email_service import send_email
            from services.email_templates import welcome_clinic_link
            raw = create_reset_token(admin_user_id, data.admin_email, purpose="welcome", ttl_minutes=60 * 72)
            setup_url = f"{os.environ.get('FRONTEND_URL', '')}/restablecer-password?token={raw}&welcome=1"
            tpl = welcome_clinic_link(
                admin_name=data.admin_name,
                clinic_name=data.name,
                login_email=data.admin_email,
                setup_url=setup_url,
            )
            res = await send_email(to=data.admin_email, subject=tpl["subject"], html=tpl["html"], text=tpl["text"])
            welcome_email_sent = bool(res.get("ok"))
        except Exception as e:
            logger.warning(f"welcome email failed: {e}")

        return {
            "message": "Clinica creada exitosamente",
            "clinic": clinic_doc,
            "welcome_email_sent": welcome_email_sent,
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

        # Enforce password policy
        from services.password_policy import validate_password
        validate_password(data.password, email=data.email, name=f"{data.name} {data.lastname}")

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

        # Force new member to change password on first login
        from core import mark_password_needs_reset
        mark_password_needs_reset(new_user_id, needs=True)

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
        query = sdb.table('clinic_members').select('*').is_('deleted_at', 'null')

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
            # Force user to set a new password on next login
            from core import mark_password_needs_reset
            mark_password_needs_reset(member.data["user_id"], needs=True)
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



# ============== DELETE ROUTES (HARD DELETE) ==============

# Tables that contain a `clinic_id` column and must be purged when a clinic is hard-deleted.
# Order matters only for readability; deletes are best-effort and isolated in try/except.
_CLINIC_SCOPED_TABLES = [
    # Child / dependent rows first (help avoid FK issues if cascades are missing)
    "sale_items", "prescription_items", "lab_order_items", "purchase_order_items",
    "payment_plan_installments", "payments", "commissions_earned",
    "inventory_movements", "inventory_batches", "inventory_stock",
    "sales", "prescriptions", "lab_orders", "purchase_orders",
    "medical_records", "appointments", "agenda_blocks",
    "accounts_receivable", "expenses",
    "products", "product_categories", "services", "suppliers",
    "cash_sessions", "cash_registers",
    "commission_settings",
    "announcement_dismissals", "announcement_views",
    "clinic_feature_overrides", "clinic_roles",
    "member_branches", "branches",
    "activity_logs", "export_jobs",
    "support_messages", "support_tickets",
    "patients",
    # clinic_members deleted separately (we need user_ids first)
]


def _delete_clinic_data(clinic_id: str) -> dict:
    """Best-effort purge of every row scoped to a clinic. Returns per-table counts."""
    stats = {}
    for tbl in _CLINIC_SCOPED_TABLES:
        try:
            # `support_messages` is scoped by ticket_id, not clinic_id — handle special-case
            if tbl == "support_messages":
                tickets = sdb.table('support_tickets').select('id').eq('clinic_id', clinic_id).execute()
                ids = [t['id'] for t in (tickets.data or [])]
                if ids:
                    sdb.table('support_messages').delete().in_('ticket_id', ids).execute()
                    stats[tbl] = len(ids)
                continue
            # Child *_items tables — scoped by parent id, not clinic_id
            if tbl == "sale_items":
                parents = sdb.table('sales').select('id').eq('clinic_id', clinic_id).execute()
                ids = [p['id'] for p in (parents.data or [])]
                if ids:
                    sdb.table('sale_items').delete().in_('sale_id', ids).execute()
                continue
            if tbl == "prescription_items":
                parents = sdb.table('prescriptions').select('id').eq('clinic_id', clinic_id).execute()
                ids = [p['id'] for p in (parents.data or [])]
                if ids:
                    sdb.table('prescription_items').delete().in_('prescription_id', ids).execute()
                continue
            if tbl == "lab_order_items":
                parents = sdb.table('lab_orders').select('id').eq('clinic_id', clinic_id).execute()
                ids = [p['id'] for p in (parents.data or [])]
                if ids:
                    sdb.table('lab_order_items').delete().in_('lab_order_id', ids).execute()
                continue
            if tbl == "purchase_order_items":
                parents = sdb.table('purchase_orders').select('id').eq('clinic_id', clinic_id).execute()
                ids = [p['id'] for p in (parents.data or [])]
                if ids:
                    sdb.table('purchase_order_items').delete().in_('purchase_order_id', ids).execute()
                continue

            res = sdb.table(tbl).delete().eq('clinic_id', clinic_id).execute()
            stats[tbl] = len(res.data or [])
        except Exception as e:
            logger.warning(f"purge clinic {clinic_id} table={tbl} failed: {e}")
            stats[tbl] = f"error:{str(e)[:80]}"
    return stats


@router.delete("/admin/clinics/{clinic_id}")
async def delete_clinic(
    clinic_id: str,
    request: Request,
    confirm_name: str = "",
    user=Depends(require_super_admin),
):
    """Soft-delete a clinic — moves it to the 30-day Papelera.

    Requires `?confirm_name=<exact clinic name>` as a safety guard.
    The clinic (and its members) are hidden from listings but data is preserved.
    A daily job in Papelera will purge items whose deleted_at is older than 30 days.
    Use POST /admin/trash/clinics/{id}/restore to undo before purge.
    """
    try:
        existing = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        if not existing or not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")
        clinic = existing.data

        if clinic.get("deleted_at"):
            raise HTTPException(status_code=400, detail="La clinica ya esta en la papelera.")

        if (confirm_name or "").strip() != (clinic.get("name") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="El nombre de confirmacion no coincide con el nombre de la clinica.",
            )

        # Actor identity for audit trail
        actor_email = None
        if isinstance(user, dict):
            actor_email = user.get("email")
        else:
            actor_email = getattr(user, "email", None)

        now = now_iso()
        sdb.table('clinics').update({
            "deleted_at": now,
            "deleted_by": actor_email,
            "is_active": False,
            "updated_at": now,
        }).eq('id', clinic_id).execute()

        # Soft-delete members too so they cannot log in
        sdb.table('clinic_members').update({
            "deleted_at": now,
            "deleted_by": actor_email,
            "is_active": False,
            "updated_at": now,
        }).eq('clinic_id', clinic_id).is_('deleted_at', 'null').execute()

        # Audit
        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="clinic_soft_deleted",
                entity="clinic",
                entity_id=clinic_id,
                clinic_id=clinic_id,
                **actor_from_super_admin(user),
                old_values={
                    "name": clinic.get("name"),
                    "plan": clinic.get("plan"),
                    "is_active": clinic.get("is_active"),
                },
                meta={"deleted_at": now, "purge_after_days": 30},
                request=request,
            )
        except Exception:
            pass

        return {
            "message": "Clinica enviada a la papelera. Se purgara automaticamente en 30 dias.",
            "clinic_id": clinic_id,
            "deleted_at": now,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Soft-delete clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar clinica")


@router.delete("/admin/users/{member_id}")
async def delete_user(
    member_id: str,
    request: Request,
    user=Depends(require_super_admin),
):
    """Soft-delete a clinic member — moves to Papelera (30 days)."""
    try:
        member_res = sdb.table('clinic_members').select('*').eq('id', member_id).maybe_single().execute()
        if not member_res or not member_res.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        member = member_res.data

        if member.get("deleted_at"):
            raise HTTPException(status_code=400, detail="El usuario ya esta en la papelera.")

        actor_id = None
        actor_email = None
        if isinstance(user, dict):
            actor_id = user.get("id") or user.get("user_id")
            actor_email = user.get("email")
        else:
            actor_id = getattr(user, "id", None)
            actor_email = getattr(user, "email", None)
        if actor_id and actor_id == member.get("user_id"):
            raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta.")

        try:
            auth_map = get_auth_users_map()
            email = (auth_map.get(member.get("user_id")) or {}).get("email")
        except Exception:
            email = member.get("email")

        now = now_iso()
        sdb.table('clinic_members').update({
            "deleted_at": now,
            "deleted_by": actor_email,
            "is_active": False,
            "updated_at": now,
        }).eq('id', member_id).execute()

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="member_soft_deleted",
                entity="clinic_member",
                entity_id=member_id,
                clinic_id=member.get("clinic_id"),
                **actor_from_super_admin(user),
                old_values={
                    "first_name": member.get("first_name"),
                    "last_name": member.get("last_name"),
                    "role": member.get("role"),
                    "email": email,
                    "user_id": member.get("user_id"),
                },
                meta={"deleted_at": now, "purge_after_days": 30},
                request=request,
            )
        except Exception:
            pass

        return {
            "message": "Usuario enviado a la papelera. Se purgara automaticamente en 30 dias.",
            "member_id": member_id,
            "deleted_at": now,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Soft-delete user error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar usuario")


# ============== PAPELERA (TRASH) ROUTES ==============

def _days_left_in_trash(deleted_at_iso: str) -> int:
    """Return remaining days before auto-purge (30 days retention)."""
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(deleted_at_iso.replace('Z', '+00:00'))
        now = dt.now(timezone.utc)
        elapsed = (now - d).days
        return max(0, 30 - elapsed)
    except Exception:
        return 0


@router.get("/admin/trash")
async def list_trash(user=Depends(require_super_admin)):
    """Return soft-deleted clinics and users with remaining days before purge."""
    try:
        clinics = sdb.table('clinics').select('*').not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute().data or []
        members = sdb.table('clinic_members').select('*').not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute().data or []

        auth_map = get_auth_users_map()

        clinics_out = []
        for c in clinics:
            clinics_out.append({
                **c,
                "days_left": _days_left_in_trash(c.get('deleted_at') or ''),
            })

        users_out = []
        for m in members:
            enriched = enrich_member(m, auth_map)
            clinic = sdb.table('clinics').select('name').eq('id', m.get('clinic_id', '')).maybe_single().execute()
            enriched["clinic_name"] = clinic.data["name"] if clinic and clinic.data else "N/A"
            enriched["days_left"] = _days_left_in_trash(m.get('deleted_at') or '')
            users_out.append(enriched)

        return {"clinics": clinics_out, "users": users_out}
    except Exception as e:
        logger.error(f"List trash error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar papelera")


@router.post("/admin/trash/clinics/{clinic_id}/restore")
async def restore_clinic(clinic_id: str, request: Request, user=Depends(require_super_admin)):
    """Restore a soft-deleted clinic. Also restores any members deleted in the same wave."""
    try:
        existing = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        if not existing or not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")
        if not existing.data.get("deleted_at"):
            raise HTTPException(status_code=400, detail="La clinica no esta en la papelera.")

        deleted_at = existing.data["deleted_at"]
        now = now_iso()

        sdb.table('clinics').update({
            "deleted_at": None,
            "deleted_by": None,
            "is_active": True,
            "updated_at": now,
        }).eq('id', clinic_id).execute()

        # Restore members that were deleted within 60 seconds of the clinic delete (same wave)
        try:
            from datetime import datetime as dt, timedelta
            base = dt.fromisoformat(deleted_at.replace('Z', '+00:00'))
            lo = (base - timedelta(seconds=60)).isoformat()
            hi = (base + timedelta(seconds=60)).isoformat()
            sdb.table('clinic_members').update({
                "deleted_at": None,
                "deleted_by": None,
                "is_active": True,
                "updated_at": now,
            }).eq('clinic_id', clinic_id).gte('deleted_at', lo).lte('deleted_at', hi).execute()
        except Exception as e:
            logger.warning(f"Could not restore members for {clinic_id}: {e}")

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="clinic_restored",
                entity="clinic",
                entity_id=clinic_id,
                clinic_id=clinic_id,
                **actor_from_super_admin(user),
                request=request,
            )
        except Exception:
            pass

        return {"message": "Clinica restaurada", "clinic_id": clinic_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al restaurar clinica")


@router.post("/admin/trash/users/{member_id}/restore")
async def restore_user(member_id: str, request: Request, user=Depends(require_super_admin)):
    """Restore a soft-deleted user."""
    try:
        existing = sdb.table('clinic_members').select('*').eq('id', member_id).maybe_single().execute()
        if not existing or not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not existing.data.get("deleted_at"):
            raise HTTPException(status_code=400, detail="El usuario no esta en la papelera.")

        # If the parent clinic is still in the trash, block restore
        clinic = sdb.table('clinics').select('deleted_at,name').eq('id', existing.data["clinic_id"]).maybe_single().execute()
        if clinic and clinic.data and clinic.data.get("deleted_at"):
            raise HTTPException(
                status_code=400,
                detail=f"La clinica '{clinic.data.get('name')}' esta en la papelera. Restaura primero la clinica.",
            )

        sdb.table('clinic_members').update({
            "deleted_at": None,
            "deleted_by": None,
            "is_active": True,
            "updated_at": now_iso(),
        }).eq('id', member_id).execute()

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="member_restored",
                entity="clinic_member",
                entity_id=member_id,
                clinic_id=existing.data.get("clinic_id"),
                **actor_from_super_admin(user),
                request=request,
            )
        except Exception:
            pass

        return {"message": "Usuario restaurado", "member_id": member_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore user error: {e}")
        raise HTTPException(status_code=500, detail="Error al restaurar usuario")


@router.delete("/admin/trash/clinics/{clinic_id}")
async def purge_clinic_now(clinic_id: str, request: Request, user=Depends(require_super_admin)):
    """Purge a clinic from the Papelera immediately (bypass 30-day wait)."""
    try:
        existing = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        if not existing or not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")
        if not existing.data.get("deleted_at"):
            raise HTTPException(status_code=400, detail="La clinica no esta en la papelera.")
        clinic = existing.data

        members_res = sdb.table('clinic_members').select('*').eq('clinic_id', clinic_id).execute()
        members = members_res.data or []
        member_user_ids = [m.get('user_id') for m in members if m.get('user_id')]

        purge_stats = _delete_clinic_data(clinic_id)
        try:
            sdb.table('clinic_members').delete().eq('clinic_id', clinic_id).execute()
            purge_stats["clinic_members"] = len(members)
        except Exception as e:
            logger.warning(f"delete clinic_members failed: {e}")

        auth_deleted = 0
        for uid in member_user_ids:
            try:
                other = sdb.table('clinic_members').select('id', count='exact').eq('user_id', uid).execute()
                if (other.count or 0) > 0:
                    continue
                supabase_admin.auth.admin.delete_user(uid)
                auth_deleted += 1
            except Exception as e:
                logger.warning(f"auth user delete failed user_id={uid}: {e}")

        sdb.table('clinics').delete().eq('id', clinic_id).execute()

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="clinic_purged",
                entity="clinic",
                entity_id=clinic_id,
                clinic_id=clinic_id,
                **actor_from_super_admin(user),
                old_values={"name": clinic.get("name"), "slug": clinic.get("slug")},
                meta={"purge_stats": purge_stats, "auth_users_deleted": auth_deleted, "manual_purge": True},
                request=request,
            )
        except Exception:
            pass

        return {"message": "Clinica purgada permanentemente", "clinic_id": clinic_id, "purge_stats": purge_stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Purge clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al purgar clinica")


@router.delete("/admin/trash/users/{member_id}")
async def purge_user_now(member_id: str, request: Request, user=Depends(require_super_admin)):
    """Purge a user from the Papelera immediately."""
    try:
        member_res = sdb.table('clinic_members').select('*').eq('id', member_id).maybe_single().execute()
        if not member_res or not member_res.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not member_res.data.get("deleted_at"):
            raise HTTPException(status_code=400, detail="El usuario no esta en la papelera.")
        member = member_res.data

        sdb.table('clinic_members').delete().eq('id', member_id).execute()

        auth_deleted = False
        uid = member.get("user_id")
        if uid:
            try:
                other = sdb.table('clinic_members').select('id', count='exact').eq('user_id', uid).execute()
                if (other.count or 0) == 0:
                    supabase_admin.auth.admin.delete_user(uid)
                    auth_deleted = True
            except Exception as e:
                logger.warning(f"auth user delete failed user_id={uid}: {e}")

        try:
            from services.audit import log_audit, actor_from_super_admin
            await log_audit(
                action="member_purged",
                entity="clinic_member",
                entity_id=member_id,
                clinic_id=member.get("clinic_id"),
                **actor_from_super_admin(user),
                old_values={
                    "first_name": member.get("first_name"),
                    "last_name": member.get("last_name"),
                    "role": member.get("role"),
                    "user_id": uid,
                },
                meta={"auth_user_deleted": auth_deleted, "manual_purge": True},
                request=request,
            )
        except Exception:
            pass

        return {"message": "Usuario purgado permanentemente", "member_id": member_id, "auth_user_deleted": auth_deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Purge user error: {e}")
        raise HTTPException(status_code=500, detail="Error al purgar usuario")


@router.post("/admin/migrations/run")
async def admin_run_migrations(user=Depends(require_super_admin)):
    """Force-apply any pending DDL migrations.

    Useful when Supabase was down at startup and the auto-runner skipped them.
    Idempotent — safe to call multiple times.
    """
    from services.migrations import run_pending_migrations
    return run_pending_migrations()

