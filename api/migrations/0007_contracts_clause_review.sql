-- VidhiDesk — Sprint 2 schema: Contracts template engine, clause-review
-- workflow, and per-draft clause-fill audit trail.
-- Run in the Supabase SQL Editor, after 0001-0006.
-- Idempotent: safe to re-run.

-- templates: beta-labelling (Project_Plan §6.4) ----------------------------
-- A template ships "beta — pending clause review" until every one of its
-- template_clauses rows has moved past 'unreviewed'. This is a plain
-- column (not derived) so the frontend badge is a cheap read, not a join +
-- aggregate on every template-list render; the clause-review endpoint
-- (app-level, not a trigger) is responsible for flipping it once the last
-- clause clears review.
alter table templates
  add column if not exists review_status text not null default 'beta'
    check (review_status in ('beta', 'reviewed'));

-- templates: stable URL/route slug ------------------------------------------
-- Added while wiring the frontend (Sprint 2 Deliverable 1): the admin
-- clause-review screen and the contracts picker both need a stable,
-- human-readable key ("nda") to route on instead of the uuid — schema_json
-- already carried a "template_key" field for this from the start, this
-- just promotes it to a real, indexable column.
alter table templates
  add column if not exists template_key text;

create unique index if not exists templates_template_key_uq
  on templates (template_key) where template_key is not null;

-- template_clauses ----------------------------------------------------------
-- One row per named clause block inside a template's docxtpl skeleton.
-- clause_type distinguishes boilerplate (never touches the LLM) from
-- bespoke slots the gateway fills per matter. applicable_variant scopes a
-- clause to one template sub-variant (e.g. NDA's mutual vs one_way) —
-- null means it applies to every variant of this template.
create table if not exists template_clauses (
  id uuid primary key default gen_random_uuid(),
  template_id uuid not null references templates(id) on delete cascade,
  clause_key text not null,
  display_order int not null,
  clause_type text not null check (clause_type in ('fixed_boilerplate', 'llm_fillable')),
  applicable_variant text,
  source_text text not null,
  current_text text not null,
  review_status text not null default 'unreviewed'
    check (review_status in ('unreviewed', 'kept', 'redrafted', 'deleted')),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (template_id, clause_key)
);
create index if not exists template_clauses_template_id_idx
  on template_clauses (template_id);

-- clause_reviews -------------------------------------------------------------
-- Append-only audit trail behind template_clauses' denormalized
-- review_status/current_text (same pattern as citations' verified_at:
-- one durable log, one fast-read summary field kept in sync by the
-- backend endpoint that writes both in one transaction — see
-- app/routers/contracts.py). Nitesh may redraft a clause more than once;
-- every decision is kept, not overwritten.
--
-- TICKET-4 (Sprint 3, filed 2026-08-02 from a live audit sweep): a
-- clause's review_status can go stale silently — re-seeding a template
-- (scripts/seed_*_template.py) only ever writes source_text/current_text,
-- never review_status, so a clause reviewed and marked 'kept' keeps that
-- badge even after its actual text is substantively rewritten underneath
-- it. Caught live: NDA's recitals clause was reviewed 'kept' on
-- 2026-08-01, then the party-names bug fix rewrote its source_text later
-- that same day, and review_status still read 'kept' until an audit
-- sweep found it (see docs/lessons_learned.md's "re-seeding a clause
-- does not clear a prior review" entry). Proposed Sprint 3 fix: add a
-- `content_hash text` column here, recording a hash of
-- template_clauses.current_text at the moment of review; any template
-- list/detail view can then flag review_status='kept' rows where
-- content_hash no longer matches the clause's current current_text hash
-- — "reviewed against different content" — without auto-invalidating on
-- every trivial rewording (a decision that stays a human call, not an
-- automatic reset, per the same lessons-learned entry).
create table if not exists clause_reviews (
  id uuid primary key default gen_random_uuid(),
  clause_id uuid not null references template_clauses(id) on delete cascade,
  decision text not null check (decision in ('keep', 'redraft', 'delete')),
  redraft_text text,
  reviewer_notes text,
  created_at timestamptz not null default now(),
  constraint clause_reviews_redraft_has_text
    check (decision <> 'redraft' or redraft_text is not null),
  constraint clause_reviews_delete_has_notes
    check (decision <> 'delete' or reviewer_notes is not null)
);
create index if not exists clause_reviews_clause_id_idx
  on clause_reviews (clause_id);

-- draft_clause_fills ----------------------------------------------------------
-- CLAUDE.md Hard Rule 4 (auditability) applied at clause granularity: the
-- per-matter, per-draft-version LLM output for a bespoke clause, plus what
-- produced it. One row per llm_fillable clause actually filled for a given
-- draft_versions row — fixed_boilerplate clauses never call the LLM, so
-- they never appear here. `prompt` is the MASKED prompt actually sent to
-- the gateway (PARTY_A/ADDR_1 placeholders) — never raw client PII; the
-- real mapping lives only in pii_masks, per CLAUDE.md Decision 4.
create table if not exists draft_clause_fills (
  id uuid primary key default gen_random_uuid(),
  draft_version_id uuid not null references draft_versions(id) on delete cascade,
  template_clause_id uuid not null references template_clauses(id),
  generated_text text not null,
  prompt text not null,
  model_used text not null,
  retrieval_sources_json jsonb,
  created_at timestamptz not null default now()
);
create index if not exists draft_clause_fills_draft_version_id_idx
  on draft_clause_fills (draft_version_id);

-- RLS ------------------------------------------------------------------------
-- template_clauses / clause_reviews: shared reference + review-audit data,
-- same posture as templates itself (0002_rls.sql) — any authenticated user
-- (single lawyer) reads; only the service role writes, via the backend's
-- clause-review endpoint.
alter table template_clauses enable row level security;
drop policy if exists template_clauses_read_authenticated on template_clauses;
create policy template_clauses_read_authenticated on template_clauses
  for select
  using (auth.role() = 'authenticated');

alter table clause_reviews enable row level security;
drop policy if exists clause_reviews_read_authenticated on clause_reviews;
create policy clause_reviews_read_authenticated on clause_reviews
  for select
  using (auth.role() = 'authenticated');

-- draft_clause_fills: matter-scoped like draft_versions/messages
-- (0002_rls.sql) — owner-only, via the parent draft_versions -> matters
-- chain.
alter table draft_clause_fills enable row level security;
drop policy if exists draft_clause_fills_owner_all on draft_clause_fills;
create policy draft_clause_fills_owner_all on draft_clause_fills
  for all
  using (exists (
    select 1 from draft_versions dv
    join matters m on m.id = dv.matter_id
    where dv.id = draft_clause_fills.draft_version_id and m.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from draft_versions dv
    join matters m on m.id = dv.matter_id
    where dv.id = draft_clause_fills.draft_version_id and m.user_id = auth.uid()
  ));
