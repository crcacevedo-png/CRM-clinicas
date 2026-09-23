"""Clinic roles & module-permission management (clinic_admin only).

Manages fixed/system roles and custom roles with per-module (menu-level) access.
Backend enforcement of the resulting permissions is done via core.require_module(...)
applied on each module's routes; this router lets a clinic_admin view/edit the
permission matrix and assign roles to members.
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()

from core import (
    sdb, now_iso, logger, validate_uuid, generate_slug,
    require_clinic_member, require_clinic_admin,
    MODULE_CATALOG, ALL_MODULE_KEYS, SYSTEM_ROLES, SYSTEM_ROLE_LABELS,
    SYSTEM_ROLE_DESCRIPTIONS, DEFAULT_ROLE_MODULES, ENUM_ROLE_VALUES,
)


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    modules: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    modules: Optional[List[str]] = None


class MemberRoleAssign(BaseModel):
    role: str


def _clean_modules(mods):
    return [m for m in (mods or []) if m in ALL_MODULE_KEYS]


def ensure_system_roles(clinic_id: str):
    """Seed the 5 system roles for a clinic if they don't exist yet (idempotent)."""
    try:
        existing = sdb.table('clinic_roles').select('key').eq('clinic_id', clinic_id).eq('is_system', True).execute()
        have = {r['key'] for r in (existing.data or [])}
    except Exception as e:
        logger.warning(f"ensure_system_roles read failed: {e}")
        have = set()
    to_insert = []
    for key in SYSTEM_ROLES:
        if key in have:
            continue
        now = now_iso()
        to_insert.append({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "key": key,
            "name": SYSTEM_ROLE_LABELS.get(key, key),
            "description": SYSTEM_ROLE_DESCRIPTIONS.get(key, ""),
            "is_system": True,
            "modules": (list(ALL_MODULE_KEYS) if key == "clinic_admin" else DEFAULT_ROLE_MODULES.get(key, [])),
            "created_at": now,
            "updated_at": now,
        })
    if to_insert:
        try:
            sdb.table('clinic_roles').insert(to_insert).execute()
        except Exception as e:
            logger.warning(f"ensure_system_roles insert failed: {e}")


def _member_counts(clinic_id: str) -> dict:
    try:
        rows = sdb.table('clinic_members').select('role,role_key').eq('clinic_id', clinic_id).eq('is_active', True).execute().data or []
    except Exception:
        rows = []
    counts = {}
    for r in rows:
        k = r.get('role_key') or r.get('role') or ''
        counts[k] = counts.get(k, 0) + 1
    return counts


