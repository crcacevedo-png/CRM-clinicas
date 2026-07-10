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
