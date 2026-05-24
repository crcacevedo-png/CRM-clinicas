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
    (
        "2026_05_24_rls_hardening_v1",
        """
        -- ============================================================
        -- RLS HARDENING v1 — fix 5 vulnerability classes
        -- ============================================================

        -- (1) Views with SECURITY DEFINER -> security_invoker so RLS applies
        ALTER VIEW IF EXISTS public.v_daily_sales      SET (security_invoker = on);
        ALTER VIEW IF EXISTS public.v_expiring_products SET (security_invoker = on);
        ALTER VIEW IF EXISTS public.v_low_stock_alerts  SET (security_invoker = on);
        ALTER VIEW IF EXISTS public.v_monthly_pnl       SET (security_invoker = on);

        -- (2) Add WITH CHECK to every UPDATE / ALL policy that has USING but no
        -- WITH CHECK. We mirror USING into WITH CHECK so cross-tenant writes
        -- (UPDATE patients SET clinic_id = 'other') become impossible.
        DO $mig$
        DECLARE
            rec RECORD;
        BEGIN
            FOR rec IN
                SELECT schemaname, tablename, policyname, cmd, roles, qual
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND cmd IN ('UPDATE', 'ALL')
                  AND with_check IS NULL
                  AND qual IS NOT NULL
            LOOP
                EXECUTE format(
                    'ALTER POLICY %I ON %I.%I TO %s USING (%s) WITH CHECK (%s)',
                    rec.policyname,
                    rec.schemaname,
                    rec.tablename,
                    array_to_string(rec.roles, ', '),
                    rec.qual,
                    rec.qual
                );
            END LOOP;
        END
        $mig$;

        -- (3) REVOKE write privileges from anon on EVERY public table.
        -- RLS already blocks them, but defense-in-depth: if a future policy is
        -- buggy, anon still cannot write anything.
        DO $mig$
        DECLARE
            t TEXT;
        BEGIN
            FOR t IN
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'v') AND n.nspname = 'public'
            LOOP
                EXECUTE format(
                    'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.%I FROM anon',
                    t
                );
            END LOOP;
        END
        $mig$;

        -- Make REVOKE the default for future tables too
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLES FROM anon;

        -- (4) schema_migrations: enable RLS + super-admin-only policy
        ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS schema_migrations_super_admin_only ON public.schema_migrations;
        CREATE POLICY schema_migrations_super_admin_only
            ON public.schema_migrations
            FOR ALL TO public
            USING (public.is_super_admin())
            WITH CHECK (public.is_super_admin());
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
