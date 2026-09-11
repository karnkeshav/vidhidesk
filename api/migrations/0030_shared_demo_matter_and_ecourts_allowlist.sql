-- Migration: 0030_shared_demo_matter_and_ecourts_allowlist.sql
-- Description: Two related additions requested directly by the platform
-- owner (2026-09-11 session):
--
--   1. A "shared demo matter" mechanism -- a matter flagged
--      is_shared_demo=true becomes READ-ONLY visible to every
--      authenticated user across every organization, not just its own
--      org's members. Confirmed explicitly with the owner before
--      building this: the specific matter this unlocks for (a real
--      litigation matter, Sharma v. Gupta, FAO (COMM) 114/2026, Delhi
--      High Court) is a genuine case, and the owner confirmed he is fine
--      with every signed-in user seeing it read-only as a working example
--      of real eCourts-synced case tracking. This is a deliberate,
--      narrow hole in the tenant-isolation RLS rewritten in
--      0024_tenant_foundation.sql -- additive SELECT-only policies,
--      never touching INSERT/UPDATE/DELETE, which stay org-membership-
--      only exactly as 0024 left them. Scoped to what a demo viewer
--      needs to see the case itself (overview, parties, facts/exhibits,
--      hearings, tracking, causelist, interlocutory applications,
--      advocates, orders) -- deliberately EXCLUDES messages/
--      draft_versions/draft_clause_fills, so chat history and AI
--      drafting artifacts stay private even on a matter flagged as a
--      shared demo.
--
--   2. An eCourts search allowlist -- every operation that can trigger a
--      live, billable eCourts API call (app/services/court_data_gateway.py)
--      is gated in app/routers/court_tracking.py to callers whose email
--      appears in this table. Deliberately a Supabase-managed table, not
--      an env var like PLATFORM_OWNER_EMAILS -- the owner explicitly
--      asked for this to be editable from Supabase directly (e.g. to
--      admit specific "authorised" testers later) without a redeploy.
--      Seeded with the owner's own email so nothing regresses for him.
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DROP POLICY IF EXISTS /
-- ON CONFLICT DO NOTHING throughout).

-- ============================================================
-- 1. Shared demo matter support
-- ============================================================
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS is_shared_demo boolean NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION public.is_shared_demo_matter(p_matter_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.matters m WHERE m.id = p_matter_id AND m.is_shared_demo
    );
$$;

-- matters itself: an ADDITIVE (permissive) SELECT-only policy. Postgres
-- OR's multiple permissive policies together per command, so this only
-- ever WIDENS what SELECT can see -- it cannot narrow or affect
-- matters_org_member_all (0024_tenant_foundation.sql), which alone still
-- governs INSERT/UPDATE/DELETE.
DROP POLICY IF EXISTS matters_demo_read ON public.matters;
CREATE POLICY matters_demo_read ON public.matters
    FOR SELECT USING (is_shared_demo AND auth.role() = 'authenticated');

DROP POLICY IF EXISTS litigation_parties_demo_read ON public.litigation_parties;
CREATE POLICY litigation_parties_demo_read ON public.litigation_parties
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS litigation_facts_demo_read ON public.litigation_facts_evidence;
CREATE POLICY litigation_facts_demo_read ON public.litigation_facts_evidence
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS litigation_hearings_demo_read ON public.litigation_hearings;
CREATE POLICY litigation_hearings_demo_read ON public.litigation_hearings
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

-- public.hearings.matter_id is nullable (0021_create_hearings.sql) --
-- calendar hearings not attached to any matter never qualify.
DROP POLICY IF EXISTS hearings_demo_read ON public.hearings;
CREATE POLICY hearings_demo_read ON public.hearings
    FOR SELECT USING (matter_id IS NOT NULL AND public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS court_case_tracking_demo_read ON public.court_case_tracking;
CREATE POLICY court_case_tracking_demo_read ON public.court_case_tracking
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS causelist_demo_read ON public.court_hearings_causelist;
CREATE POLICY causelist_demo_read ON public.court_hearings_causelist
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS ia_demo_read ON public.interlocutory_applications;
CREATE POLICY ia_demo_read ON public.interlocutory_applications
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS case_advocate_links_demo_read ON public.case_advocate_links;
CREATE POLICY case_advocate_links_demo_read ON public.case_advocate_links
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

DROP POLICY IF EXISTS orders_demo_read ON public.orders;
CREATE POLICY orders_demo_read ON public.orders
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));

-- ============================================================
-- 2. eCourts search allowlist
-- ============================================================
CREATE TABLE IF NOT EXISTS public.ecourts_search_allowlist (
    email text PRIMARY KEY,
    note text,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.ecourts_search_allowlist ENABLE ROW LEVEL SECURITY;
-- No authenticated-role policy at all, deliberately -- service_role
-- (backend) reads it for the gate check; only the Supabase table editor
-- (or a service-role script) writes it. Same posture as account_security/
-- pii_masks/court_sync_log: not meant for direct client reads or writes.

INSERT INTO public.ecourts_search_allowlist (email, note)
VALUES ('keshav.karn@gmail.com', 'Platform owner -- pays for eCourts API usage, never restricted')
ON CONFLICT (email) DO NOTHING;
