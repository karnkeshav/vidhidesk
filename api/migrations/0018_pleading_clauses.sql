-- Migration: 0018_pleading_clauses.sql
-- Description: Sprint 3.6 Phase 2 — Clause-Based Drafting Engine.
-- Creates litigation_pleading_clauses (one row per clause GENERATION, not
-- per clause type — every regeneration is a new immutable version, same
-- convention as litigation_case_analyses/litigation_pleading_outlines) and
-- litigation_pleading_drafts (a composed pleading assembled from a
-- specific set of clause versions, with full traceability back to which
-- version of each clause was used).
--
-- Architectural guarantee this sprint's brief requires in the schema, not
-- just in code: "changing one clause must never regenerate the whole
-- document." Each clause_type's versions are independent rows keyed by
-- (matter_id, pleading_outline_id, clause_type, version_no) — regenerating
-- "Facts" only inserts a new litigation_pleading_clauses row for
-- clause_type='facts'; every other clause_type's rows are untouched. The
-- composer (document_composer.py) reads whichever version of each clause
-- is currently review_status='approved' at compose time — it does not
-- regenerate anything itself (see its own module docstring: "no legal
-- reasoning").
--
-- clause_type is intentionally NOT an enum: Postgres enums require a
-- migration to add a value, which would violate "changing one clause must
-- never regenerate the whole document" at the schema-evolution level too.
-- Application-level validation (clause_generator.py::CLAUSE_TYPES) is the
-- single source of truth for the fixed 14-type list, matching the
-- FIXED_PLEADING_SECTIONS convention pleading_outline.py already
-- established for its own fixed section list.

CREATE TABLE IF NOT EXISTS public.litigation_pleading_clauses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    pleading_outline_id uuid NOT NULL REFERENCES public.litigation_pleading_outlines(id) ON DELETE RESTRICT,
    clause_type text NOT NULL,
    version_no integer NOT NULL,

    -- Structured clause output. `text` is the clause's rendered content;
    -- `bullet_items` holds list-shaped content (Chronology entries, Prayer
    -- items, Annexure entries) alongside `text` so the composer can render
    -- either a paragraph or a numbered list without re-deriving structure
    -- from prose. Never drafted freeform beyond what the generator itself
    -- produced — the composer only assembles this field, never edits it.
    content jsonb NOT NULL DEFAULT '{}',

    -- Every statute/case-law reference this clause relies on, cross-checked
    -- the same way case_analysis.py/pleading_outline.py already do
    -- (grounded: true/false, never silently trusted or dropped —
    -- CLAUDE.md Hard Rule 3) or Citation-Verifier-gated (Hard Rule 1).
    statute_refs jsonb NOT NULL DEFAULT '[]',
    case_law_refs jsonb NOT NULL DEFAULT '[]',

    -- confidence: 0.0-1.0. For a deterministic clause this is always 1.0
    -- (assembled from already-verified/already-reviewed data, no synthesis
    -- risk). For an LLM clause this is the grounding ratio (fraction of
    -- claimed statute/case-law refs that verified/grounded) when the
    -- clause claims any refs, else the model's own self-reported
    -- confidence — see clause_generator.py::_confidence_for.
    confidence numeric NOT NULL DEFAULT 1.0,
    is_deterministic boolean NOT NULL DEFAULT false,

    -- Versioning fields the sprint brief requires explicitly.
    model_used text,
    model_routing jsonb,
    prompt_version text NOT NULL DEFAULT 'v1',
    regenerated boolean NOT NULL DEFAULT false,
    author text NOT NULL DEFAULT 'ai',
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
    reviewed_at timestamptz,

    masked_prompt text,
    generation_warning text,
    created_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE (matter_id, pleading_outline_id, clause_type, version_no)
);

CREATE INDEX IF NOT EXISTS idx_litigation_pleading_clauses_lookup
    ON public.litigation_pleading_clauses(matter_id, pleading_outline_id, clause_type, version_no DESC);
CREATE INDEX IF NOT EXISTS idx_litigation_pleading_clauses_review
    ON public.litigation_pleading_clauses(pleading_outline_id, clause_type, review_status);

ALTER TABLE public.litigation_pleading_clauses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS litigation_pleading_clauses_select_owner ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_select_owner ON public.litigation_pleading_clauses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_clauses.matter_id
              AND m.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS litigation_pleading_clauses_insert_owner ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_insert_owner ON public.litigation_pleading_clauses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_clauses.matter_id
              AND m.user_id = auth.uid()
        )
    );

-- Update is restricted to review fields only at the application layer
-- (clause_generator.py::review_clause never touches content/version_no);
-- allowed here so a human review decision doesn't require a whole new
-- version row, unlike content itself which is always immutable-per-version.
DROP POLICY IF EXISTS litigation_pleading_clauses_update_owner ON public.litigation_pleading_clauses;
CREATE POLICY litigation_pleading_clauses_update_owner ON public.litigation_pleading_clauses
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_clauses.matter_id
              AND m.user_id = auth.uid()
        )
    );

-- Composed pleadings: an assembly of whichever clause versions were
-- review_status='approved' at compose time. Immutable once created
-- (recomposing after a clause changes creates a new version, same
-- convention as every other artifact in this pipeline) — never updated in
-- place, so a previously-shown draft can never silently change underneath
-- an advocate who already has it open.
CREATE TABLE IF NOT EXISTS public.litigation_pleading_drafts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    pleading_outline_id uuid NOT NULL REFERENCES public.litigation_pleading_outlines(id) ON DELETE RESTRICT,
    version_no integer NOT NULL,

    -- Full traceability: exactly which clause row (and therefore which
    -- version, model, prompt_version) contributed each section of this
    -- composition — the composer's only real output besides the assembled
    -- text itself.
    clause_versions jsonb NOT NULL DEFAULT '[]',
    composed_sections jsonb NOT NULL DEFAULT '[]',
    missing_clauses jsonb NOT NULL DEFAULT '[]',

    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, pleading_outline_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_litigation_pleading_drafts_lookup
    ON public.litigation_pleading_drafts(matter_id, pleading_outline_id, version_no DESC);

ALTER TABLE public.litigation_pleading_drafts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS litigation_pleading_drafts_select_owner ON public.litigation_pleading_drafts;
CREATE POLICY litigation_pleading_drafts_select_owner ON public.litigation_pleading_drafts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_drafts.matter_id
              AND m.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS litigation_pleading_drafts_insert_owner ON public.litigation_pleading_drafts;
CREATE POLICY litigation_pleading_drafts_insert_owner ON public.litigation_pleading_drafts
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_drafts.matter_id
              AND m.user_id = auth.uid()
        )
    );
