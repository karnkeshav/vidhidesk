-- Migration: 0014_litigation_case_analysis.sql
-- Description: Sprint 3.5.3 — End-to-End Advocate Experience vertical slice.
-- (1) Adds file-attachment columns to litigation_facts_evidence so "Upload
--     Evidence" is a real document, not just a text label.
-- (2) Creates litigation_case_analyses: versioned AI Case Analysis output.
--     Reuses the immutable, auto-incrementing per-matter versioning pattern
--     established by draft_versions (see
--     api/app/services/contracts.py::_next_version_no) applied to a new
--     artifact type — structured legal analysis, not a docx draft. See
--     docs/30_Implementation/ADR/ADR-011-ai-case-analysis-before-pleading.md.

-- 1. Evidence file attachment columns (additive; existing rows unaffected)
ALTER TABLE public.litigation_facts_evidence ADD COLUMN IF NOT EXISTS file_url text;
ALTER TABLE public.litigation_facts_evidence ADD COLUMN IF NOT EXISTS file_name text;
ALTER TABLE public.litigation_facts_evidence ADD COLUMN IF NOT EXISTS file_size_bytes bigint;
ALTER TABLE public.litigation_facts_evidence ADD COLUMN IF NOT EXISTS mime_type text;

-- 2. litigation_case_analyses
CREATE TABLE IF NOT EXISTS public.litigation_case_analyses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    version_no integer NOT NULL,

    -- Deterministic sections (never LLM-generated; either passed through
    -- from the Limitation Engine / Forum Advisor / RAG Retriever verbatim,
    -- or derived by plain sorting/filtering of matter data).
    chronological_facts jsonb NOT NULL DEFAULT '[]',
    jurisdiction_summary jsonb,
    limitation_summary jsonb,
    applicable_statutes jsonb NOT NULL DEFAULT '[]',

    -- LLM-synthesized sections (single masked generate() call, task_type
    -- "case_analyst"; statutes_relied_upon inside possible_causes_of_action
    -- is cross-checked against applicable_statutes and flagged, never
    -- silently trusted or silently dropped — Statute Grounding hard rule).
    matter_summary text,
    missing_information jsonb NOT NULL DEFAULT '[]',
    possible_causes_of_action jsonb NOT NULL DEFAULT '[]',
    potential_risks jsonb NOT NULL DEFAULT '[]',
    evidence_gaps jsonb NOT NULL DEFAULT '[]',
    recommended_next_steps jsonb NOT NULL DEFAULT '[]',

    -- Any case law the model mentions is verified through the Citation
    -- Verifier (api/app/services/citations.py) before storage — this column
    -- holds the post-verification result, never the model's raw claim.
    possible_precedents jsonb NOT NULL DEFAULT '[]',

    -- Auditability (CLAUDE.md Hard Rule 4): every AI output stored with
    -- its prompt, model used, and retrieval sources.
    model_used text,
    masked_prompt text,
    retrieval_sources jsonb NOT NULL DEFAULT '[]',
    generation_warning text,

    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (matter_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_litigation_case_analyses_matter
    ON public.litigation_case_analyses(matter_id, version_no DESC);

ALTER TABLE public.litigation_case_analyses ENABLE ROW LEVEL SECURITY;

-- Select + insert only — analysis rows are immutable versions, same
-- convention as draft_versions (a regeneration creates a new row, never
-- updates or deletes a prior one).
CREATE POLICY litigation_case_analyses_select_owner ON public.litigation_case_analyses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_case_analyses.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_case_analyses_insert_owner ON public.litigation_case_analyses
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_case_analyses.matter_id
              AND m.user_id = auth.uid()
        )
    );
