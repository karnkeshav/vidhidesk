-- VidhiDesk — Sprint 1 deliverable 2: vector search RPC function.
-- Run after 0003_sprint1_rag_and_citation_verifier.sql.
-- Idempotent: safe to re-run (create or replace).

-- PostgREST's query builder has no way to express pgvector's `<=>`
-- distance operator, so the vector half of the hybrid retriever calls
-- this function via Supabase RPC instead of .select().
create or replace function match_statute_chunks(
  query_embedding vector(384),
  match_count int default 5
)
returns table (
  id uuid,
  act text,
  section_no text,
  year int,
  text text,
  similarity float
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
    1 - (statute_chunks.embedding <=> query_embedding) as similarity
  from statute_chunks
  where statute_chunks.embedding is not null
  order by statute_chunks.embedding <=> query_embedding
  limit match_count;
$$;

-- Postgres grants EXECUTE to PUBLIC by default when a function is
-- created, and every role (including anon) is implicitly a member of
-- PUBLIC — so without an explicit revoke here, anon's access survives
-- untouched no matter what the GRANT line below says. CREATE OR REPLACE
-- FUNCTION does not reset existing permissions, so this revoke has to be
-- unconditional and re-run every time for the migration to be idempotent
-- regardless of the function's prior grant state.
revoke execute on function match_statute_chunks(vector, int) from public;

-- No grant to anon: it has no legitimate reason to call this, and RLS on
-- statute_chunks would block it from seeing rows anyway — but "harmless"
-- isn't a reason to grant it. Least privilege.
grant execute on function match_statute_chunks(vector, int) to authenticated, service_role;
