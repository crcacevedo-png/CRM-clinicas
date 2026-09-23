"""DB-backed rate limiting so counters survive across multiple backend pods.

Unlike in-memory limits (slowapi memory://), this uses `rate_limit_events`
in Postgres. It's slower per request (~5-10 ms extra) so it's applied ONLY
to authentication-critical endpoints where multi-pod correctness matters:

    - /auth/login
    - /admin/users/{id}/reset-password
    - /clinic/members/{id}/password

Everything else keeps using slowapi memory-based (single-pod correct today,
still N/pod-count correct after scaling — acceptable).

Usage as a FastAPI dependency:

    @router.post("/foo")
    async def foo(_=Depends(rate_limit("foo", limit=5, window_sec=60))):
        ...

    # or per-key when you have context:
    await check_rate_limit(f"login:{ip}", limit=5, window_sec=60)
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional
from fastapi import HTTPException, Request

from core import sdb, run_sql, client_ip

logger = logging.getLogger(__name__)


def _cleanup_old_hits(scope: str) -> None:
    """Best-effort GC of ancient rows for this scope. Bounded, fire-and-forget."""
    try:
        run_sql(
            "DELETE FROM rate_limit_events WHERE key LIKE %s AND occurred_at < NOW() - INTERVAL '1 hour'",
            (f"{scope}:%",),
        )
    except Exception:
        pass


async def check_rate_limit(key: str, *, limit: int, window_sec: int) -> None:
    """Raise HTTPException(429) if `key` exceeded `limit` in the last window_sec.

    Also inserts a hit row so this request counts toward the next check.
    """
    try:
        # Count hits in window
        rows = run_sql(
            "SELECT count(*) AS n FROM rate_limit_events WHERE key = %s AND occurred_at > NOW() - (%s || ' seconds')::interval",
            (key, str(window_sec)),
            fetch=True,
        )
        n = rows[0]["n"] if rows else 0
    except Exception as e:
        logger.warning(f"rate_limit count failed for {key}: {e}")
        return  # fail-open on DB errors

    if n >= limit:
        raise HTTPException(status_code=429, detail=f"Demasiadas solicitudes. Intenta en unos momentos.")

    # Insert this hit (doesn't matter if it races — we allow slight over-count)
    try:
        sdb.table('rate_limit_events').insert({"key": key}).execute()
    except Exception as e:
        logger.warning(f"rate_limit insert failed for {key}: {e}")


def rate_limit_key(request: Request, scope: str, extra: Optional[str] = None) -> str:
    """Build a stable key from IP + scope [+ extra qualifier like email].

    Uses trusted-proxy-aware client IP so a spoofed X-Forwarded-For from a
    direct (non-proxy) peer cannot reset the counter.
    """
    ip = client_ip(request)
    parts = [scope, ip or 'unknown']
    if extra:
        parts.append(hashlib.sha1(extra.encode()).hexdigest()[:12])
    return ":".join(parts)


def db_rate_limit(scope: str, limit: int, window_sec: int):
    """FastAPI dependency factory. Rate-limits by (scope, IP)."""
    async def _dep(request: Request):
        key = rate_limit_key(request, scope)
        await check_rate_limit(key, limit=limit, window_sec=window_sec)
        # Sample-based cleanup (~5% of calls) to keep the table small
        import random
        if random.random() < 0.05:
            _cleanup_old_hits(scope)
    return _dep
