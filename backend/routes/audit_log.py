"""Audit log read endpoints.

- Super admin: GET /api/admin/audit-log (all events, all clinics)
- Clinic admin: GET /api/clinic/audit-log (own clinic only)

Both support filters (entity, action, actor, date range) and pagination.
The data is read directly from `audit_log` via the service_role client; RLS
is the safety net but authorization is also enforced at the FastAPI layer.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from core import sdb, require_super_admin, require_clinic_admin

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_filters(q, *, entity, action, actor_email, since, until):
    if entity:
        q = q.eq('entity', entity)
    if action:
        q = q.eq('action', action)
    if actor_email:
        q = q.ilike('actor_email', f'%{actor_email}%')
    if since:
        q = q.gte('occurred_at', since)
    if until:
        q = q.lte('occurred_at', until)
    return q


@router.get("/admin/audit-log")
async def admin_audit_log(
    clinic_id: Optional[str] = None,
    entity: Optional[str] = None,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    user=Depends(require_super_admin),
):
    """Super admin view — sees ALL events across ALL clinics."""
    try:
        limit = min(max(limit, 1), 200)
        page = max(page, 1)
        q = sdb.table('audit_log').select('*', count='exact')
        if clinic_id:
            q = q.eq('clinic_id', clinic_id)
        q = _apply_filters(q, entity=entity, action=action, actor_email=actor_email, since=since, until=until)
        offset = (page - 1) * limit
        result = q.order('occurred_at', desc=True).range(offset, offset + limit - 1).execute()
        total = result.count or 0
        return {
            "rows": result.data or [],
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
        }
    except Exception as e:
        logger.error(f"admin audit-log error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener bitácora")


@router.get("/clinic/audit-log")
async def clinic_audit_log(
    entity: Optional[str] = None,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    ctx=Depends(require_clinic_admin),
):
    """Clinic admin view — sees only their own clinic's events."""
    try:
        clinic_id = ctx["member"]["clinic_id"]
        limit = min(max(limit, 1), 200)
        page = max(page, 1)
        q = sdb.table('audit_log').select('*', count='exact').eq('clinic_id', clinic_id)
        q = _apply_filters(q, entity=entity, action=action, actor_email=actor_email, since=since, until=until)
        offset = (page - 1) * limit
        result = q.order('occurred_at', desc=True).range(offset, offset + limit - 1).execute()
        total = result.count or 0
        return {
            "rows": result.data or [],
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
        }
    except Exception as e:
        logger.error(f"clinic audit-log error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener bitácora")


@router.get("/admin/audit-log/actions")
async def admin_audit_log_actions(user=Depends(require_super_admin)):
    """Return the distinct list of action types seen so far (for UI filter dropdown)."""
    try:
        result = sdb.rpc('audit_log_distinct_actions').execute() if False else None  # noqa: F841
        # Cheaper: select distinct via PostgREST? Not supported; do a window via raw SQL
        from core import run_sql
        rows = run_sql("SELECT DISTINCT action FROM audit_log ORDER BY action", None, fetch=True) or []
        return {"actions": [r['action'] for r in rows]}
    except Exception as e:
        logger.error(f"audit-log actions error: {e}")
        return {"actions": []}
