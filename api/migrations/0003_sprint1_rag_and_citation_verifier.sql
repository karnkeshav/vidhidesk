-- VidhiDesk — Sprint 1 schema changes (Statute RAG + Citation Verifier v2)
-- Run in the Supabase SQL Editor, after 0001_schema.sql and 0002_rls.sql.
-- Idempotent: safe to re-run.

-- statute_chunks: idempotent ingestion needs a natural key ----------------
-- (act, section_no) per CLAUDE.md's ingestion spec ("act_name, section_no"
-- — this table's existing columns are named act/text per TRD §4; the
-- ingestion script maps its act_name/chunk_text fields onto these).
-- A section can legitimately repeat across acts (e.g. every act has a
-- "Section 1"), so the natural key is the pair, not section_no alone.
alter table statute_chunks
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists statute_chunks_act_section_uq
  on statute_chunks (act, section_no);

-- HNSW over ivfflat: it builds incrementally and doesn't need "lists"
-- tuned against an existing data volume, which matters here because this
-- migration runs *before* any ingestion — an ivfflat index built against
-- zero rows would cluster badly once data lands.
create index if not exists statute_chunks_embedding_hnsw_idx
  on statute_chunks using hnsw (embedding vector_cosine_ops);

-- Keyword search side of the hybrid retriever (act name + section number).
create index if not exists statute_chunks_act_trgm_idx
  on statute_chunks using gin (act gin_trgm_ops);
create extension if not exists pg_trgm;

-- citations: TRD §3.3 cache key + tid-based verification + staleness ------
-- Sprint 0's cache key was (case_name, court); Sprint 1's Citation
-- Verifier spec keys on (case_name_normalized, neutral_citation) instead,
-- because the verifier's own retry logic already varies court within a
-- single case_name (first-pass has a court filter, retry-pass doesn't) —
-- keying on court would cache the two passes as different citations.
drop index if exists citations_case_court_uq;

alter table citations
  add column if not exists case_name_normalized text
    generated always as (lower(trim(case_name))) stored,
  add column if not exists stale boolean not null default false,
  add column if not exists last_checked_at timestamptz;

create unique index if not exists citations_normalized_uq
  on citations (case_name_normalized, coalesce(neutral_citation, ''));

comment on column citations.ik_doc_id is
  'Must be the tid from GET /doc/{id}/, not the docid from /search/ results — '
  'the canonical https://indiankanoon.org/doc/{ik_doc_id}/ URL resolves against '
  'tid. Confirmed diverging for statute documents in the Sprint 0 IK spike.';
comment on column citations.stale is
  'Set by the nightly dead-link job when a verified ik_url stops returning 200. '
  'Never deleted — the renderer gate checks status=''verified'' AND NOT stale.';
