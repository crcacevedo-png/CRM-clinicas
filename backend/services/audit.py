"""Audit log helper.

`log_audit(...)` writes an append-only event to `public.audit_log` and never
raises (failures only log a warning). Use it for security-relevant actions:
login, password resets, plan/role changes, deletions, sensitive edits.

Designed to be cheap: synchronous Supabase REST insert (~50ms). For very
hot paths, wrap in `asyncio.create_task(log_audit(...))` from an async ctx.
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import Request

from core import sdb, now_iso

logger = logging.getLogger(__name__)


def _ip_from_request(req: Optional[Request]) -> Optional[str]:
    if req is None:
        return None
    # Honor common proxy headers
    fwd = req.headers.get('x-forwarded-for') or req.headers.get('x-real-ip')
    if fwd:
        return fwd.split(',')[0].strip()
    try:
        return req.client.host if req.client else None
    except Exception:
        return None


def _ua_from_request(req: Optional[Request]) -> Optional[str]:
    if req is None:
        return None
    ua = req.headers.get('user-agent')
    return ua[:500] if ua else None


async def log_audit(
    *,
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    clinic_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Append one row to audit_log. Never raises."""
    try:
        row = {
            "id": str(uuid.uuid4()),
            "occurred_at": now_iso(),
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "clinic_id": clinic_id,
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": _ip_from_request(request),
            "user_agent": _ua_from_request(request),
            "meta": meta,
        }
        # Strip None to keep the JSON compact
        row = {k: v for k, v in row.items() if v is not None}
        sdb.table('audit_log').insert(row).execute()
    except Exception as e:
        logger.warning(f"audit_log insert failed action={action!r} entity={entity!r}: {e}")


def actor_from_ctx(ctx: dict) -> dict:
    """Extract actor fields from a `require_clinic_member` ctx dict.

    ctx shape: {"auth_user": <gotrue user>, "member": {id, clinic_id, role, ...}}
    """
    m = (ctx or {}).get('member') or {}
    user = (ctx or {}).get('auth_user')
    user_id = getattr(user, 'id', None) if user else None
    user_email = getattr(user, 'email', None) if user else None
    return {
        "actor_user_id": user_id,
        "actor_email": user_email,
        "actor_role": m.get('role'),
        "clinic_id": m.get('clinic_id'),
    }


def actor_from_super_admin(user) -> dict:
    """Extract actor fields from `require_super_admin` user payload."""
    if user is None:
        return {}
    if isinstance(user, dict):
        return {
            "actor_user_id": user.get('id') or user.get('user_id'),
            "actor_email": user.get('email'),
            "actor_role": "super_admin",
        }
    return {
        "actor_user_id": getattr(user, 'id', None),
        "actor_email": getattr(user, 'email', None),
        "actor_role": "super_admin",
    }
