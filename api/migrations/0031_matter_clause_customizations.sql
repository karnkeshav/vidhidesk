-- Migration: 0031_matter_clause_customizations.sql
-- Description: Per-matter clause customization for Contracts (2026-09-11
-- session, requested directly by the platform owner): today,
-- template_clauses.review_status ('beta'/'reviewed') is ONE shared,
-- global decision -- the owner reviews a template once via
-- /admin/templates and that's final for every lawyer, every matter,
-- forever. The owner asked for the opposite: every lawyer should be able
-- to keep/redraft/delete any clause AND add a wholly custom one, for
-- their own matter only, without touching the shared template baseline
-- or any other lawyer's matter.
--
-- This table is strictly ADDITIVE per-matter override data, never a
-- replacement for template_clauses (the shared, service-role-only-write
-- reference baseline stays exactly as-is). app/services/contracts.py's
-- generate_draft() consults it (see that file's own comment) to decide,
-- per clause, whether to use the template's own current_text, this
-- matter's own edited text, skip a clause entirely, or append a
-- wholly custom one this matter's lawyer authored -- never mutating
-- template_clauses itself.
--
-- decision:
--   'kept'      -- use the template clause's own current_text unmodified
--                  (the default/absence of a row means the same thing;
--                  an explicit 'kept' row exists so a lawyer's choice is
--                  recorded even when it matches the baseline)
--   'modified'  -- use custom_text (this matter's own rewrite) instead
--   'deleted'   -- omit this clause from this matter's draft entirely
--   'custom'    -- a wholly new clause, not derived from any
--                  template_clauses row (template_clause_id NULL);
--                  custom_text is the lawyer-authored clause body,
--                  heading is the lawyer-supplied heading
--
-- Idempotent: safe to re-run (IF NOT EXISTS / DROP POLICY IF EXISTS).

CREATE TABLE IF NOT EXISTS public.matter_clause_customizations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    -- NULL for a 'custom' (wholly new, not template-derived) clause.
    template_clause_id uuid REFERENCES public.template_clauses(id) ON DELETE CASCADE,
    decision text NOT NULL CHECK (decision IN ('kept', 'modified', 'deleted', 'custom')),
    heading text,
    custom_text text,
    -- Ordering for 'custom' clauses relative to each other and to the
    -- template's own clauses; template-derived clauses keep the
    -- template's own display_order regardless of this column.
    display_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_matter_clause_customizations_matter
    ON public.matter_clause_customizations(matter_id);

-- A template clause gets at most one override per matter -- re-deciding
-- it (keep -> modify -> delete) updates the same row, never adds a
-- second conflicting one. A partial index (not a plain UNIQUE
-- constraint) so it only applies when template_clause_id IS NOT NULL --
-- 'custom' clauses (template_clause_id NULL) are exempt, a matter can
-- have many. Same idiom as idx_memberships_one_default_per_user
-- (0024_tenant_foundation.sql).
CREATE UNIQUE INDEX IF NOT EXISTS idx_matter_clause_customizations_one_per_template_clause
    ON public.matter_clause_customizations(matter_id, template_clause_id)
    WHERE template_clause_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.handle_matter_clause_customizations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_matter_clause_customizations_updated_at ON public.matter_clause_customizations;
CREATE TRIGGER set_matter_clause_customizations_updated_at
    BEFORE UPDATE ON public.matter_clause_customizations
    FOR EACH ROW EXECUTE FUNCTION public.handle_matter_clause_customizations_updated_at();

ALTER TABLE public.matter_clause_customizations ENABLE ROW LEVEL SECURITY;

-- Same org-member-all-via-matter-join pattern as court_case_tracking
-- (0025_litigation_intelligence_ecourts.sql) -- this is matter-owned
-- data, not shared reference data like template_clauses itself.
DROP POLICY IF EXISTS matter_clause_customizations_org_member_all ON public.matter_clause_customizations;
CREATE POLICY matter_clause_customizations_org_member_all ON public.matter_clause_customizations
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = matter_clause_customizations.matter_id AND mm.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            JOIN public.memberships mm ON mm.organization_id = m.organization_id
            WHERE m.id = matter_clause_customizations.matter_id AND mm.user_id = auth.uid()
        )
    );

-- Same shared-demo read extension as 0030 -- a customization on the
-- shared demo matter is visible read-only to every user, same as the
-- rest of that matter's data, never writable by anyone but its own org.
DROP POLICY IF EXISTS matter_clause_customizations_demo_read ON public.matter_clause_customizations;
CREATE POLICY matter_clause_customizations_demo_read ON public.matter_clause_customizations
    FOR SELECT USING (public.is_shared_demo_matter(matter_id));
