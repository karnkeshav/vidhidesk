-- Migration: 0016_case_analysis_model_routing.sql
-- Description: Sprint 3.6 Phase 4 (TICKET-20/21) — record actual model
-- used and expose fallback decisions for AI Case Analysis, not just the
-- new Pleading Outline feature (migration 0015). Additive column; existing
-- rows unaffected (model_routing will simply be null for anything
-- generated before this sprint).

ALTER TABLE public.litigation_case_analyses ADD COLUMN IF NOT EXISTS model_routing jsonb;
