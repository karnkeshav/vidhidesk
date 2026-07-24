-- VidhiDesk — Sprint 2 prep: full-text keyword search over chunk_text.
-- Run after 0005_case_name_normalization.sql.
--
-- Process note (per the rule established after the 0004 grant incident):
-- every statement below is purely additive — ADD COLUMN IF NOT EXISTS,
-- CREATE INDEX IF NOT EXISTS, and a CREATE OR REPLACE FUNCTION for a
-- function name that has never existed before. Nothing here drops and
-- recreates an existing object (that combination is what let the stale
-- PUBLIC grant survive on 0004), so this is safe to apply as a single
-- block — no need to split or go statement-by-statement.

alter table statute_chunks
  add column if not exists text_search tsvector
    generated always as (to_tsvector('english', text)) stored;

create index if not exists statute_chunks_text_search_idx
  on statute_chunks using gin (text_search);

-- Full-text search RPC, mirroring match_statute_chunks (0004) for the
-- same reason: PostgREST's fts/wfts filter operators can test whether a
-- row matches (`@@`), but the query builder has no way to order by an
-- expression like ts_rank(...) — relevance-ranked full-text search needs
-- its own RPC the same way cosine-ranked vector search does.
create or replace function search_statute_chunks_fulltext(
  query_text text,
  match_count int default 5
)
returns table (
  id uuid,
  act text,
  section_no text,
  year int,
  text text,
  rank float
)
language sql stable
set search_path = public, pg_temp
as $$
  select
    statute_chunks.id,
    statute_chunks.act,
    statute_chunks.section_no,
    statute_chunks.year,
    statute_chunks.text,
    ts_rank(statute_chunks.text_search, websearch_to_tsquery('english', query_text)) as rank
  from statute_chunks
  where statute_chunks.text_search @@ websearch_to_tsquery('english', query_text)
  order by rank desc
  limit match_count;
$$;

-- Same least-privilege posture as match_statute_chunks — and the same
-- fix, hardened further: revoking from PUBLIC alone was NOT sufficient
-- (confirmed live on this exact function). Supabase provisions every
-- project with `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE
-- ON FUNCTIONS TO anon, authenticated, service_role` — anon's access is
-- a *direct* grant made automatically at CREATE FUNCTION time, separate
-- from and in addition to vanilla Postgres's PUBLIC-default grant.
-- Revoking from PUBLIC only strips the generic-Postgres path; the
-- Supabase-provisioned direct grant to anon survives untouched unless
-- revoked explicitly, by name, every time. Both revokes are therefore
-- mandatory for every function this project creates, not just one or
-- the other.
revoke execute on function search_statute_chunks_fulltext(text, int) from public;
revoke execute on function search_statute_chunks_fulltext(text, int) from anon;
grant execute on function search_statute_chunks_fulltext(text, int) to authenticated, service_role;
