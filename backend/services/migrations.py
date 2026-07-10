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
    (
        "2026_05_24_audit_log_v1",
        """
        -- ============================================================
        -- AUDIT LOG v1 — append-only, immutable, RLS-scoped
        -- ============================================================
        CREATE TABLE IF NOT EXISTS public.audit_log (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            action        TEXT NOT NULL,          -- e.g. 'login', 'password_reset', 'plan_change'
            entity        TEXT,                   -- e.g. 'clinic', 'patient', 'prescription'
            entity_id     UUID,
            clinic_id     UUID,                   -- nullable for super-admin global actions
            actor_user_id UUID,                   -- auth.users.id, nullable for system events
            actor_email   TEXT,
            actor_role    TEXT,                   -- 'super_admin' | 'clinic_admin' | 'doctor' | ...
            old_values    JSONB,
            new_values    JSONB,
            ip_address    INET,
            user_agent    TEXT,
            meta          JSONB                   -- arbitrary extra context
        );

        CREATE INDEX IF NOT EXISTS idx_audit_log_clinic_time
            ON public.audit_log (clinic_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_actor_time
            ON public.audit_log (actor_user_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_entity
            ON public.audit_log (entity, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_action_time
            ON public.audit_log (action, occurred_at DESC);

        -- Immutability trigger: nobody (not even service_role) can UPDATE or DELETE.
        CREATE OR REPLACE FUNCTION public.audit_log_immutable()
        RETURNS TRIGGER LANGUAGE plpgsql AS $f$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (% blocked)', TG_OP;
        END;
        $f$;

        DROP TRIGGER IF EXISTS audit_log_no_update ON public.audit_log;
        CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON public.audit_log
            FOR EACH ROW EXECUTE FUNCTION public.audit_log_immutable();

        DROP TRIGGER IF EXISTS audit_log_no_delete ON public.audit_log;
        CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON public.audit_log
            FOR EACH ROW EXECUTE FUNCTION public.audit_log_immutable();

        -- RLS: super admin sees all; clinic_admin sees only their clinic.
        -- Backend writes via service_role (bypasses RLS for INSERT).
        ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS audit_log_super_admin_all ON public.audit_log;
        CREATE POLICY audit_log_super_admin_all
            ON public.audit_log FOR SELECT TO public
            USING (public.is_super_admin());

        DROP POLICY IF EXISTS audit_log_clinic_admin_scoped ON public.audit_log;
        CREATE POLICY audit_log_clinic_admin_scoped
            ON public.audit_log FOR SELECT TO public
            USING (
                clinic_id IS NOT NULL
                AND public.user_has_role(clinic_id, ARRAY['clinic_admin'::user_role])
            );

        -- Lock down anon completely
        REVOKE ALL ON public.audit_log FROM anon;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.audit_log FROM authenticated;
        """,
    ),
    (
        "2026_06_07_audit_log_partitioning_v2",
        """
        -- audit_log → RANGE partitioned by occurred_at (monthly).
        -- v2 backfills partitions for past 24 months to avoid gaps.
        ALTER TABLE public.audit_log RENAME TO audit_log_legacy;
        ALTER TRIGGER audit_log_no_update ON public.audit_log_legacy
            RENAME TO audit_log_legacy_no_update;
        ALTER TRIGGER audit_log_no_delete ON public.audit_log_legacy
            RENAME TO audit_log_legacy_no_delete;

        CREATE TABLE public.audit_log (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            action        TEXT NOT NULL,
            entity        TEXT,
            entity_id     UUID,
            clinic_id     UUID,
            actor_user_id UUID,
            actor_email   TEXT,
            actor_role    TEXT,
            old_values    JSONB,
            new_values    JSONB,
            ip_address    INET,
            user_agent    TEXT,
            meta          JSONB,
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at);

        CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON public.audit_log
            FOR EACH ROW EXECUTE FUNCTION public.audit_log_immutable();
        CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON public.audit_log
            FOR EACH ROW EXECUTE FUNCTION public.audit_log_immutable();

        CREATE INDEX IF NOT EXISTS idx_audit_log_clinic_time
            ON public.audit_log (clinic_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_actor_time
            ON public.audit_log (actor_user_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_entity
            ON public.audit_log (entity, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_action_time
            ON public.audit_log (action, occurred_at DESC);

        CREATE TABLE IF NOT EXISTS public.audit_log_pre_2026 PARTITION OF public.audit_log
            FOR VALUES FROM (MINVALUE) TO ('2026-01-01');

        DO $mig$
        DECLARE
            m INT;
            start_date DATE;
            end_date DATE;
            part_name TEXT;
        BEGIN
            FOR m IN -24..6 LOOP
                start_date := date_trunc('month', now())::date + (m || ' months')::interval;
                end_date   := start_date + interval '1 month';
                IF start_date < DATE '2026-01-01' THEN
                    CONTINUE;
                END IF;
                part_name  := 'audit_log_' || to_char(start_date, 'YYYY_MM');
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.audit_log FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
            END LOOP;
        END $mig$;

        INSERT INTO public.audit_log
            (id, occurred_at, action, entity, entity_id, clinic_id, actor_user_id,
             actor_email, actor_role, old_values, new_values, ip_address, user_agent, meta)
        SELECT id, occurred_at, action, entity, entity_id, clinic_id, actor_user_id,
               actor_email, actor_role, old_values, new_values, ip_address, user_agent, meta
        FROM public.audit_log_legacy;

        DROP TRIGGER IF EXISTS audit_log_legacy_no_update ON public.audit_log_legacy;
        DROP TRIGGER IF EXISTS audit_log_legacy_no_delete ON public.audit_log_legacy;
        DROP TABLE public.audit_log_legacy;

        ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS audit_log_super_admin_all ON public.audit_log;
        CREATE POLICY audit_log_super_admin_all
            ON public.audit_log FOR SELECT TO public
            USING (public.is_super_admin());
        DROP POLICY IF EXISTS audit_log_clinic_admin_scoped ON public.audit_log;
        CREATE POLICY audit_log_clinic_admin_scoped
            ON public.audit_log FOR SELECT TO public
            USING (
                clinic_id IS NOT NULL
                AND public.user_has_role(clinic_id, ARRAY['clinic_admin'::user_role])
            );
        REVOKE ALL ON public.audit_log FROM anon;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.audit_log FROM authenticated;

        CREATE OR REPLACE FUNCTION public.ensure_audit_partitions(months_ahead INT DEFAULT 3)
        RETURNS INT LANGUAGE plpgsql AS $f$
        DECLARE
            m INT;
            start_date DATE;
            end_date DATE;
            part_name TEXT;
            created INT := 0;
            exists_check INT;
        BEGIN
            FOR m IN 0..months_ahead LOOP
                start_date := date_trunc('month', now())::date + (m || ' months')::interval;
                end_date   := start_date + interval '1 month';
                part_name  := 'audit_log_' || to_char(start_date, 'YYYY_MM');
                SELECT count(*) INTO exists_check
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = part_name;
                IF exists_check = 0 THEN
                    EXECUTE format(
                        'CREATE TABLE public.%I PARTITION OF public.audit_log FOR VALUES FROM (%L) TO (%L)',
                        part_name, start_date, end_date
                    );
                    created := created + 1;
                END IF;
            END LOOP;
            RETURN created;
        END $f$;
        """,
    ),
    (
        "2026_06_07_rate_limit_events_table",
        """
        CREATE TABLE IF NOT EXISTS public.rate_limit_events (
            key         TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events
            ON public.rate_limit_events (key, occurred_at DESC);
        ALTER TABLE public.rate_limit_events ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.rate_limit_events FROM anon, authenticated;
        """,
    ),
    (
        "2026_06_07_export_jobs_table",
        """
        CREATE TABLE IF NOT EXISTS public.export_jobs (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinic_id     UUID NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
            requested_by  UUID,
            requested_email TEXT,
            status        TEXT NOT NULL DEFAULT 'queued',
            progress      JSONB DEFAULT '{}'::jsonb,
            error         TEXT,
            file_path     TEXT,
            file_size     BIGINT,
            signed_url    TEXT,
            url_expires_at TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at    TIMESTAMPTZ,
            finished_at   TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_export_jobs_clinic ON public.export_jobs (clinic_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON public.export_jobs (status) WHERE status IN ('queued','running');

        ALTER TABLE public.export_jobs ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS export_jobs_clinic_admin_scoped ON public.export_jobs;
        CREATE POLICY export_jobs_clinic_admin_scoped
            ON public.export_jobs FOR SELECT TO public
            USING (public.user_has_role(clinic_id, ARRAY['clinic_admin'::user_role]));
        REVOKE ALL ON public.export_jobs FROM anon;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.export_jobs FROM authenticated;
        """,
    ),
    (
        "2026_06_07_distributed_locks_table",
        """
        -- Distributed locks that survive across pods. Simpler than pg_advisory_lock
        -- because it doesn't require holding an open connection.
        CREATE TABLE IF NOT EXISTS public.distributed_locks (
            lock_name   TEXT PRIMARY KEY,
            holder      TEXT,
            acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at  TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_distributed_locks_expires ON public.distributed_locks (expires_at);
        ALTER TABLE public.distributed_locks ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.distributed_locks FROM anon, authenticated;

        -- Atomic acquire: INSERT..ON CONFLICT..DO UPDATE only if expired.
        CREATE OR REPLACE FUNCTION public.try_acquire_lock(p_name TEXT, p_holder TEXT, p_ttl_seconds INT)
        RETURNS BOOLEAN LANGUAGE plpgsql AS $f$
        DECLARE
            got BOOLEAN;
        BEGIN
            INSERT INTO public.distributed_locks (lock_name, holder, acquired_at, expires_at)
            VALUES (p_name, p_holder, NOW(), NOW() + (p_ttl_seconds || ' seconds')::interval)
            ON CONFLICT (lock_name) DO UPDATE
                SET holder = EXCLUDED.holder,
                    acquired_at = EXCLUDED.acquired_at,
                    expires_at = EXCLUDED.expires_at
                WHERE distributed_locks.expires_at < NOW();
            SELECT (holder = p_holder AND acquired_at > NOW() - INTERVAL '5 seconds') INTO got
                FROM public.distributed_locks WHERE lock_name = p_name;
            RETURN COALESCE(got, false);
        END $f$;

        CREATE OR REPLACE FUNCTION public.release_lock(p_name TEXT, p_holder TEXT)
        RETURNS VOID LANGUAGE plpgsql AS $f$
        BEGIN
            DELETE FROM public.distributed_locks WHERE lock_name = p_name AND holder = p_holder;
        END $f$;
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
