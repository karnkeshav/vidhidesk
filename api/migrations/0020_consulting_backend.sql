-- Migration: 0020_consulting_backend.sql
-- Description: Consulting & Legal Research module backend — Phase 1.
--
-- Creates consulting_analyses: versioned, structured Consulting analysis
-- output. Directly mirrors the litigation_case_analyses pattern
-- (migration 0014) — same immutable, auto-incrementing per-matter
-- versioning (api/app/services/consulting.py::_next_version_no, same
-- convention as case_analysis.py/document_composer.py/contracts.py), same
-- deterministic-vs-LLM-generated column split, same RLS shape.
--
-- Deliberately NOT creating a "consulting_cases" or "consulting_matters"
-- table: Consulting matters are plain `matters` rows with module =
-- 'consulting' (already a valid value in the matters.module CHECK
-- constraint since migration 0001 — see MODULES in
-- api/app/models/schemas.py). No new matter/case entity is needed.
--
-- Deliberately NOT touching the existing `messages` table: Consulting's
-- structured, versioned, grounded analysis output does not fit a plain
-- (role, content) chat row any more than litigation_case_analyses did —
-- same reasoning as migration 0014's own rationale. The generic
-- POST/GET /api/matters/{id}/messages endpoints remain available,
-- unmodified, for free-form chat within a Consulting matter if the
-- frontend chooses to use them; this table is additive, not a
-- replacement.
--
-- Idempotent: safe to re-run (CREATE TABLE IF NOT EXISTS, DROP POLICY IF
-- EXISTS before CREATE POLICY).
-- NOT destructive: no existing table, column, or row is altered.

CREATE TABLE IF NOT EXISTS public.consulting_analyses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    version_no integer NOT NULL,

    -- The question this version answers. Version 1 is the matter's
    -- opening question; version 2+ is a follow-up question within the
    -- SAME matter (per the product's explicit "do not create a new
    -- matter for every follow-up" requirement). Stored unmasked, same
    -- convention as messages.content — the advocate's own record of
    -- what they asked, per _build_history's documented rationale in
    -- app/routers/matters.py.
    question text NOT NULL,

    -- Deterministic-vs-LLM split (CLAUDE.md Hard Rule 3 / Statute
    -- Grounding): applicable_law entries carry a `grounded` boolean set
    -- by cross-checking each LLM-claimed (act, section_no) against the
    -- RAG Retriever's actually-retrieved chunks — identical pattern to
    -- litigation_case_analyses.possible_causes_of_action's
    -- statutes_relied_upon. Never silently trusted, never silently
    -- dropped.
    applicable_law jsonb NOT NULL DEFAULT '[]',

    -- correct_forum / limitation_period: populated from the existing
    -- deterministic Forum Advisor (app/services/forum.py::determine_forum)
    -- / Limitation Calculator (app/services/limitation.py::calculate_limitation)
    -- when the caller supplies their output (same "caller-computed,
    -- passed-through verbatim" pattern as
    -- litigation_case_analyses.jurisdiction_summary/limitation_summary).
    -- When not supplied, holds the LLM's own advisory-only estimate,
    -- explicitly flagged non-deterministic in the JSON payload itself
    -- (never silently presented as equivalent to the rule-based result).
    correct_forum jsonb,
    limitation_period jsonb,

    -- LLM-synthesized sections (single masked generate() call, task_type
    -- "consulting_analyst").
    remedies_available jsonb NOT NULL DEFAULT '[]',
    missing_information jsonb NOT NULL DEFAULT '[]',

    -- Every case name the model proposes is verified through the
    -- Citation Verifier (api/app/services/citations.py) before storage —
    -- this column holds the post-verification result, never the model's
    -- raw claim. Same shape/rule as litigation_case_analyses.possible_precedents.
    case_law_references jsonb NOT NULL DEFAULT '[]',

    -- Auditability (CLAUDE.md Hard Rule 4).
    model_used text,
    masked_prompt text,
    retrieval_sources jsonb NOT NULL DEFAULT '[]',
    generation_warning text,

    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_consulting_analyses_matter
    ON public.consulting_analyses(matter_id, version_no DESC);

ALTER TABLE public.consulting_analyses ENABLE ROW LEVEL SECURITY;

-- Select + insert only — analysis rows are immutable versions, same
-- convention as litigation_case_analyses / draft_versions /
-- litigation_pleading_drafts (no UPDATE policy anywhere in this family:
-- a regeneration creates a new row, never overwrites a prior one).
DROP POLICY IF EXISTS consulting_analyses_select_owner ON public.consulting_analyses;
CREATE POLICY consulting_analyses_select_owner ON public.consulting_analyses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = consulting_analyses.matter_id
              AND m.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS consulting_analyses_insert_owner ON public.consulting_analyses;
CREATE POLICY consulting_analyses_insert_owner ON public.consulting_analyses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = consulting_analyses.matter_id
              AND m.user_id = auth.uid()
        )
    );
