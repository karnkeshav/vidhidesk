-- Migration: 0019_rera_backend.sql
-- Description: RERA & Real Estate module backend — Phase 1.
--
-- Resolves three of the five documented RERA gaps at the schema level
-- (see docs/30_Implementation/Backlog.md and this sprint's brief):
--
--   1. RERA state-specific data model — rera_guides already existed
--      (migration 0001) but had no "procedure" dimension (a state has
--      MULTIPLE distinct RERA procedures: project registration, complaint
--      filing, extension application, etc. — the original schema only
--      supported one flat step list per state). Extended additively, not
--      replaced, per this sprint's "smallest justified schema extension"
--      instruction.
--   2. Explicit verification status on curated legal/procedural content
--      (rera_guides + state_rules) — previously only implicit via
--      source_url/last_verified being populated or not.
--   3. Walkthrough progress persistence — did not exist at all
--      (docs/30_Implementation/Backlog.md and this sprint's brief both
--      flag this as a known gap). New table, user-scoped (not
--      matter-scoped) per the product's own routing
--      (/rera/walkthrough/[state]/[procedure] carries no matterId segment
--      at all — see Navigation_and_Functional_Spec.md), with an OPTIONAL
--      matter_id so progress can still be associated with a specific RERA
--      matter when one exists, without requiring one.
--
-- Deliberately NOT creating: a RERA complaint table, a property deed
-- table, or a RERA case entity. Property deeds and RERA complaints reuse
-- the existing generic templates/template_clauses/draft_versions engine
-- (api/app/services/contracts.py::generate_draft, already module-agnostic
-- despite its filename — see RERA_BACKEND_INTEGRATION_CONTRACT.md for the
-- full reuse rationale) exactly the same way every Contracts template
-- does. No new table, no new drafting code path, no duplicate generic
-- entity — per CLAUDE.md's "do not create duplicate generic entities."
--
-- Idempotent: safe to re-run (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF
-- NOT EXISTS / DROP POLICY IF EXISTS before CREATE POLICY, matching the
-- convention migration 0015 established after TICKET-12).
--
-- NOT destructive: every rera_guides/state_rules change is an additive
-- column with a safe default; no column is dropped, renamed, or narrowed;
-- no existing row is modified by this migration (both tables have zero
-- production rows as of authoring — see RERA_BACKEND_INTEGRATION_CONTRACT.md
-- Runtime Verification section — but the migration does not assume that).

-- 1. rera_guides: add the procedure dimension + verification/portal fields ---
alter table public.rera_guides add column if not exists procedure text;
alter table public.rera_guides add column if not exists heading text;
alter table public.rera_guides add column if not exists required_documents text[] not null default '{}';
alter table public.rera_guides add column if not exists portal_url text;
alter table public.rera_guides add column if not exists warnings text;
alter table public.rera_guides add column if not exists verification_status text not null default 'unverified'
  check (verification_status in ('verified', 'pending_verification', 'unverified'));

-- Backfill: any pre-existing row (none expected in production — see above)
-- gets a placeholder procedure of 'general' rather than being left null,
-- since the new unique constraint below requires procedure to be non-null
-- for the (state, procedure, step_no) tuple to be meaningful.
update public.rera_guides set procedure = 'general' where procedure is null;
alter table public.rera_guides alter column procedure set not null;

drop index if exists rera_guides_state_procedure_step_uq;
create unique index rera_guides_state_procedure_step_uq
  on public.rera_guides (state, procedure, step_no);
create index if not exists rera_guides_state_procedure_idx
  on public.rera_guides (state, procedure);

-- RLS already exists on rera_guides (migration 0002_rls.sql,
-- rera_guides_read_authenticated — read-only for any authenticated user,
-- writes only via service role). Not modified here: this is shared
-- reference data, not user-owned, exactly like templates/statute_chunks.

-- 2. state_rules: same explicit verification_status, same reasoning -------
alter table public.state_rules add column if not exists verification_status text not null default 'unverified'
  check (verification_status in ('verified', 'pending_verification', 'unverified'));
-- Existing rows (seeded by the Contracts template seed scripts, which
-- always set source_url + last_verified) are backfilled to 'verified'
-- specifically — not left at the new column's 'unverified' default —
-- because they already carry a real source_url and last_verified date,
-- i.e. they already meet this migration's own definition of verified.
update public.state_rules set verification_status = 'verified'
  where source_url is not null and last_verified is not null and verification_status = 'unverified';

-- RLS already exists on state_rules (migration 0002_rls.sql,
-- state_rules_read_authenticated). Not modified here.

-- 3. rera_walkthrough_progress: new table, user-scoped ----------------------
-- Ownership is direct (user_id = auth.uid()), same pattern as `matters`
-- itself — not matter-derived, because matter_id is optional here (see
-- module docstring above for why: the walkthrough UI route carries no
-- matterId segment, so progress must be resumable without one).
create table if not exists public.rera_walkthrough_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  -- Optional association with a specific RERA matter — set null on
  -- matter deletion (never cascade-delete progress just because the
  -- matter that happened to be open at the time was later removed;
  -- the advocate's walkthrough progress is a distinct, independently
  -- meaningful record).
  matter_id uuid references public.matters(id) on delete set null,
  state text not null,
  procedure text not null,
  current_step_no int not null default 1,
  completed_step_ids uuid[] not null default '{}',
  is_complete boolean not null default false,
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One progress record per (user, state, procedure) when not tied to a
-- matter, and one per (user, state, procedure, matter) when it is — a
-- partial unique index each, since a plain UNIQUE(...) treats NULL
-- matter_id as always-distinct in Postgres (would silently allow
-- duplicate "no matter" progress rows for the same walkthrough).
drop index if exists rera_walkthrough_progress_user_global_uq;
create unique index rera_walkthrough_progress_user_global_uq
  on public.rera_walkthrough_progress (user_id, state, procedure)
  where matter_id is null;
drop index if exists rera_walkthrough_progress_user_matter_uq;
create unique index rera_walkthrough_progress_user_matter_uq
  on public.rera_walkthrough_progress (user_id, state, procedure, matter_id)
  where matter_id is not null;
create index if not exists rera_walkthrough_progress_user_idx
  on public.rera_walkthrough_progress (user_id);

alter table public.rera_walkthrough_progress enable row level security;

drop policy if exists rera_walkthrough_progress_owner_all on public.rera_walkthrough_progress;
create policy rera_walkthrough_progress_owner_all on public.rera_walkthrough_progress
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
