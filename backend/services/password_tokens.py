"""Single-use, time-limited password set/reset tokens.

Used by:
  - Forgot password flow (purpose='reset', 60 min TTL)
  - Welcome / set-password flow when a clinic is created (purpose='welcome', 72h TTL)

Tokens are random (secrets.token_urlsafe); only their SHA-256 hash is stored.
Redemption sets `used_at` so a link works exactly once.
"""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

from core import run_sql


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_reset_token(user_id: str, email: str, purpose: str = "reset", ttl_minutes: int = 60) -> str:
    """Create a token, invalidating any previous unused token of the same purpose."""
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    run_sql(
        "UPDATE public.password_reset_tokens SET used_at = NOW() "
        "WHERE user_id = %s AND purpose = %s AND used_at IS NULL",
        (user_id, purpose),
    )
    run_sql(
        "INSERT INTO public.password_reset_tokens (user_id, email, token_hash, purpose, expires_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, email, _hash(raw), purpose, expires.isoformat()),
    )
    return raw


def peek_token(raw: str) -> dict | None:
    """Return the token row if valid (exists, unused, not expired), else None."""
    if not raw:
        return None
    rows = run_sql(
        "SELECT id, user_id, email, purpose, expires_at, used_at "
        "FROM public.password_reset_tokens WHERE token_hash = %s",
        (_hash(raw),),
        fetch=True,
    )
    if not rows:
        return None
    r = rows[0]
    if r.get("used_at") is not None:
        return None
    exp = r.get("expires_at")
    if exp and exp < datetime.now(timezone.utc):
        return None
    return r


def mark_token_used(token_id: str) -> None:
    run_sql(
        "UPDATE public.password_reset_tokens SET used_at = NOW() WHERE id = %s AND used_at IS NULL",
        (token_id,),
    )
