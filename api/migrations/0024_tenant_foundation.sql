-- Migration: 0024_tenant_foundation.sql
-- Description: Multi-tenancy foundation (docs/00_Product/Enhancement_Roadmap.md
-- Section 2/3, "Recommended Single Next Step"). Introduces organizations and
-- memberships, adds organization_id to the two root owner-scoped tables
-- (matters, hearings), migrates existing live data into per-user
-- organizations so nothing becomes inaccessible, and rewrites every
-- matter-scoped RLS policy from "owner reads own row" (auth.uid() = user_id)
-- to "member of the matter's organization reads the row".
--
-- Amended 27 Aug 2026 (security/migration review follow-up): the
-- backfill's membership creation now also sets is_default=true (see
-- Section 2's is_default column), and a new atomic
-- ensure_organization_membership() function/RPC (Section 5b) replaces
-- the previous two-round-trip org+membership provisioning in
-- routers/auth.py, closing a partial-failure/orphan-organization gap the
-- review identified. organizations.access_enabled/subscription_status
-- are ALSO no longer purely informational as of this amendment -- see
-- app/auth.py::_check_organization_access, added the same day as an
-- ADDITIVE second gate alongside (never replacing) account_security.
--
-- Explicitly OUT of scope for this migration (see Enhancement_Roadmap.md and
-- session discussion, 26-27 Aug 2026):
--   - The existing per-user 5-day trial lock (account_security,
--     0022/0023, api/app/auth.py::_check_account_not_locked) is NOT
--     touched, rewritten, or replaced. It remains the sole user-level
--     gate, checked BEFORE the new organization-level gate on every
--     request (see _check_organization_access's ordering note). Fully
--     consolidating account_security and organizations.subscription_status
--     into one mechanism is a deliberate, separate future decision, not
--     made here.
--   - advocate_profiles stays user-scoped, not organization-scoped: a bar
--     number/designation belongs to the individual professional, not the
--     firm, even if they later change organizations.
--   - template_clauses/clause_reviews/templates/citations/statute_chunks/
--     state_rules/rera_guides are shared reference data (0002_rls.sql,
--     0007_contracts_clause_review.sql already establish this) and are not
--     touched -- they stay platform-wide, not per-organization.
--   - No structured Litigation objects (Order/Filing/Witness) are added
--     here -- Litigation implementation is strictly gated pending the
--     Google Stitch design lifecycle (docs/50_Reference/Stitch_Guidelines.md,
--     Build_Tracker.md Sec 0.3), and this migration is tenancy plumbing,
--     not a new Litigation feature. Existing litigation_* tables ARE
--     included below because leaving their RLS on the old single-user
--     policy while matters/hearings move to org-based RLS would silently
--     break access to a matter's own child data.
--
-- DEPLOYMENT NOTE: this migration and the corresponding backend change
-- (api/app/auth.py resolving CurrentUser.organization_id, matters.py/
-- hearings.py setting organization_id on insert) must ship together. Once
-- applied, matters/hearings INSERT will fail RLS's WITH CHECK unless the
-- request already sets organization_id -- do not apply this to production
-- before deploying the matching backend code.
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DROP POLICY IF EXISTS
-- throughout; the backfill DO block only acts on users still missing a
-- membership row, so re-running it is a no-op on a second pass).

-- ============================================================
-- 1. organizations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.organizations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    organization_type text NOT NULL DEFAULT 'individual'
        CHECK (organization_type IN ('individual', 'firm')),
    subscription_status text NOT NULL DEFAULT 'trial'
        CHECK (subscription_status IN ('trial', 'active', 'suspended', 'expired')),
    trial_started_at timestamptz NOT NULL DEFAULT now(),
    trial_ends_at timestamptz NOT NULL DEFAULT (now() + interval '5 days'),
    access_enabled boolean NOT NULL DEFAULT true,
    payment_marked_at timestamptz,
    payment_marked_by uuid REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

-- organizations_select_member is created further below, after
-- public.memberships exists (its USING clause queries memberships, so
-- creating it here -- before memberships exists -- fails with
-- 42P01: relation "public.memberships" does not exist).

CREATE OR REPLACE FUNCTION public.handle_organizations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_organizations_updated_at ON public.organizations;
CREATE TRIGGER set_organizations_updated_at
    BEFORE UPDATE ON public.organizations
    FOR EACH ROW EXECUTE FUNCTION public.handle_organizations_updated_at();

