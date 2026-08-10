-- Migration: 0015_pleading_outlines.sql
-- Description: Sprint 3.6 Phase 1 — AI Pleading Generation foundation.
-- Creates litigation_pleading_outlines: a versioned, STRUCTURED PLAN for a
-- pleading (legal issues -> applicable statutes -> applicable case law ->
-- cause of action -> reliefs -> jurisdiction -> limitation -> evidence
-- mapping -> pleading outline), explicitly NOT a drafted pleading document.
-- Per this sprint's brief ("Do NOT generate complete pleadings yet.
-- Generate only structured pleading plans.") and ADR-011/ADR-002 (fixed
-- document structure, LLM never invents whole-document structure), a real
-- prose pleading is out of scope until a future sprint builds the
-- Jinja2-skeleton drafting layer on top of this table's output.
--
-- Reuses the immutable, auto-incrementing per-matter versioning pattern
-- litigation_case_analyses (migration 0014) established, applied to a new
-- artifact type one step further downstream. An outline is always built
-- FROM a specific, already-reviewed litigation_case_analyses row (never
-- re-derived independently from raw facts) — case_analysis_id is NOT
-- NULL and not just a loose foreign key, it is the architectural
-- guarantee that pleading planning stays downstream of, and consistent
-- with, what the advocate already reviewed and signed off on.

CREATE TABLE IF NOT EXISTS public.litigation_pleading_outlines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    case_analysis_id uuid NOT NULL REFERENCES public.litigation_case_analyses(id) ON DELETE RESTRICT,
    version_no integer NOT NULL,

    -- Deterministic / passed-through sections (same trust boundary as
    -- litigation_case_analyses: never LLM-generated, verbatim from the
    -- source case analysis row or plain derivation of it).
    jurisdiction_summary jsonb,
    limitation_summary jsonb,
    applicable_statutes jsonb NOT NULL DEFAULT '[]',

    -- LLM-synthesized planning sections (single masked generate() call,
    -- task_type "pleading_planner"). Every statute reference inside
    -- cause_of_action is cross-checked against applicable_statutes and
    -- flagged (grounded: true/false), same convention as
    -- litigation_case_analyses.possible_causes_of_action — never silently
    -- trusted or dropped (CLAUDE.md Hard Rule 3).
    legal_issues jsonb NOT NULL DEFAULT '[]',
    cause_of_action jsonb NOT NULL DEFAULT '[]',
    reliefs_sought jsonb NOT NULL DEFAULT '[]',
    evidence_mapping jsonb NOT NULL DEFAULT '[]',

    -- The structured plan itself: an ordered list of {section, content_plan}
    -- objects describing what each eventual pleading section will need to
    -- cover — never prose paragraphs, never the pleading text itself.
    -- Enforced in code (pleading_outline.py), not just by convention: see
    -- _validate_outline_is_structured().
    pleading_outline jsonb NOT NULL DEFAULT '[]',

    -- Any case law the model mentions is verified through the Citation
    -- Verifier before storage — this column holds the post-verification
    -- result, never the model's raw claim (same convention as
    -- litigation_case_analyses.possible_precedents).
    applicable_case_law jsonb NOT NULL DEFAULT '[]',

    -- Auditability (CLAUDE.md Hard Rule 4): every AI output stored with
    -- its prompt, model used, and retrieval sources. model_used additionally
    -- carries the Sprint 3.6 Phase 4 model-routing-transparency fields
    -- (requested_model / actual_model / degraded) rather than just a bare
    -- provider/model string — see app/services/llm_gateway.py.
    model_used text,
    model_routing jsonb,
    masked_prompt text,
    retrieval_sources jsonb NOT NULL DEFAULT '[]',
    generation_warning text,

    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_litigation_pleading_outlines_matter
    ON public.litigation_pleading_outlines(matter_id, version_no DESC);
CREATE INDEX IF NOT EXISTS idx_litigation_pleading_outlines_case_analysis
    ON public.litigation_pleading_outlines(case_analysis_id);

ALTER TABLE public.litigation_pleading_outlines ENABLE ROW LEVEL SECURITY;

-- Select + insert only — outline rows are immutable versions, same
-- convention as litigation_case_analyses / draft_versions (a regeneration
-- creates a new row, never updates or deletes a prior one). Unlike
-- migrations 0011/0013/0014 (TICKET-12), DROP POLICY IF EXISTS precedes
-- every CREATE POLICY here so this migration is safely re-runnable.
DROP POLICY IF EXISTS litigation_pleading_outlines_select_owner ON public.litigation_pleading_outlines;
CREATE POLICY litigation_pleading_outlines_select_owner ON public.litigation_pleading_outlines
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_outlines.matter_id
              AND m.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS litigation_pleading_outlines_insert_owner ON public.litigation_pleading_outlines;
CREATE POLICY litigation_pleading_outlines_insert_owner ON public.litigation_pleading_outlines
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_pleading_outlines.matter_id
              AND m.user_id = auth.uid()
        )
    );
