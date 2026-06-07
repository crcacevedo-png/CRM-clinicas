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


import os
from ipaddress import ip_address, ip_network

# Trusted proxy CIDRs. Only headers coming from these networks are trusted.
# Configurable via TRUSTED_PROXY_CIDRS env (comma-separated). Defaults to
# private/cloud-internal ranges used by the Emergent K8s ingress.
_DEFAULT_TRUSTED_CIDRS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"
_TRUSTED_CIDRS = []
for _c in (os.environ.get('TRUSTED_PROXY_CIDRS') or _DEFAULT_TRUSTED_CIDRS).split(','):
    _c = _c.strip()
    if _c:
        try:
            _TRUSTED_CIDRS.append(ip_network(_c, strict=False))
        except ValueError:
            pass


def _is_from_trusted_proxy(peer_ip: str | None) -> bool:
    if not peer_ip:
        return False
    try:
        addr = ip_address(peer_ip)
        return any(addr in net for net in _TRUSTED_CIDRS)
    except ValueError:
        return False


def _ip_from_request(req: Optional[Request]) -> Optional[str]:
    """Return the real client IP.

    We only honor X-Forwarded-For / X-Real-IP when the request peer (direct
    TCP source) is a trusted proxy (typically the K8s ingress). For untrusted
    peers we use the raw connection IP. This defeats spoofing attempts where
    an attacker reaches the backend directly and sets fake XFF headers.
    """
    if req is None:
        return None
    try:
        peer = req.client.host if req.client else None
    except Exception:
        peer = None

    if _is_from_trusted_proxy(peer):
        fwd = req.headers.get('x-forwarded-for') or req.headers.get('x-real-ip')
        if fwd:
            # Take the leftmost IP (original client) from the comma list.
            first = fwd.split(',')[0].strip()
            if first:
                return first
    return peer


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