-- ============================================================
-- 2. memberships
-- ============================================================
CREATE TABLE IF NOT EXISTS public.memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'member' CHECK (role IN ('org_admin', 'member')),
    -- Deterministic organization resolution (security review follow-up,
    -- 27 Aug 2026): the schema deliberately allows a user to belong to
    -- more than one organization (future firm-collaboration support), so
    -- app/auth.py::_fetch_organization_id must not rely on an
    -- undefined-order `LIMIT 1`. Exactly one membership per user may be
    -- is_default -- enforced below by a partial unique index, not just
    -- application logic -- and that is the one CurrentUser.organization_id
    -- ever resolves to. A future "switch active organization" feature
    -- flips this flag on a different row; it does not require touching
    -- this column's meaning or any RLS policy.
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_memberships_user ON public.memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON public.memberships(organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memberships_one_default_per_user
    ON public.memberships(user_id) WHERE is_default;

ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;

-- A user can see their own membership row(s) -- needed so the frontend can
-- resolve "what organization am I in" without a service-role call. No
-- authenticated write policy: membership management (invites, role
-- changes) is backend/service_client()-only in this phase, same reasoning
-- as organizations above -- firm-internal member invites are explicitly
-- out of scope for this pass (Enhancement_Roadmap.md Section 2.5).
DROP POLICY IF EXISTS memberships_select_own ON public.memberships;
CREATE POLICY memberships_select_own ON public.memberships
    FOR SELECT USING (user_id = auth.uid());

CREATE OR REPLACE FUNCTION public.handle_memberships_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_memberships_updated_at ON public.memberships;
CREATE TRIGGER set_memberships_updated_at
    BEFORE UPDATE ON public.memberships
    FOR EACH ROW EXECUTE FUNCTION public.handle_memberships_updated_at();

-- Members can see their own organization's metadata (e.g. a future
-- "trial ends in N days" banner). No INSERT/UPDATE/DELETE policy for the
-- authenticated role -- organization lifecycle (creation, status changes,
-- payment marking) is only ever done by the backend via service_client(),
-- same convention as account_security (0022/0023). Created here, after
-- memberships exists, since its USING clause queries memberships.
DROP POLICY IF EXISTS organizations_select_member ON public.organizations;
CREATE POLICY organizations_select_member ON public.organizations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.memberships mm
            WHERE mm.organization_id = organizations.id
              AND mm.user_id = auth.uid()
        )
    );

-- ============================================================
-- 3. organization_access_events (platform-owner audit trail)
-- ============================================================
-- No policy for the authenticated/anon role at all -- same posture as
-- pii_masks (0002_rls.sql): only service_client() (platform-owner API
-- routes, after a server-side owner check) ever reads or writes this.
CREATE TABLE IF NOT EXISTS public.organization_access_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    previous_status text,
    new_status text,
    action text NOT NULL,
    actor_user_id uuid REFERENCES auth.users(id),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_access_events_org
    ON public.organization_access_events(organization_id, created_at DESC);

ALTER TABLE public.organization_access_events ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 4. organization_id on the two root owner-scoped tables
-- ============================================================
-- Nullable at the DB level deliberately: the backend always sets it on
-- insert going forward (see DEPLOYMENT NOTE above), but a hard NOT NULL
-- constraint here would make this migration order-sensitive against the
-- backfill below in a way that isn't worth the extra safety given RLS's
-- WITH CHECK already refuses a NULL-organization_id write (see Section 6).
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
CREATE INDEX IF NOT EXISTS idx_matters_organization ON public.matters(organization_id);

ALTER TABLE public.hearings ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
CREATE INDEX IF NOT EXISTS idx_hearings_organization ON public.hearings(organization_id);

-- ============================================================
-- 5. Backfill: wrap every existing user into an individual organization
-- ============================================================
-- One organization per distinct existing user who owns a matter, a
-- hearing, or an advocate profile and doesn't already have a membership
-- (idempotent: the NOT EXISTS guard means re-running this is a no-op for
-- users already migrated). Backfilled organizations start
-- subscription_status='active'/access_enabled=true -- these are real,
-- already-working users, not new trial signups, and the actual access
-- gate remains account_security's per-user 5-day lock, unaffected by this
-- migration (see header note).
DO $$
DECLARE
    r RECORD;
    new_org_id uuid;
