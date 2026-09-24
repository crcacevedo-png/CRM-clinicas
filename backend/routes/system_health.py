"""System health & maintenance endpoints for super admin.

- GET  /api/admin/system/health          — full health metrics dashboard
- POST /api/admin/maintenance/monthly    — trigger maintenance manually
- GET  /api/admin/maintenance/last-run   — most recent maintenance report (audit_log)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends

from core import sdb, supabase_admin, run_sql, require_super_admin, logger

router = APIRouter()


def _safe(fn, default=None, label=""):
    """Run a metric collector, log & swallow errors, return default on fail."""
    try:
        return fn()
    except Exception as e:
        logger.warning(f"health metric {label} failed: {e}")
        return default


def _db_size_metrics() -> dict:
    rows = run_sql(
        """
        SELECT c.relname AS name,
               pg_total_relation_size(c.oid) AS bytes,
               COALESCE(s.n_live_tup, 0) AS rows
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE c.relkind = 'r' AND n.nspname = 'public'
        ORDER BY pg_total_relation_size(c.oid) DESC
        LIMIT 15
        """,
        None,
        fetch=True,
    ) or []
    total = run_sql(
        "SELECT pg_database_size(current_database()) AS bytes",
        None,
        fetch=True,
    )
    total_bytes = total[0]["bytes"] if total else 0
    # Supabase Pro DB limit is 8 GB
    PRO_LIMIT_BYTES = 8 * 1024 * 1024 * 1024
    return {
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 2),
        "pro_limit_bytes": PRO_LIMIT_BYTES,
        "pct_of_pro_limit": round(total_bytes * 100.0 / PRO_LIMIT_BYTES, 2),
        "top_tables": [
            {"name": r["name"], "bytes": r["bytes"], "mb": round(r["bytes"] / 1024 / 1024, 2), "rows": r["rows"]}
            for r in rows
        ],
    }


def _row_counts() -> dict:
    counts = {}
    for tbl in ("clinics", "clinic_members", "patients", "appointments",
                "medical_records", "prescriptions", "sales", "audit_log",
                "export_jobs", "rate_limit_events"):
        try:
            r = run_sql(f"SELECT count(*) AS n FROM {tbl}", None, fetch=True)
            counts[tbl] = r[0]["n"] if r else 0
        except Exception:
            counts[tbl] = -1
    return counts


def _active_users_metrics() -> dict:
    """Login events last 24h & 7d based on audit_log."""
    daily = run_sql(
        """
        SELECT count(DISTINCT actor_user_id) AS n
        FROM audit_log
        WHERE action = 'login_success'
          AND occurred_at > NOW() - INTERVAL '24 hours'
        """,
        None,
        fetch=True,
    )
    weekly = run_sql(
        """
        SELECT count(DISTINCT actor_user_id) AS n
        FROM audit_log
        WHERE action = 'login_success'
          AND occurred_at > NOW() - INTERVAL '7 days'
        """,
        None,
        fetch=True,
    )
    monthly = run_sql(
        """
        SELECT count(DISTINCT actor_user_id) AS n
        FROM audit_log
        WHERE action = 'login_success'
          AND occurred_at > NOW() - INTERVAL '30 days'
        """,
        None,
        fetch=True,
    )
    return {
        "dau": daily[0]["n"] if daily else 0,
        "wau": weekly[0]["n"] if weekly else 0,
        "mau": monthly[0]["n"] if monthly else 0,
    }


def _auth_health() -> dict:
    """Login attempts, failures, rate-limit hits — indicators of brute-force attacks."""
    res = run_sql(
        """
        SELECT
            count(*) FILTER (WHERE action = 'login_success' AND occurred_at > NOW() - INTERVAL '1 hour') AS success_1h,
            count(*) FILTER (WHERE action = 'login_success' AND occurred_at > NOW() - INTERVAL '24 hours') AS success_24h,
            count(*) FILTER (WHERE action = 'login_failed'  AND occurred_at > NOW() - INTERVAL '1 hour') AS failed_1h,
            count(*) FILTER (WHERE action = 'login_failed'  AND occurred_at > NOW() - INTERVAL '24 hours') AS failed_24h,
            count(*) FILTER (WHERE action = 'login_rate_limited' AND occurred_at > NOW() - INTERVAL '24 hours') AS rate_limited_24h,
            count(*) FILTER (WHERE action = 'login_denied'  AND occurred_at > NOW() - INTERVAL '24 hours') AS denied_24h,
            count(DISTINCT ip_address) FILTER (WHERE action IN ('login_success','login_failed') AND occurred_at > NOW() - INTERVAL '24 hours') AS unique_ips_24h
        FROM audit_log
        """,
        None,
        fetch=True,
    )
    row = res[0] if res else {}
    failure_ratio = 0.0
    total_24h = (row.get("success_24h", 0) or 0) + (row.get("failed_24h", 0) or 0)
    if total_24h > 0:
        failure_ratio = round((row.get("failed_24h", 0) or 0) * 100.0 / total_24h, 1)
    return {**{k: v or 0 for k, v in row.items()}, "failure_ratio_pct": failure_ratio}


def _jobs_health() -> dict:
    res = run_sql(
        """
        SELECT
            count(*) FILTER (WHERE status = 'queued') AS queued,
            count(*) FILTER (WHERE status = 'running') AS running,
            count(*) FILTER (WHERE status = 'done'   AND created_at > NOW() - INTERVAL '30 days') AS done_30d,
            count(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '30 days') AS failed_30d,
            avg(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (WHERE status='done' AND started_at IS NOT NULL) AS avg_seconds
        FROM export_jobs
        """,
        None,
        fetch=True,
    )
    row = res[0] if res else {}
    return {
        "queued": row.get("queued", 0) or 0,
        "running": row.get("running", 0) or 0,
        "done_last_30d": row.get("done_30d", 0) or 0,
        "failed_last_30d": row.get("failed_30d", 0) or 0,
        "avg_duration_seconds": round(float(row.get("avg_seconds") or 0), 2),
    }


def _locks_health() -> dict:
    res = run_sql(
        """
        SELECT lock_name, holder, acquired_at, expires_at,
               (expires_at < NOW()) AS is_stale
        FROM distributed_locks
        """,
        None,
        fetch=True,
    ) or []
    return {"active_locks": [
        {**r, "acquired_at": r["acquired_at"].isoformat() if r.get("acquired_at") else None,
              "expires_at":  r["expires_at"].isoformat()  if r.get("expires_at")  else None}
        for r in res
    ]}


def _partitions_health() -> dict:
    res = run_sql(
        """
        SELECT c.relname AS name,
               COALESCE(s.n_live_tup, 0) AS rows,
               pg_total_relation_size(c.oid) AS bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_inherits i ON i.inhrelid = c.oid
        JOIN pg_class p ON p.oid = i.inhparent
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE n.nspname = 'public' AND p.relname = 'audit_log'
        ORDER BY c.relname
        """,
        None,
        fetch=True,
    ) or []
    return {"audit_log_partitions": [
        {"name": r["name"], "rows": r["rows"], "bytes": r["bytes"], "mb": round(r["bytes"] / 1024 / 1024, 2)}
        for r in res
    ]}


def _storage_health() -> dict:
    """Storage usage total & per-clinic (top 10)."""
    try:
        # Attachments table gives us file-level stats we control (excludes raw
        # Storage-only objects like exports/*.zip). Good enough for order-of-magnitude.
        rows = run_sql(
            """
            SELECT clinic_id, count(*) AS files, COALESCE(sum(file_size), 0) AS bytes
            FROM attachments
            WHERE clinic_id IS NOT NULL
            GROUP BY clinic_id
            ORDER BY bytes DESC
            LIMIT 10
            """,
            None,
            fetch=True,
        ) or []
        total = run_sql(
            "SELECT count(*) as files, COALESCE(sum(file_size), 0) AS bytes FROM attachments",
            None,
            fetch=True,
        )
        total_row = total[0] if total else {"files": 0, "bytes": 0}
        # Supabase Pro Storage limit is 100 GB
        PRO_STORAGE_LIMIT = 100 * 1024 * 1024 * 1024
        return {
            "attachments_total_bytes": total_row["bytes"] or 0,
            "attachments_total_gb": round((total_row["bytes"] or 0) / 1024 / 1024 / 1024, 3),
            "attachments_total_files": total_row["files"] or 0,
            "pro_limit_gb": 100,
            "pct_of_pro_limit": round((total_row["bytes"] or 0) * 100.0 / PRO_STORAGE_LIMIT, 2),
            "top_clinics": [
                {"clinic_id": r["clinic_id"], "files": r["files"], "bytes": r["bytes"], "mb": round(r["bytes"] / 1024 / 1024, 2)}
                for r in rows
            ],
        }
    except Exception as e:
        logger.warning(f"storage_health failed: {e}")
        return {}


def _connections_health() -> dict:
    res = run_sql(
        """
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE state = 'active') AS active,
            count(*) FILTER (WHERE state = 'idle') AS idle
        FROM pg_stat_activity
        WHERE datname = current_database()
        """,
        None,
        fetch=True,
    )
    row = res[0] if res else {}
    # Supabase Pro pooler = 200 connections default
    return {
        "total": row.get("total", 0) or 0,
        "active": row.get("active", 0) or 0,
        "idle": row.get("idle", 0) or 0,
        "pooler_limit": 200,
    }


def _reminder_scheduler_status() -> dict:
    """Last time the reminder scheduler acquired the lock (proxy for last tick)."""
    res = run_sql(
        """
        SELECT acquired_at, expires_at, holder
        FROM distributed_locks
        WHERE lock_name = 'reminder_tick'
        """,
        None,
        fetch=True,
    )
    if res:
        r = res[0]
        return {
            "last_acquired_at": r["acquired_at"].isoformat() if r.get("acquired_at") else None,
            "last_holder": r.get("holder"),
        }
    # If no active lock, try to infer from most recent reminder sent
    res2 = run_sql(
        "SELECT max(reminder_email_sent_at) AS last FROM appointments WHERE reminder_email_sent_at IS NOT NULL",
        None,
        fetch=True,
    )
    return {"last_reminder_sent_at": res2[0]["last"].isoformat() if res2 and res2[0]["last"] else None}


def _slow_queries() -> dict:
    """Slowest queries (if pg_stat_statements is available)."""
    try:
        rows = run_sql(
            """
            SELECT calls, mean_exec_time, max_exec_time,
                   left(query, 200) AS query
            FROM pg_stat_statements
            WHERE calls > 5 AND query NOT LIKE '%pg_stat_statements%'
            ORDER BY mean_exec_time DESC
            LIMIT 10
            """,
            None,
            fetch=True,
        )
        return {"available": True, "rows": [
            {
                "calls": r["calls"],
                "mean_ms": round(float(r["mean_exec_time"]), 2),
                "max_ms": round(float(r["max_exec_time"]), 2),
                "query": r["query"],
            }
            for r in (rows or [])
        ]}
    except Exception as e:
        return {"available": False, "reason": str(e)[:200]}


@router.get("/admin/system/health")
async def system_health(user=Depends(require_super_admin)):
    """Comprehensive health snapshot for the super admin's Salud dashboard.

    Aggregates 9 metric groups. Every group is wrapped in `_safe(...)` so a
    single failing collector never breaks the whole endpoint.
    """
    started = datetime.now(timezone.utc)
    payload = {
        "generated_at": started.isoformat(),
        "db_size":       _safe(_db_size_metrics,    {}, "db_size"),
        "row_counts":    _safe(_row_counts,         {}, "row_counts"),
        "active_users":  _safe(_active_users_metrics, {}, "active_users"),
        "auth":          _safe(_auth_health,        {}, "auth"),
        "jobs":          _safe(_jobs_health,        {}, "jobs"),
        "locks":         _safe(_locks_health,       {}, "locks"),
        "partitions":    _safe(_partitions_health,  {}, "partitions"),
        "storage":       _safe(_storage_health,     {}, "storage"),
        "connections":   _safe(_connections_health, {}, "connections"),
        "reminders":     _safe(_reminder_scheduler_status, {}, "reminders"),
        "slow_queries":  _safe(_slow_queries,       {}, "slow_queries"),
    }
    payload["duration_ms"] = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1)
    return payload


@router.post("/admin/maintenance/monthly")
async def run_maintenance_manually(user=Depends(require_super_admin)):
    """Manually trigger the monthly maintenance job. Idempotent — safe anytime."""
    from services.monthly_maintenance import run_monthly_maintenance
    return run_monthly_maintenance()


@router.get("/admin/maintenance/archives")
async def list_audit_archives(user=Depends(require_super_admin)):
    """List archived audit_log partitions in Storage.

    Each entry: {name, size, updated_at, signed_url (24h)}. Used by super admin
    to download cold-storage archives for compliance or forensic review.
    """
    try:
        files = supabase_admin.storage.from_('patient-files').list(
            '_archives/audit_log',
            {"limit": 200, "sortBy": {"column": "name", "order": "desc"}},
        ) or []
    except Exception as e:
        logger.warning(f"list archives failed: {e}")
        return {"archives": [], "error": str(e)[:200]}

    out = []
    for f in files:
        name = f.get('name')
        if not name or not name.endswith('.jsonl.gz'):
            continue
        path = f"_archives/audit_log/{name}"
        try:
            signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 86400)
            url = signed.get('signedURL') or signed.get('signed_url')
        except Exception:
            url = None
        meta = f.get('metadata') or {}
        out.append({
            "name": name,
            "path": path,
            "size": meta.get('size'),
            "updated_at": f.get('updated_at') or f.get('created_at'),
            "signed_url": url,
        })
    return {"archives": out, "count": len(out)}


# ============== RUNTIME CAPACITY / SELF-BENCHMARK ==============
import os as _os
import time as _time
import concurrent.futures as _futures

_PROC_START = _time.time()


def _cgroup_memory():
    """Return (used_bytes, limit_bytes) from cgroup v2/v1 if available."""
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            raw = f.read().strip()
        limit = None if raw == "max" else int(raw)
        with open("/sys/fs/cgroup/memory.current") as f:
            used = int(f.read().strip())
        return used, limit
    except Exception:
        try:
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                limit = int(f.read().strip())
            with open("/sys/fs/cgroup/memory/memory.usage_in_bytes") as f:
                used = int(f.read().strip())
            return used, (None if limit > 10 ** 15 else limit)
        except Exception:
            return None, None


def _capacity_snapshot() -> dict:
    out = {}
    # CPU / memory
    try:
        import psutil
        out["cpu"] = {
            "count": psutil.cpu_count(),
            "percent": psutil.cpu_percent(interval=0.15),
            "load_avg": [round(x, 2) for x in _os.getloadavg()] if hasattr(_os, "getloadavg") else None,
        }
        vm = psutil.virtual_memory()
        used, limit = _cgroup_memory()
        mem_total = limit or vm.total
        mem_used = used if used is not None else vm.used
        out["memory"] = {
            "total_mb": round(mem_total / 1024 / 1024),
            "used_mb": round(mem_used / 1024 / 1024),
            "percent": round(mem_used / mem_total * 100, 1) if mem_total else None,
        }
        p = psutil.Process()
        out["process"] = {
            "pid": p.pid,
            "rss_mb": round(p.memory_info().rss / 1024 / 1024, 1),
            "threads": p.num_threads(),
            "uptime_s": round(_time.time() - _PROC_START),
        }
    except Exception as e:
        out["resources_error"] = str(e)
    # Config
    out["config"] = {
        "workers_env": _os.environ.get("WEB_CONCURRENCY") or _os.environ.get("GUNICORN_WORKERS") or "unknown (preview=1)",
        "threadpool_tokens": int(_os.environ.get("THREADPOOL_TOKENS", "128")),
        "supabase_max_connections": int(_os.environ.get("SUPABASE_MAX_CONNECTIONS", "200")),
    }
    # Redis
    try:
        from services.cache import _get_redis
        r = _get_redis()
        if r is not None:
            t0 = _time.perf_counter()
            r.ping()
            out["redis"] = {"enabled": True, "ping_ms": round((_time.perf_counter() - t0) * 1000, 1)}
        else:
            out["redis"] = {"enabled": False, "note": "REDIS_URL no configurada — usando caché en memoria"}
    except Exception as e:
        out["redis"] = {"enabled": False, "error": str(e)}
    # DB API (PostgREST) latency
    try:
        t0 = _time.perf_counter()
        sdb.table("clinics").select("id").limit(1).execute()
        out["db_api"] = {"ping_ms": round((_time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        out["db_api"] = {"error": str(e)}
    return out


def _one_light_query():
    t0 = _time.perf_counter()
    try:
        sdb.table("clinics").select("id").limit(1).execute()
        return (_time.perf_counter() - t0) * 1000, True
    except Exception:
        return (_time.perf_counter() - t0) * 1000, False


def _run_benchmark(concurrency: int, total_ops: int) -> dict:
    lat = []
    ok = 0
    wall0 = _time.perf_counter()
    with _futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        for ms, success in ex.map(lambda _i: _one_light_query(), range(total_ops)):
            lat.append(ms)
            ok += 1 if success else 0
    wall = _time.perf_counter() - wall0
    lat.sort()
    n = len(lat)
    def pct(p):
        return round(lat[min(n - 1, int(n * p))], 1) if n else None
    thrpt = round(total_ops / wall, 1) if wall > 0 else None
    # Rough capacity estimate: assume an active user issues ~0.25 requests/sec at peak.
    est_users = int(thrpt / 0.25) if thrpt else None
    return {
        "concurrency": concurrency,
        "total_ops": total_ops,
        "ok": ok,
        "errors": total_ops - ok,
        "wall_s": round(wall, 2),
        "throughput_ops_s": thrpt,
        "latency_ms": {"p50": pct(0.50), "p95": pct(0.95), "max": pct(1.0)},
        "estimated_active_users": est_users,
        "estimate_note": "Estimación aprox. asumiendo ~0.25 req/s por usuario activo en pico. Con más workers en producción escala casi lineal.",
    }


@router.get("/admin/system/capacity")
async def system_capacity(user=Depends(require_super_admin)):
    """Live runtime capacity snapshot (CPU, memoria, proceso, Redis, latencia BD)."""
    from starlette.concurrency import run_in_threadpool
    snap = await run_in_threadpool(_capacity_snapshot)
    # Threadpool utilization (must read on the event loop)
    try:
        import anyio.to_thread
        lim = anyio.to_thread.current_default_thread_limiter()
        snap["threadpool"] = {
            "capacity": lim.total_tokens,
            "in_use": lim.borrowed_tokens,
        }
    except Exception as e:
        snap["threadpool"] = {"error": str(e)}
    snap["generated_at"] = datetime.now(timezone.utc).isoformat()
    return snap


@router.post("/admin/system/capacity/benchmark")
async def system_capacity_benchmark(concurrency: int = 20, user=Depends(require_super_admin)):
    """Run a controlled internal load test (parallel lightweight DB queries) and
    report throughput/latency. `concurrency` is capped at 400 for safety."""
    from starlette.concurrency import run_in_threadpool
    concurrency = max(1, min(int(concurrency), 400))
    total_ops = concurrency * 3  # a few rounds for a stable measurement
    result = await run_in_threadpool(_run_benchmark, concurrency, total_ops)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result
