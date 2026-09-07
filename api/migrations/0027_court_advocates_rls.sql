-- Migration: 0027_court_advocates_rls.sql
-- Description: Fixes the ERROR-level "RLS Disabled in Public" advisory on
-- public.court_advocates -- it was created (see 0026) with RLS never
-- enabled at all, leaving it readable/writable by the anon and
-- authenticated PostgREST roles with no restriction whatsoever.
--
-- court_advocates has no organization_id (see 0026's note: it's a shared,
-- cross-organization directory keyed by globally-unique name/
-- bar_council_id). It is therefore NOT scoped the same way as
-- case_advocate_links/interlocutory_applications/court_hearings_causelist
-- (which gate on "does this row's matter belong to one of my orgs").
-- Instead:
--   - SELECT/INSERT/UPDATE are open to any authenticated user. This is a
--     deliberate choice, not an oversight: the data held here (an
--     advocate's name/bar council ID/office contact details) is public
--     professional information already sourced from eCourts case records,
--     and the table's own uniqueness constraints (name, bar_council_id)
--     are what let two different organizations' matters reference the
--     SAME advocate row instead of creating duplicates -- an org-scoped
--     policy would defeat that by construction (a fresh INSERT has no
--     case_advocate_links row yet to scope against). The anon role still
--     gets nothing.
--   - No DELETE policy for authenticated -- deleting a shared directory
--     entry can orphan another organization's case_advocate_links (ON
--     DELETE CASCADE), so that stays service_client()-only, same posture
--     as court_sync_log.
ALTER TABLE public.court_advocates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS court_advocates_select_authenticated ON public.court_advocates;
CREATE POLICY court_advocates_select_authenticated ON public.court_advocates
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS court_advocates_insert_authenticated ON public.court_advocates;
CREATE POLICY court_advocates_insert_authenticated ON public.court_advocates
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS court_advocates_update_authenticated ON public.court_advocates;
CREATE POLICY court_advocates_update_authenticated ON public.court_advocates
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);