BEGIN
    FOR r IN
        SELECT DISTINCT u.id AS user_id, u.email
        FROM auth.users u
        WHERE (
            EXISTS (SELECT 1 FROM public.matters m WHERE m.user_id = u.id)
            OR EXISTS (SELECT 1 FROM public.hearings h WHERE h.user_id = u.id)
            OR EXISTS (SELECT 1 FROM public.advocate_profiles ap WHERE ap.user_id = u.id)
        )
        AND NOT EXISTS (SELECT 1 FROM public.memberships mm WHERE mm.user_id = u.id)
    LOOP
        INSERT INTO public.organizations (name, organization_type, subscription_status, access_enabled)
        VALUES (COALESCE(r.email, 'Advocate') || '''s Practice', 'individual', 'active', true)
        RETURNING id INTO new_org_id;

        INSERT INTO public.memberships (organization_id, user_id, role, is_default)
        VALUES (new_org_id, r.user_id, 'org_admin', true);
    END LOOP;
END $$;

-- Any membership row that predates the is_default column (impossible on a
-- fresh apply of this same file, but keeps the migration correct if a
-- future edit ever splits this into a separate ALTER) gets backfilled to
-- is_default=true when it's the only membership its user has -- never
-- guesses when a user already has more than one row.
UPDATE public.memberships m
SET is_default = true
WHERE NOT m.is_default
  AND (SELECT count(*) FROM public.memberships m2 WHERE m2.user_id = m.user_id) = 1;

-- ============================================================
-- 5b. Atomic organization+membership provisioning (security review
-- follow-up, 27 Aug 2026)
-- ============================================================
-- Replaces the two-round-trip provisioning previously done in Python
-- (routers/auth.py::_ensure_organization) with one atomic, idempotent,
-- concurrency-safe operation: a partial failure between "create org" and
-- "create membership" can no longer happen, because both writes are in
-- the same function body / same transaction, and pg_advisory_xact_lock
-- serializes concurrent first-ever calls for the SAME user (e.g. two
-- browser tabs signing in at once) so only one organization is ever
-- created for them -- a different user never contends for this lock,
-- since the key is derived from their own uid.
--
-- SECURITY DEFINER + a fixed search_path (schema-shadowing hardening),
-- but this alone would make the function executable by any role Postgres
-- grants EXECUTE to by default (PUBLIC) -- the REVOKE/GRANT block below
-- restricts that explicitly to service_role, matching every other write
-- path into organizations/memberships (both tables carry zero
-- authenticated-role INSERT/UPDATE policy already). Without that REVOKE,
-- any authenticated user could call this via PostgREST's /rpc/ endpoint
-- with an arbitrary p_user_id and create a membership for someone else.
CREATE OR REPLACE FUNCTION public.ensure_organization_membership(p_user_id uuid, p_email text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_org_id uuid;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_user_id::text));

    SELECT organization_id INTO v_org_id
    FROM public.memberships
    WHERE user_id = p_user_id AND is_default
    LIMIT 1;

    IF v_org_id IS NOT NULL THEN
        RETURN v_org_id;
    END IF;

    INSERT INTO public.organizations (name, organization_type)
    VALUES (COALESCE(p_email, 'Advocate') || '''s Practice', 'individual')
    RETURNING id INTO v_org_id;

    INSERT INTO public.memberships (organization_id, user_id, role, is_default)
    VALUES (v_org_id, p_user_id, 'org_admin', true);

    RETURN v_org_id;
END;
$$;

REVOKE ALL ON FUNCTION public.ensure_organization_membership(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ensure_organization_membership(uuid, text) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ensure_organization_membership(uuid, text) TO service_role;

-- Backfill organization_id on matters/hearings from the now-guaranteed
-- membership row of each existing row's owning user.
UPDATE public.matters m
SET organization_id = mm.organization_id
FROM public.memberships mm
WHERE mm.user_id = m.user_id
  AND m.organization_id IS NULL;

UPDATE public.hearings h
SET organization_id = mm.organization_id
FROM public.memberships mm
WHERE mm.user_id = h.user_id
  AND h.organization_id IS NULL;

-- ============================================================
-- 6. RLS rewrite: matters and hearings (root tables)
-- ============================================================
DROP POLICY IF EXISTS matters_owner_all ON public.matters;
DROP POLICY IF EXISTS matters_org_member_all ON public.matters;
CREATE POLICY matters_org_member_all ON public.matters
    FOR ALL USING (
        organization_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.memberships mm
            WHERE mm.organization_id = matters.organization_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        organization_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.memberships mm
            WHERE mm.organization_id = matters.organization_id AND mm.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS hearings_select_owner ON public.hearings;
DROP POLICY IF EXISTS hearings_insert_owner ON public.hearings;
DROP POLICY IF EXISTS hearings_update_owner ON public.hearings;
DROP POLICY IF EXISTS hearings_delete_owner ON public.hearings;
DROP POLICY IF EXISTS hearings_org_member_all ON public.hearings;
CREATE POLICY hearings_org_member_all ON public.hearings
    FOR ALL USING (
        organization_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.memberships mm
            WHERE mm.organization_id = hearings.organization_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        organization_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.memberships mm
            WHERE mm.organization_id = hearings.organization_id AND mm.user_id = auth.uid()
        )
    );

-- ============================================================
-- 7. RLS rewrite: tables scoped via matters.organization_id
-- ============================================================
-- Same EXISTS-against-parent-matters convention every one of these
-- already used (Database_Architecture.md's documented pattern) -- only
-- the join now also crosses memberships instead of comparing user_id
-- directly, so any member of the matter's organization (not only the
-- original creator) gets the same access the creator always had.

-- messages
DROP POLICY IF EXISTS messages_owner_all ON public.messages;
DROP POLICY IF EXISTS messages_org_member_all ON public.messages;
CREATE POLICY messages_org_member_all ON public.messages
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = messages.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = messages.matter_id AND mm.user_id = auth.uid()
        )
    );

