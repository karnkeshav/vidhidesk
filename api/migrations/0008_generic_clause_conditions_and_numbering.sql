-- VidhiDesk — Sprint 2 Deliverable 2 prep: generalize clause inclusion
-- from NDA-specific "variant" matching to an arbitrary field/equals
-- condition (needed for Service Agreement's SLA toggle, and every future
-- template's own conditional clauses), plus assembly-time clause
-- numbering (needed because a conditionally-excluded clause shifts every
-- later clause's number — hardcoded numbers inside clause text break
-- under that, which NDA never exercised since its two variant clauses
-- always occupy the same position).
-- Run in the Supabase SQL Editor, after 0001-0007.
-- Idempotent: safe to re-run.

-- template_clauses: generic inclusion condition -----------------------------
-- Same shape as the frontend's field-visibility `condition` (IntakeField in
-- web/src/lib/api.ts): {"field": "...", "equals": ...} or
-- {"field": "...", "not_equals": ...}. Replaces applicable_variant (text,
-- exact-match against one hardcoded field name) — one condition mechanism,
-- not two competing ones.
alter table template_clauses
  add column if not exists applicable_condition jsonb;

update template_clauses
  set applicable_condition = jsonb_build_object('field', 'nda_variant', 'equals', applicable_variant)
  where applicable_variant is not null
    and applicable_condition is null;

alter table template_clauses
  drop column if exists applicable_variant;

-- template_clauses: heading, separate from body ------------------------------
-- The clause's heading text WITHOUT a leading number (e.g. "Definitions",
-- "Confidentiality Obligations") — null for clauses that render with no
-- heading line at all (NDA's recitals: unnumbered WHEREAS paragraphs).
-- generate_draft() prepends "{n}. " at assembly time, against the actual
-- variant/condition-filtered clause list, so numbering is always correct
-- regardless of which conditional clauses ended up included. Sub-numbering
-- *within* a clause's own body (e.g. Definitions' "1.1", "1.2") is still
-- hand-authored, not auto-derived — a known limitation (see
-- docs/lessons_learned.md) that holds only because no clause with internal
-- sub-numbers currently sits after a conditionally-excludable clause.
alter table template_clauses
  add column if not exists heading text;