@router.get("/clinic/roles")
async def list_roles(ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    ensure_system_roles(clinic_id)
    try:
        rows = (sdb.table('clinic_roles').select('*')
                .eq('clinic_id', clinic_id)
                .order('is_system', desc=True).order('name')
                .execute().data) or []
    except Exception as e:
        logger.error(f"list_roles error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar roles")
    counts = _member_counts(clinic_id)
    for r in rows:
        r['member_count'] = counts.get(r['key'], 0)
        r['locked'] = (r['key'] == 'clinic_admin')  # admin role can't be edited/deleted
    return {"roles": rows, "modules": MODULE_CATALOG}


@router.post("/clinic/roles")
async def create_role(data: RoleCreate, ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    ensure_system_roles(clinic_id)
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del rol es requerido")
    key = generate_slug(name) or f"rol-{uuid.uuid4().hex[:6]}"
    try:
        existing = sdb.table('clinic_roles').select('id').eq('clinic_id', clinic_id).eq('key', key).maybe_single().execute()
        if getattr(existing, 'data', None):
            key = f"{key}-{uuid.uuid4().hex[:4]}"
    except Exception:
        pass
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "key": key,
        "name": name,
        "description": (data.description or "").strip() or None,
        "is_system": False,
        "modules": _clean_modules(data.modules),
        "created_at": now,
        "updated_at": now,
    }
    try:
        sdb.table('clinic_roles').insert(doc).execute()
    except Exception as e:
        logger.error(f"create_role error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear rol")
    doc['member_count'] = 0
    doc['locked'] = False
    return doc


@router.put("/clinic/roles/{role_id}")
async def update_role(role_id: str, data: RoleUpdate, ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    validate_uuid(role_id, "role_id")
    role = sdb.table('clinic_roles').select('*').eq('id', role_id).eq('clinic_id', clinic_id).maybe_single().execute()
    rdata = getattr(role, 'data', None)
    if not rdata:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if rdata['key'] == 'clinic_admin':
        raise HTTPException(status_code=400, detail="El rol Administrador no se puede modificar")
    update = {"updated_at": now_iso()}
    if data.modules is not None:
        update['modules'] = _clean_modules(data.modules)
    # Only custom roles can rename / change description; system roles keep their label
    if not rdata['is_system']:
        if data.name is not None:
            nm = data.name.strip()
            if not nm:
                raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
            update['name'] = nm
        if data.description is not None:
            update['description'] = data.description.strip() or None
    try:
        sdb.table('clinic_roles').update(update).eq('id', role_id).eq('clinic_id', clinic_id).execute()
    except Exception as e:
        logger.error(f"update_role error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar rol")
    return {"message": "Rol actualizado"}


@router.delete("/clinic/roles/{role_id}")
async def delete_role(role_id: str, ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    validate_uuid(role_id, "role_id")
    role = sdb.table('clinic_roles').select('*').eq('id', role_id).eq('clinic_id', clinic_id).maybe_single().execute()
    rdata = getattr(role, 'data', None)
    if not rdata:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if rdata['is_system']:
        raise HTTPException(status_code=400, detail="Los roles del sistema no se pueden eliminar")
    cnt = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic_id).eq('role_key', rdata['key']).eq('is_active', True).execute()
    if (cnt.count or 0) > 0:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar: {cnt.count} miembro(s) usan este rol. Reasígnalos primero.")
    try:
        sdb.table('clinic_roles').delete().eq('id', role_id).eq('clinic_id', clinic_id).execute()
    except Exception as e:
        logger.error(f"delete_role error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar rol")
    return {"message": "Rol eliminado"}


@router.put("/clinic/members/{member_id}/role")
async def assign_member_role(member_id: str, data: MemberRoleAssign, ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    validate_uuid(member_id, "member_id")
    ensure_system_roles(clinic_id)
    new_role = (data.role or "").strip()
    if not new_role:
        raise HTTPException(status_code=400, detail="Rol requerido")
    role_row = sdb.table('clinic_roles').select('key').eq('clinic_id', clinic_id).eq('key', new_role).maybe_single().execute()
    if not getattr(role_row, 'data', None):
        raise HTTPException(status_code=400, detail="Rol inválido")
    member = sdb.table('clinic_members').select('id,role,role_key').eq('id', member_id).eq('clinic_id', clinic_id).maybe_single().execute()
    mdata = getattr(member, 'data', None)
    if not mdata:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    # Never leave a clinic without an active admin
    current_effective = mdata.get('role_key') or mdata.get('role')
    if current_effective == 'clinic_admin' and new_role != 'clinic_admin':
        admins = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic_id).eq('role', 'clinic_admin').eq('is_active', True).execute()
        if (admins.count or 0) <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo")
    update = {"role_key": new_role, "updated_at": now_iso()}
    if new_role in ENUM_ROLE_VALUES:
        update["role"] = new_role
    try:
        sdb.table('clinic_members').update(update).eq('id', member_id).eq('clinic_id', clinic_id).execute()
    except Exception as e:
        logger.error(f"assign_member_role error: {e}")
        raise HTTPException(status_code=500, detail="Error al asignar rol")
    return {"message": "Rol asignado", "role": new_role}
