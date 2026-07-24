-- VidhiDesk — Sprint 0 schema (TRD §4 tables + pii_masks)
-- Run in the Supabase SQL Editor (Project → SQL Editor → New query).
-- Idempotent: safe to re-run.

create extension if not exists vector;
create extension if not exists pgcrypto;

-- matters --------------------------------------------------------------
create table if not exists matters (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  client_name text,
  module text not null check (module in ('litigation', 'contracts', 'rera', 'consulting')),
  created_at timestamptz not null default now()
);
create index if not exists matters_user_id_idx on matters (user_id);

-- messages ---------------------------------------------------------------
-- Extends TRD's base columns with the audit fields Hard Rule 4 requires:
-- every AI output is stored with its prompt, model used, and retrieval
-- sources.
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references matters(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  model_used text,
  masked_prompt text,
  retrieval_sources jsonb,
  created_at timestamptz not null default now()
);
create index if not exists messages_matter_id_idx on messages (matter_id);

-- citations ----------------------------------------------------------------
-- Hard Rule 1: the renderer refuses to show a hyperlink unless ik_doc_id
-- is set here. status is 'verified' only when ik_doc_id is populated.
create table if not exists citations (
  id uuid primary key default gen_random_uuid(),
  case_name text not null,
  neutral_citation text,
  ik_doc_id text,
  ik_url text,
  court text,
  decided_on date,
  status text not null default 'unverified' check (status in ('verified', 'unverified')),
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  constraint citations_verified_has_doc_id
    check (status = 'unverified' or ik_doc_id is not null)
);
create unique index if not exists citations_case_court_uq
  on citations (lower(case_name), coalesce(court, ''));

-- templates ------------------------------------------------------------
create table if not exists templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text not null,
  schema_json jsonb not null,
  docx_path text,
  states_supported text[] not null default '{}',
  created_at timestamptz not null default now()
);

-- draft_versions ---------------------------------------------------------
create table if not exists draft_versions (
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references matters(id) on delete cascade,
  template_id uuid references templates(id),
  version_no int not null,
  docx_path text,
  change_summary text,
  created_at timestamptz not null default now(),
  unique (matter_id, version_no)
);

-- statute_chunks ---------------------------------------------------------
-- embedding dimension matches BAAI/bge-small-en-v1.5 (384-dim), per
-- CLAUDE.md's embeddings choice.
create table if not exists statute_chunks (
  id uuid primary key default gen_random_uuid(),
  act text not null,
  section_no text,
  year int,
  text text not null,
  embedding vector(384),
  created_at timestamptz not null default now()
);

-- state_rules --------------------------------------------------------------
create table if not exists state_rules (
  id uuid primary key default gen_random_uuid(),
  state text not null,
  instrument text not null,
  stamp_duty text,
  registration_req text,
  notes text,
  source_url text,
  last_verified date
);

-- rera_guides ------------------------------------------------------------
create table if not exists rera_guides (
  id uuid primary key default gen_random_uuid(),
  state text not null,
  step_no int not null,
  instruction text not null,
  source_url text,
  last_verified date
);

-- pii_masks --------------------------------------------------------------
-- CLAUDE.md Decision 4: masking map is stored per-matter, never sent to
-- the LLM. Only the backend (service role) reads/writes this table.
create table if not exists pii_masks (
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references matters(id) on delete cascade,
  placeholder text not null,
  real_value text not null,
  kind text not null,
  created_at timestamptz not null default now(),
  unique (matter_id, placeholder)
);
create index if not exists pii_masks_matter_id_idx on pii_masks (matter_id);
