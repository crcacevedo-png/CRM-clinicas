"""Agenda blocks — block a doctor's agenda (all branches) or a whole branch's
agenda (all doctors) for a time range. Appointments cannot be scheduled/moved
into a blocked range. Allowed for receptionist / doctor / clinic_admin.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()

from core import sdb, require_clinic_member, now_iso, logger, validate_uuid, assert_doctor_in_clinic

AGENDA_BLOCK_ROLES = ["receptionist", "doctor", "clinic_admin"]


def require_agenda_block_role(ctx):
    role = ctx["member"].get("role", "")
    if role not in AGENDA_BLOCK_ROLES:
        raise HTTPException(status_code=403, detail="Solo recepción, médicos y administradores pueden bloquear la agenda")
    return ctx


class AgendaBlockCreate(BaseModel):
    scope: str                        # 'doctor' | 'branch'
    doctor_id: Optional[str] = None
    branch_id: Optional[str] = None
    starts_at: str
    ends_at: str
    all_day: bool = False
    label: Optional[str] = None


def check_agenda_block_conflict(clinic_id: str, doctor_id: Optional[str], branch_id: Optional[str],
                                starts_iso: str, ends_iso: str) -> Optional[dict]:
    """Return the first agenda_block that conflicts with [starts, ends) for the
    given doctor/branch, or None. A doctor-scope block applies to ALL branches;
    a branch-scope block applies to ALL doctors at that branch.
    """
    try:
        blocks = (sdb.table('agenda_blocks').select('*')
                  .eq('clinic_id', clinic_id)
                  .lt('starts_at', ends_iso)
                  .gt('ends_at', starts_iso)
                  .execute().data) or []
    except Exception as e:
        logger.warning(f"check_agenda_block_conflict query failed: {e}")
        return None
    for b in blocks:
        if b.get('scope') == 'doctor' and doctor_id and b.get('doctor_id') == doctor_id:
            return b
        if b.get('scope') == 'branch' and branch_id and b.get('branch_id') == branch_id:
            return b
    return None


@router.post("/clinic/agenda-blocks")
async def create_agenda_block(data: AgendaBlockCreate, ctx=Depends(require_clinic_member)):
    require_agenda_block_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]

    if data.scope not in ("doctor", "branch"):
        raise HTTPException(status_code=400, detail="Alcance inválido (doctor o branch)")

    try:
        s = datetime.fromisoformat(data.starts_at.replace('Z', '+00:00'))
        e = datetime.fromisoformat(data.ends_at.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Fechas inválidas")
    if e <= s:
        raise HTTPException(status_code=400, detail="La hora de fin debe ser posterior a la de inicio")

    doctor_id = None
    branch_id = None
    if data.scope == "doctor":
        if not data.doctor_id:
            raise HTTPException(status_code=400, detail="Debe seleccionar un médico")
        assert_doctor_in_clinic(data.doctor_id, clinic_id)
        doctor_id = data.doctor_id
    else:  # branch
        if not data.branch_id:
            raise HTTPException(status_code=400, detail="Debe seleccionar una sucursal")
        br = sdb.table('branches').select('id').eq('id', data.branch_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not getattr(br, 'data', None):
            raise HTTPException(status_code=400, detail="Sucursal inválida")
        branch_id = data.branch_id

    import uuid
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "scope": data.scope,
        "doctor_id": doctor_id,
        "branch_id": branch_id,
        "starts_at": s.isoformat(),
        "ends_at": e.isoformat(),
        "all_day": bool(data.all_day),
        "label": (data.label or "").strip() or None,
        "created_by": member["id"],
        "created_at": now,
        "updated_at": now,
    }
    try:
        sdb.table('agenda_blocks').insert(doc).execute()
    except Exception as ex:
        logger.error(f"Create agenda block error: {ex}")
        raise HTTPException(status_code=500, detail="Error al crear el bloqueo")
    return doc


@router.get("/clinic/agenda-blocks")
async def list_agenda_blocks(start_date: Optional[str] = None, end_date: Optional[str] = None,
                             doctor_id: Optional[str] = None, branch_id: Optional[str] = None,
                             ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        q = sdb.table('agenda_blocks').select('*').eq('clinic_id', clinic_id)
        # Overlap with [start_date, end_date): block.starts_at < end AND block.ends_at > start
        if end_date:
            q = q.lt('starts_at', end_date)
        if start_date:
            q = q.gt('ends_at', start_date)
        if doctor_id:
            q = q.eq('doctor_id', doctor_id)
        if branch_id:
            q = q.eq('branch_id', branch_id)
        blocks = q.order('starts_at').execute().data or []

        doctor_ids = list({b['doctor_id'] for b in blocks if b.get('doctor_id')})
        branch_ids = list({b['branch_id'] for b in blocks if b.get('branch_id')})
        dmap, bmap = {}, {}
        if doctor_ids:
            ds = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
            dmap = {d['id']: f"{d['first_name']} {d['last_name']}" for d in (ds.data or [])}
        if branch_ids:
            bs = sdb.table('branches').select('id,name').in_('id', branch_ids).execute()
            bmap = {b['id']: b['name'] for b in (bs.data or [])}
        for b in blocks:
            b['doctor_name'] = dmap.get(b.get('doctor_id'), '')
            b['branch_name'] = bmap.get(b.get('branch_id'), '')
        return blocks
    except Exception as e:
        logger.error(f"List agenda blocks error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar bloqueos")


@router.delete("/clinic/agenda-blocks/{block_id}")
async def delete_agenda_block(block_id: str, ctx=Depends(require_clinic_member)):
    require_agenda_block_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    validate_uuid(block_id, "block_id")
    try:
        existing = sdb.table('agenda_blocks').select('id').eq('id', block_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not getattr(existing, 'data', None):
            raise HTTPException(status_code=404, detail="Bloqueo no encontrado")
        sdb.table('agenda_blocks').delete().eq('id', block_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Bloqueo eliminado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete agenda block error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar el bloqueo")
