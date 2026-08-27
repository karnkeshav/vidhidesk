-- Migration: 0025_litigation_intelligence_ecourts.sql
-- Description: Litigation Intelligence + eCourts integration foundation
-- (docs/00_Product/Enhancement_Roadmap.md Section 4, session discussion
-- 27 Aug 2026). Extends the existing `hearings` table (0021 -- already
-- had court/bench/item_no, chosen over litigation_hearings/0013 as the
-- target shape in the earlier Tenant Foundation work) rather than
-- creating a parallel Hearing concept, and adds the minimum new tables
-- needed for: structured Orders, CNR/court tracking (one row per
-- litigation matter, matter stays canonical), a sync audit log, versioned
-- Hearing Briefs, and in-app notifications.
--
-- Everything here is organization-scoped from creation (no retrofit):
-- every new table carries organization_id directly (not just inherited
-- via a matters join), matching this session's court_case_tracking
-- naming from the spec. RLS follows the EXISTS-against-matters-via-
-- memberships convention 0024_tenant_foundation.sql established.
--
-- Explicitly OUT of scope here:
--   - No live eCourts API calls happen from this file -- schema only.
--   - Google Stitch screens (Hearing Intelligence workspace, Court
--     Tracking panel) are generated/implemented separately; this
--     migration only adds the tables they read/write.
--   - WhatsApp/SMS notification channels -- in-app only, per spec.
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DROP POLICY IF EXISTS
-- throughout, matching every prior migration's convention).

-- ============================================================
-- 1. Extend hearings (0021) with intelligence/provenance fields
-- ============================================================
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS judge text;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS listing_details jsonb;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS arguments_made text;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS judge_questions text;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS opposing_counsel_position text;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS outcome text;
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS next_steps text;

-- Source provenance (spec Section 7): a lawyer's manual entry must never
-- be silently clobbered by the next provider sync. `source` records who
-- last wrote court/bench/item_no/listing_details; sync code must check
-- for 'manual_override' and skip overwriting those fields when present
-- (enforced in application code -- see app/services/court_sync.py).
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual'
    CHECK (source IN ('manual', 'ecourts', 'manual_override'));
ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS source_synced_at timestamptz;

-- ============================================================
-- 2. orders
-- ============================================================
CREATE TABLE IF NOT EXISTS public.orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    hearing_id uuid REFERENCES public.hearings(id) ON DELETE SET NULL,
    order_date date,
    court text,
    raw_text text,
    file_url text,
    -- AI-extracted directions/deadlines -- advisory only, never presented
    -- as the order itself; the source text/file above remains the record
    -- of truth. Shape: [{"direction": str, "deadline": str|null, "complied": bool}].
    ai_extracted_directions jsonb NOT NULL DEFAULT '[]',
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'complied', 'superseded')),
    source text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ecourts')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_matter ON public.orders(matter_id, order_date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_hearing ON public.orders(hearing_id);

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS orders_org_member_all ON public.orders;
CREATE POLICY orders_org_member_all ON public.orders
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = orders.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = orders.matter_id AND mm.user_id = auth.uid()
        )
    );

CREATE OR REPLACE FUNCTION public.handle_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_orders_updated_at ON public.orders;
CREATE TRIGGER set_orders_updated_at
    BEFORE UPDATE ON public.orders
    FOR EACH ROW EXECUTE FUNCTION public.handle_orders_updated_at();

-- ============================================================
-- 3. court_case_tracking (CNR belongs to the Matter -- this is a
--    tracking-state row referencing it, never a second Matter/Case
--    concept, per spec Section 4)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.court_case_tracking (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL UNIQUE REFERENCES public.matters(id) ON DELETE CASCADE,
    cnr_number text,
    tracking_enabled boolean NOT NULL DEFAULT false,
    last_synced_at timestamptz,
    next_hearing_date date,
    -- 'idle' (never synced or tracking disabled), 'syncing', 'synced',
    -- 'error' -- never silently stuck, see app/services/court_sync.py.
    sync_status text NOT NULL DEFAULT 'idle'
        CHECK (sync_status IN ('idle', 'syncing', 'synced', 'error')),
    last_error text,
    -- Normalized eCourtsIndia case-detail response (GET /api/partner/case/{cnr}):
    -- petitioners/respondents/advocates/judge/status/courtName/etc. Raw
    -- provider JSON, kept for traceability -- UI reads through normalized
    -- accessors (app/services/court_sync.py), never this blob directly.
    provider_metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_court_case_tracking_org ON public.court_case_tracking(organization_id);
CREATE INDEX IF NOT EXISTS idx_court_case_tracking_cnr ON public.court_case_tracking(cnr_number) WHERE cnr_number IS NOT NULL;
-- Tracking-enabled + next_hearing_date is the scheduler's own query shape
-- (Section 7/8) -- "which matters need a sync tonight".
CREATE INDEX IF NOT EXISTS idx_court_case_tracking_due
    ON public.court_case_tracking(next_hearing_date) WHERE tracking_enabled;

ALTER TABLE public.court_case_tracking ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS court_case_tracking_org_member_all ON public.court_case_tracking;
CREATE POLICY court_case_tracking_org_member_all ON public.court_case_tracking
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = court_case_tracking.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = court_case_tracking.matter_id AND mm.user_id = auth.uid()
        )
    );

CREATE OR REPLACE FUNCTION public.handle_court_case_tracking_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_court_case_tracking_updated_at ON public.court_case_tracking;
CREATE TRIGGER set_court_case_tracking_updated_at
    BEFORE UPDATE ON public.court_case_tracking
    FOR EACH ROW EXECUTE FUNCTION public.handle_court_case_tracking_updated_at();

