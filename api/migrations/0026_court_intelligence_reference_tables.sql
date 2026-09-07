-- Migration: 0026_court_intelligence_reference_tables.sql
-- Description: Documents the four Litigation Intelligence reference
-- tables (court_advocates, case_advocate_links, interlocutory_applications,
-- court_hearings_causelist) that were applied directly to the Supabase
-- project on/around 6 Sep 2026 without ever being committed as a migration
-- file -- there was no 0026 in the repo before this one. This file is
-- written to match the schema already live in the database exactly (see
-- verification queries run against information_schema/pg_constraint/
-- pg_indexes/pg_trigger on 2026-09-07), so applying it is a no-op there;
-- its purpose is to make the schema reproducible from the repo for any
-- other environment and to close the drift between the repo and Supabase.
--
-- IF NOT EXISTS / DROP ... IF EXISTS throughout, matching every prior
-- migration's idempotency convention.
--
-- court_advocates deliberately has NO organization_id: it is a shared,
-- cross-organization directory (advocate name/bar_council_id are globally
-- unique) so the same real-world advocate is one row no matter which
-- org's matter they appear opposite. Tenant scoping for "which advocates
-- can this org see" happens one level down, through case_advocate_links
-- (which does carry organization_id/matter_id and is scoped the same way
-- as every other table 0025 established). RLS for court_advocates itself
-- is added separately in 0027_court_advocates_rls.sql -- it was missing
-- entirely from the original apply (ERROR-level "RLS Disabled in Public"
-- lint), which this migration does not try to silently paper over.

-- ============================================================
-- 1. court_advocates (global advocate directory)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.court_advocates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    bar_council_id text UNIQUE,
    phone text,
    email text,
    website text,
    office_address text,
    case_count integer NOT NULL DEFAULT 1,
    first_seen_in_case date,
    last_seen_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_court_advocates_name ON public.court_advocates(name);
CREATE INDEX IF NOT EXISTS idx_court_advocates_bar_council ON public.court_advocates(bar_council_id) WHERE bar_council_id IS NOT NULL;

-- Missing from the original apply (updated_at never auto-refreshed) --
-- added here since every other timestamped table in this schema has one.
CREATE OR REPLACE FUNCTION public.handle_court_advocates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_court_advocates_updated_at ON public.court_advocates;
CREATE TRIGGER set_court_advocates_updated_at
    BEFORE UPDATE ON public.court_advocates
    FOR EACH ROW EXECUTE FUNCTION public.handle_court_advocates_updated_at();

-- ============================================================
-- 2. case_advocate_links (junction: which advocate appeared for which
--    party on which matter -- this is what carries the org/matter scope)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.case_advocate_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    advocate_id uuid NOT NULL REFERENCES public.court_advocates(id) ON DELETE CASCADE,
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    cnr_number text,
    role text NOT NULL DEFAULT 'UNKNOWN'
        CHECK (role IN ('PETITIONER_COUNSEL', 'RESPONDENT_COUNSEL', 'UNKNOWN')),
    first_appeared date,
    last_appeared date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (advocate_id, matter_id)
);

CREATE INDEX IF NOT EXISTS idx_case_advocate_links_advocate ON public.case_advocate_links(advocate_id);
CREATE INDEX IF NOT EXISTS idx_case_advocate_links_matter ON public.case_advocate_links(matter_id);
CREATE INDEX IF NOT EXISTS idx_case_advocate_links_org ON public.case_advocate_links(organization_id);

ALTER TABLE public.case_advocate_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_advocate_links_org_member_all ON public.case_advocate_links;
CREATE POLICY case_advocate_links_org_member_all ON public.case_advocate_links
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = case_advocate_links.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = case_advocate_links.matter_id AND mm.user_id = auth.uid()
        )
    );

-- Missing from the original apply -- added for the same reason as
-- court_advocates above.
CREATE OR REPLACE FUNCTION public.handle_case_advocate_links_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_case_advocate_links_updated_at ON public.case_advocate_links;
CREATE TRIGGER set_case_advocate_links_updated_at
    BEFORE UPDATE ON public.case_advocate_links
    FOR EACH ROW EXECUTE FUNCTION public.handle_case_advocate_links_updated_at();

-- ============================================================
-- 3. interlocutory_applications (pending/decided IAs -- CM APPLs -- on a matter)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.interlocutory_applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    cnr_number text,
    application_number text NOT NULL,
    filed_by text NOT NULL,
    filing_date date NOT NULL,
    current_status text NOT NULL DEFAULT 'PENDING'
        CHECK (current_status IN ('PENDING', 'GRANTED', 'REJECTED', 'WITHDRAWN')),
    relief_sought text,
    last_update_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, application_number)
);

CREATE INDEX IF NOT EXISTS idx_ia_matter ON public.interlocutory_applications(matter_id);
CREATE INDEX IF NOT EXISTS idx_ia_status ON public.interlocutory_applications(current_status) WHERE current_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_ia_org ON public.interlocutory_applications(organization_id);

ALTER TABLE public.interlocutory_applications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ia_org_member_all ON public.interlocutory_applications;
CREATE POLICY ia_org_member_all ON public.interlocutory_applications
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = interlocutory_applications.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = interlocutory_applications.matter_id AND mm.user_id = auth.uid()
        )
    );

CREATE OR REPLACE FUNCTION public.handle_ia_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_ia_updated_at ON public.interlocutory_applications;
CREATE TRIGGER set_ia_updated_at
    BEFORE UPDATE ON public.interlocutory_applications
    FOR EACH ROW EXECUTE FUNCTION public.handle_ia_updated_at();

-- ============================================================
-- 4. court_hearings_causelist (daily causelist cache per matter)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.court_hearings_causelist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    cnr_number text,
    hearing_date date NOT NULL,
    hearing_time time,
    bench_number text,
    judge_names text[],
    court_location text,
    causelist_type text,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, hearing_date)
);

CREATE INDEX IF NOT EXISTS idx_causelist_matter ON public.court_hearings_causelist(matter_id);
CREATE INDEX IF NOT EXISTS idx_causelist_date ON public.court_hearings_causelist(hearing_date);
CREATE INDEX IF NOT EXISTS idx_causelist_org ON public.court_hearings_causelist(organization_id);

ALTER TABLE public.court_hearings_causelist ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS causelist_org_member_all ON public.court_hearings_causelist;
CREATE POLICY causelist_org_member_all ON public.court_hearings_causelist
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = court_hearings_causelist.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = court_hearings_causelist.matter_id AND mm.user_id = auth.uid()
        )
    );

CREATE OR REPLACE FUNCTION public.handle_causelist_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_causelist_updated_at ON public.court_hearings_causelist;
CREATE TRIGGER set_causelist_updated_at
    BEFORE UPDATE ON public.court_hearings_causelist
    FOR EACH ROW EXECUTE FUNCTION public.handle_causelist_updated_at();