-- draft_versions
DROP POLICY IF EXISTS draft_versions_owner_all ON public.draft_versions;
DROP POLICY IF EXISTS draft_versions_org_member_all ON public.draft_versions;
CREATE POLICY draft_versions_org_member_all ON public.draft_versions
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = draft_versions.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = draft_versions.matter_id AND mm.user_id = auth.uid()
        )
    );

-- draft_clause_fills (via draft_versions -> matters)
DROP POLICY IF EXISTS draft_clause_fills_owner_all ON public.draft_clause_fills;
DROP POLICY IF EXISTS draft_clause_fills_org_member_all ON public.draft_clause_fills;
CREATE POLICY draft_clause_fills_org_member_all ON public.draft_clause_fills
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.draft_versions dv
            JOIN public.matters m ON m.id = dv.matter_id
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE dv.id = draft_clause_fills.draft_version_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.draft_versions dv
            JOIN public.matters m ON m.id = dv.matter_id
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE dv.id = draft_clause_fills.draft_version_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_parties
DROP POLICY IF EXISTS litigation_parties_select_owner ON public.litigation_parties;
DROP POLICY IF EXISTS litigation_parties_insert_owner ON public.litigation_parties;
DROP POLICY IF EXISTS litigation_parties_update_owner ON public.litigation_parties;
DROP POLICY IF EXISTS litigation_parties_delete_owner ON public.litigation_parties;
DROP POLICY IF EXISTS litigation_parties_org_member_all ON public.litigation_parties;
CREATE POLICY litigation_parties_org_member_all ON public.litigation_parties
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_parties.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_parties.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_facts_evidence
DROP POLICY IF EXISTS litigation_facts_select_owner ON public.litigation_facts_evidence;
DROP POLICY IF EXISTS litigation_facts_insert_owner ON public.litigation_facts_evidence;
DROP POLICY IF EXISTS litigation_facts_update_owner ON public.litigation_facts_evidence;
DROP POLICY IF EXISTS litigation_facts_delete_owner ON public.litigation_facts_evidence;
DROP POLICY IF EXISTS litigation_facts_org_member_all ON public.litigation_facts_evidence;
CREATE POLICY litigation_facts_org_member_all ON public.litigation_facts_evidence
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_facts_evidence.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_facts_evidence.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_hearings (the matter-scoped docket table -- distinct from
-- the standalone `hearings` Calendar table rewritten in Section 6)
DROP POLICY IF EXISTS litigation_hearings_select_owner ON public.litigation_hearings;
DROP POLICY IF EXISTS litigation_hearings_insert_owner ON public.litigation_hearings;
DROP POLICY IF EXISTS litigation_hearings_update_owner ON public.litigation_hearings;
DROP POLICY IF EXISTS litigation_hearings_delete_owner ON public.litigation_hearings;
DROP POLICY IF EXISTS litigation_hearings_org_member_all ON public.litigation_hearings;
CREATE POLICY litigation_hearings_org_member_all ON public.litigation_hearings
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_hearings.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_hearings.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_case_analyses (select + insert only -- immutable versions)
DROP POLICY IF EXISTS litigation_case_analyses_select_owner ON public.litigation_case_analyses;
DROP POLICY IF EXISTS litigation_case_analyses_insert_owner ON public.litigation_case_analyses;
DROP POLICY IF EXISTS litigation_case_analyses_select_org_member ON public.litigation_case_analyses;
CREATE POLICY litigation_case_analyses_select_org_member ON public.litigation_case_analyses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_case_analyses.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS litigation_case_analyses_insert_org_member ON public.litigation_case_analyses;
CREATE POLICY litigation_case_analyses_insert_org_member ON public.litigation_case_analyses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_case_analyses.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_pleading_outlines (select + insert only)
DROP POLICY IF EXISTS litigation_pleading_outlines_select_owner ON public.litigation_pleading_outlines;
DROP POLICY IF EXISTS litigation_pleading_outlines_insert_owner ON public.litigation_pleading_outlines;
DROP POLICY IF EXISTS litigation_pleading_outlines_select_org_member ON public.litigation_pleading_outlines;
CREATE POLICY litigation_pleading_outlines_select_org_member ON public.litigation_pleading_outlines
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_outlines.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS litigation_pleading_outlines_insert_org_member ON public.litigation_pleading_outlines;
CREATE POLICY litigation_pleading_outlines_insert_org_member ON public.litigation_pleading_outlines
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_outlines.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_pleading_clauses (select + insert + update -- review fields only)
DROP POLICY IF EXISTS litigation_pleading_clauses_select_owner ON public.litigation_pleading_clauses;
DROP POLICY IF EXISTS litigation_pleading_clauses_insert_owner ON public.litigation_pleading_clauses;
DROP POLICY IF EXISTS litigation_pleading_clauses_update_owner ON public.litigation_pleading_clauses;
DROP POLICY IF EXISTS litigation_pleading_clauses_select_org_member ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_select_org_member ON public.litigation_pleading_clauses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_clauses.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS litigation_pleading_clauses_insert_org_member ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_insert_org_member ON public.litigation_pleading_clauses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_clauses.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS litigation_pleading_clauses_update_org_member ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_update_org_member ON public.litigation_pleading_clauses
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_clauses.matter_id AND mm.user_id = auth.uid()
        )
    );

