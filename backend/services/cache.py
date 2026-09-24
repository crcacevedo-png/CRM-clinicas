"""Shared cache layer with a Redis backend (production) and an in-process
TTL fallback (dev/preview). Set REDIS_URL to enable Redis so the cache is
shared across all Uvicorn/Gunicorn workers — essential when scaling to many
workers so hot lookups (features, role modules, catalogs) hit the DB once
cluster-wide instead of once per worker.

Values are JSON-serializable. `None` means "miss".
"""
import os
import json
import time
import logging

logger = logging.getLogger("clinic_crm")

_redis = None            # None = not yet resolved; False = unavailable; client = ready
_local: dict = {}        # key -> (expires_monotonic, value)  (fallback)


def _get_redis():
    global _redis
    if _redis is None:
        url = os.environ.get("REDIS_URL")
        if not url:
            _redis = False
        else:
            try:
                import redis
                client = redis.from_url(
                    url, decode_responses=True,
                    socket_timeout=1.0, socket_connect_timeout=1.0,
                    health_check_interval=30,
                )
                client.ping()
                _redis = client
                logger.info("Cache backend: Redis")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}); using in-process cache")
                _redis = False
    return _redis or None


def cache_get(key):
    r = _get_redis()
    if r is not None:
        try:
            v = r.get(key)
            return json.loads(v) if v is not None else None
        except Exception:
            return None
    v = _local.get(key)
    if v and v[0] > time.monotonic():
        return v[1]
    if v:
        _local.pop(key, None)
    return None


def cache_set(key, value, ttl: float):
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, max(1, int(ttl)), json.dumps(value))
            return
        except Exception:
            pass
    _local[key] = (time.monotonic() + ttl, value)


def cache_delete_contains(substr: str):
    """Invalidate every key containing `substr` (e.g. a clinic_id)."""
    r = _get_redis()
    if r is not None:
        try:
            for k in r.scan_iter(match=f"*{substr}*", count=500):
                r.delete(k)
            return
        except Exception:
            pass
    for k in [k for k in _local if substr in k]:
        _local.pop(k, None)