-- ============================================================
-- 4. court_sync_log (append-only audit trail -- backend/service_client()
--    only, same posture as organization_access_events/pii_masks; not
--    meant for direct client reads, surfaced via the tracking API instead)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.court_sync_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    cnr_number text,
    operation text NOT NULL CHECK (operation IN ('case_lookup', 'bulk_refresh', 'causelist_batch')),
    status text NOT NULL CHECK (status IN ('success', 'error')),
    provider_request_id text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_court_sync_log_matter ON public.court_sync_log(matter_id, created_at DESC);

ALTER TABLE public.court_sync_log ENABLE ROW LEVEL SECURITY;
-- No authenticated-role policy -- service_client() only, same as
-- organization_access_events (0024_tenant_foundation.sql).

-- ============================================================
-- 5. hearing_briefs
-- ============================================================
CREATE TABLE IF NOT EXISTS public.hearing_briefs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    hearing_id uuid NOT NULL REFERENCES public.hearings(id) ON DELETE CASCADE,
    version integer NOT NULL,

    -- generated -> draft -> reviewed -> approved_for_hearing (spec
    -- Section 11) -- never auto-advances past 'draft'; only a lawyer
    -- action (PATCH .../review, .../approve) moves it forward.
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'reviewed', 'approved_for_hearing')),

    generated_at timestamptz NOT NULL DEFAULT now(),
    generated_by text, -- model_used, same convention as every other AI-output table

    -- Exactly which source rows fed this generation (matter/pleading/
    -- order/hearing/evidence/citation ids actually read) -- the
    -- traceability the spec requires: "every bundle component should be
    -- traceable to its source record."
    source_snapshot jsonb NOT NULL DEFAULT '{}',

    -- The four-part structure (Section 10): case_record and
    -- supported_arguments are grounded-only (each item carries a
    -- source reference); ai_suggested_points is explicitly,
    -- separately labeled; checklist and information_gaps round it out.
    -- Enforced in code (app/services/hearing_brief.py), not just by
    -- convention -- see _validate_brief_sections().
    brief_content jsonb NOT NULL DEFAULT '{}',

    -- Freeform lawyer edits layered on top of brief_content -- the
    -- generated version is never mutated in place (immutable-per-version,
    -- same convention as litigation_pleading_clauses/drafts).
    lawyer_edits jsonb,

    reviewed_at timestamptz,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE (hearing_id, version)
);

CREATE INDEX IF NOT EXISTS idx_hearing_briefs_hearing ON public.hearing_briefs(hearing_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_hearing_briefs_matter ON public.hearing_briefs(matter_id);

ALTER TABLE public.hearing_briefs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hearing_briefs_select_org_member ON public.hearing_briefs;
CREATE POLICY hearing_briefs_select_org_member ON public.hearing_briefs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = hearing_briefs.matter_id AND mm.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS hearing_briefs_insert_org_member ON public.hearing_briefs;
CREATE POLICY hearing_briefs_insert_org_member ON public.hearing_briefs
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = hearing_briefs.matter_id AND mm.user_id = auth.uid()
        )
    );

-- UPDATE is restricted to review/edit fields at the application layer
-- (status/lawyer_edits/reviewed_at/approved_at) -- brief_content itself
-- is immutable per version, same convention as
-- litigation_pleading_clauses' review-only UPDATE policy.
DROP POLICY IF EXISTS hearing_briefs_update_org_member ON public.hearing_briefs;
CREATE POLICY hearing_briefs_update_org_member ON public.hearing_briefs
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = hearing_briefs.matter_id AND mm.user_id = auth.uid()
        )
    );

CREATE OR REPLACE FUNCTION public.handle_hearing_briefs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_hearing_briefs_updated_at ON public.hearing_briefs;
CREATE TRIGGER set_hearing_briefs_updated_at
    BEFORE UPDATE ON public.hearing_briefs
    FOR EACH ROW EXECUTE FUNCTION public.handle_hearing_briefs_updated_at();

-- ============================================================
-- 6. notifications (in-app only, per spec Section 13)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    matter_id uuid REFERENCES public.matters(id) ON DELETE CASCADE,
    -- 'hearing_listed' | 'brief_ready' -- deliberately not a bare text
    -- field with no constraint, so a typo'd type can't silently create
    -- an un-renderable notification the frontend has no case for.
    type text NOT NULL CHECK (type IN ('hearing_listed', 'brief_ready')),
    title text NOT NULL,
    body text NOT NULL,
    -- Idempotency key (Section 8/13: "no duplicate notifications"): the
    -- backend computes this deterministically (e.g. hash of
    -- type+matter_id+hearing_id+date) and upserts on it rather than
    -- blindly inserting -- see app/services/notifications.py.
    dedupe_key text NOT NULL,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON public.notifications(user_id, created_at DESC);

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Owner reads their own notifications and may mark them read (UPDATE
-- restricted to read_at at the application layer) -- no INSERT/DELETE
-- policy for the authenticated role; only service_client() creates
-- notifications, same posture as every other backend-authored table.
DROP POLICY IF EXISTS notifications_select_own ON public.notifications;
CREATE POLICY notifications_select_own ON public.notifications
    FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS notifications_update_own ON public.notifications;
CREATE POLICY notifications_update_own ON public.notifications
    FOR UPDATE USING (user_id = auth.uid());