-- litigation_pleading_drafts (select + insert only -- immutable compositions)
DROP POLICY IF EXISTS litigation_pleading_drafts_select_owner ON public.litigation_pleading_drafts;
DROP POLICY IF EXISTS litigation_pleading_drafts_insert_owner ON public.litigation_pleading_drafts;
DROP POLICY IF EXISTS litigation_pleading_drafts_select_org_member ON public.litigation_pleading_drafts;
CREATE POLICY litigation_pleading_drafts_select_org_member ON public.litigation_pleading_drafts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_drafts.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS litigation_pleading_drafts_insert_org_member ON public.litigation_pleading_drafts;
CREATE POLICY litigation_pleading_drafts_insert_org_member ON public.litigation_pleading_drafts
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = litigation_pleading_drafts.matter_id AND mm.user_id = auth.uid()
        )
    );

-- consulting_analyses (select + insert only)
DROP POLICY IF EXISTS consulting_analyses_select_owner ON public.consulting_analyses;
DROP POLICY IF EXISTS consulting_analyses_insert_owner ON public.consulting_analyses;
DROP POLICY IF EXISTS consulting_analyses_select_org_member ON public.consulting_analyses;
CREATE POLICY consulting_analyses_select_org_member ON public.consulting_analyses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = consulting_analyses.matter_id AND mm.user_id = auth.uid()
        )
    );
DROP POLICY IF EXISTS consulting_analyses_insert_org_member ON public.consulting_analyses;
CREATE POLICY consulting_analyses_insert_org_member ON public.consulting_analyses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = consulting_analyses.matter_id AND mm.user_id = auth.uid()
        )
    );
