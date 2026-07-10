"""Monthly maintenance routine.

Runs the housekeeping tasks that keep the DB fast and clean at scale:

  1. `ensure_audit_partitions(6)` — pre-create the next 6 months of partitions.
  2. DROP `audit_log_YYYY_MM` partitions older than 12 months (archive-first
     policy left to the operator — we don't move to cold storage automatically).
  3. VACUUM ANALYZE on the top-10 largest tables (bloat + planner stats).
  4. DELETE from `rate_limit_events` older than 1 hour.
  5. DELETE completed `export_jobs` older than 30 days + their Storage files.

Wired to run:
  - Automatically on the 1st of each month at 03:00 UTC (via APScheduler).
  - Manually via `POST /api/admin/maintenance/monthly` (idempotent).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from core import sdb, supabase_admin, run_sql

logger = logging.getLogger(__name__)

# Tables to VACUUM ANALYZE — biggest / most write-heavy first
_VACUUM_TABLES = [
    "audit_log", "appointments", "medical_records", "prescriptions",
    "sales", "sale_items", "payments", "accounts_receivable",
    "inventory_movements", "expenses",
]


def _drop_old_audit_partitions() -> list[str]:
    """DROP audit_log_YYYY_MM partitions older than 12 months.

    Skips `audit_log_pre_2026` (the catch-all). Returns names dropped.
    """
    dropped: list[str] = []
    try:
        # Find partitions whose upper bound is > 12 months ago
        rows = run_sql(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_inherits i ON i.inhrelid = c.oid
            JOIN pg_class p ON p.oid = i.inhparent
            WHERE n.nspname = 'public'
              AND p.relname = 'audit_log'
              AND c.relname ~ '^audit_log_[0-9]{4}_[0-9]{2}$'
            ORDER BY c.relname
            """,
            None,
            fetch=True,
        ) or []
        cutoff = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=380)).date()
        for r in rows:
            name = r["relname"]
            # Extract YYYY_MM from name
            try:
                y = int(name.split("_")[-2])
                m = int(name.split("_")[-1])
                part_start = datetime(y, m, 1).date()
                if part_start < cutoff:
                    run_sql(f"DROP TABLE IF EXISTS public.{name}")
                    dropped.append(name)
            except Exception as e:
                logger.warning(f"skip partition {name}: {e}")
    except Exception as e:
        logger.warning(f"drop_old_audit_partitions failed: {e}")
    return dropped


def _vacuum_analyze() -> dict[str, str]:
    """Run VACUUM (ANALYZE) on the hot tables. Requires autocommit which
    `run_sql` provides. Non-blocking-ish — Postgres does it concurrently."""
    result = {}
    for t in _VACUUM_TABLES:
        try:
            # VACUUM can't run inside a transaction — run_sql uses autocommit.
            run_sql(f"VACUUM (ANALYZE) public.{t}")
            result[t] = "ok"
        except Exception as e:
            result[t] = f"err: {str(e)[:120]}"
    return result


def _cleanup_rate_limits() -> int:
    """Delete rate_limit_events older than 1 hour."""
    try:
        run_sql("DELETE FROM rate_limit_events WHERE occurred_at < NOW() - INTERVAL '1 hour'")
        r = run_sql("SELECT count(*) as n FROM rate_limit_events", None, fetch=True)
        return r[0]["n"] if r else -1
    except Exception as e:
        logger.warning(f"cleanup rate_limits failed: {e}")
        return -1


def _cleanup_export_jobs() -> dict[str, int]:
    """DELETE export_jobs older than 30 days + their Storage files."""
    deleted = 0
    files_deleted = 0
    try:
        old = sdb.table('export_jobs').select('id,file_path').lt(
            'created_at', (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        ).execute()
        for job in old.data or []:
            fp = job.get('file_path')
            if fp:
                try:
                    supabase_admin.storage.from_('patient-files').remove([fp])
                    files_deleted += 1
                except Exception as e:
                    logger.warning(f"remove file {fp}: {e}")
            sdb.table('export_jobs').delete().eq('id', job['id']).execute()
            deleted += 1
    except Exception as e:
        logger.warning(f"cleanup export_jobs failed: {e}")
    return {"rows_deleted": deleted, "files_deleted": files_deleted}


def run_monthly_maintenance() -> dict[str, Any]:
    """Execute all maintenance tasks. Idempotent."""
    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {"started_at": started.isoformat()}

    # 1) Ensure future partitions
    try:
        r = run_sql("SELECT public.ensure_audit_partitions(6) as n", None, fetch=True)
        report["partitions_created"] = r[0]["n"] if r else 0
    except Exception as e:
        report["partitions_created_error"] = str(e)[:200]

    # 2) Drop old partitions
    report["partitions_dropped"] = _drop_old_audit_partitions()

    # 3) VACUUM ANALYZE hot tables
    report["vacuum"] = _vacuum_analyze()

    # 4) Cleanup rate_limit_events
    report["rate_limit_remaining"] = _cleanup_rate_limits()

    # 5) Cleanup old export_jobs
    report["export_jobs_cleanup"] = _cleanup_export_jobs()

    finished = datetime.now(timezone.utc)
    report["finished_at"] = finished.isoformat()
    report["duration_seconds"] = (finished - started).total_seconds()
    logger.info(f"Monthly maintenance done: {report}")
    return report
