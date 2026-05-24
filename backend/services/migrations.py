"""Idempotent schema migrations applied at startup.

Each migration is a (id, sql) pair. We track applied migrations in a table
`schema_migrations` so each runs exactly once. Failures are logged but never
crash the app — the next startup will retry pending migrations.
"""
import logging

from core import run_sql

logger = logging.getLogger(__name__)


MIGRATIONS: list[tuple[str, str]] = [
    (
        "2026_05_24_appointment_reminder_email_sent_at",
        """
        ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS reminder_email_sent_at TIMESTAMPTZ;
        CREATE INDEX IF NOT EXISTS idx_apt_reminder_due
            ON appointments (starts_at)
            WHERE status = 'scheduled' AND reminder_email_sent_at IS NULL;
        """,
    ),
]


def run_pending_migrations() -> dict:
    """Apply any migration whose id is not yet in `schema_migrations`."""
    applied: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    try:
        run_sql("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    except Exception as e:
        logger.warning(f"Migrations table init failed: {e}")
        return {"ok": False, "error": str(e)[:200], "applied": [], "skipped": [], "failed": []}

    try:
        rows = run_sql("SELECT id FROM schema_migrations", None, fetch=True) or []
        done_ids = {r["id"] for r in rows}
    except Exception as e:
        logger.warning(f"Could not read schema_migrations: {e}")
        done_ids = set()

    for mig_id, sql in MIGRATIONS:
        if mig_id in done_ids:
            skipped.append(mig_id)
            continue
        try:
            run_sql(sql)
            run_sql("INSERT INTO schema_migrations (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (mig_id,))
            applied.append(mig_id)
            logger.info(f"Migration applied: {mig_id}")
        except Exception as e:
            failed.append(mig_id)
            logger.warning(f"Migration {mig_id} failed: {e}")

    return {"ok": True, "applied": applied, "skipped": skipped, "failed": failed}
