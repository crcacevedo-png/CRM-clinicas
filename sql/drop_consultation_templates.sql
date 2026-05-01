-- Migration: Drop consultation_templates table
-- Date: 2026-05-01
-- Reason: User requested removal of "planillas" (consultation templates) module.
--         All rows have been deleted via the admin API; this script removes the
--         table itself. No other tables reference consultation_templates (no FKs),
--         so this is safe.
--
-- Run this in the Supabase SQL Editor:

DROP TABLE IF EXISTS public.consultation_templates CASCADE;
