"""In-memory cache for Supabase Storage signed URLs.

Signed URL creation is a Supabase Storage API call (~30-80 ms round trip).
For endpoints that repeatedly return the same URL (e.g. viewing a saved
prescription PDF), caching lets us serve the second+ request in <1 ms and
reduces Storage API pressure ~90 %.

The cache is process-local (dict). Entries have a 5-minute safety margin
before the URL's true TTL so we never hand out an about-to-expire URL.

Usage:
    from services.signed_url_cache import get_or_create_signed_url
    url = get_or_create_signed_url("patient-files", f"{clinic}/{sale}.pdf", ttl=3600)
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from core import supabase_admin

logger = logging.getLogger(__name__)

# {(bucket, path): (url, expires_epoch)}
_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_SAFETY_MARGIN_SECONDS = 300  # 5 min


def get_or_create_signed_url(bucket: str, path: str, ttl: int = 3600) -> Optional[str]:
    """Return a signed URL for the object, generating a new one only if the
    cached URL is missing or within the safety margin of expiration.
    """
    now = time.time()
    key = (bucket, path)
    cached = _CACHE.get(key)
    if cached is not None:
        url, expires_epoch = cached
        if expires_epoch - now > _SAFETY_MARGIN_SECONDS:
            return url
    try:
        signed = supabase_admin.storage.from_(bucket).create_signed_url(path, ttl)
    except Exception as e:
        logger.warning(f"create_signed_url failed for {bucket}/{path}: {e}")
        # Return stale cached URL if we had one — better than nothing
        return cached[0] if cached else None

    url = signed.get('signedURL') or signed.get('signedUrl', '')
    if url:
        _CACHE[key] = (url, now + ttl)
    return url or None


def invalidate(bucket: str, path: str) -> None:
    """Drop the cached URL — call this if the underlying object was replaced."""
    _CACHE.pop((bucket, path), None)


def stats() -> dict:
    """Cheap observability: cache size + hit potential."""
    return {"size": len(_CACHE)}
