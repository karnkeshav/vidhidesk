-- VidhiDesk — RLS policies (CLAUDE.md: "only the owning user reads their
-- matters"). Run after 0001_schema.sql, in the Supabase SQL Editor.
-- Idempotent: drops+recreates each policy so it's safe to re-run.

-- matters: strictly owner-only ------------------------------------------
alter table matters enable row level security;

drop policy if exists matters_owner_all on matters;
create policy matters_owner_all on matters
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- messages: owner-only via the parent matter ------------------------------
alter table messages enable row level security;

drop policy if exists messages_owner_all on messages;
create policy messages_owner_all on messages
  for all
  using (exists (
    select 1 from matters m where m.id = messages.matter_id and m.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from matters m where m.id = messages.matter_id and m.user_id = auth.uid()
  ));

-- draft_versions: owner-only via the parent matter ------------------------
alter table draft_versions enable row level security;

drop policy if exists draft_versions_owner_all on draft_versions;
create policy draft_versions_owner_all on draft_versions
  for all
  using (exists (
    select 1 from matters m where m.id = draft_versions.matter_id and m.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from matters m where m.id = draft_versions.matter_id and m.user_id = auth.uid()
  ));

-- pii_masks: no direct client access at all -------------------------------
-- The masking map is only ever read/written by the backend using the
-- service-role key (which bypasses RLS). No policy is created for the
-- anon/authenticated roles, so PostgREST denies all access to this table
-- from the frontend even for the owning user — it exists purely to let
-- the LLM gateway unmask its own output.
alter table pii_masks enable row level security;

-- citations / templates / statute_chunks / state_rules / rera_guides:
-- shared reference data, not user-owned. Any authenticated user (single
-- lawyer, per CLAUDE.md) can read; only the service role can write.
alter table citations enable row level security;
drop policy if exists citations_read_authenticated on citations;
create policy citations_read_authenticated on citations
  for select
  using (auth.role() = 'authenticated');

alter table templates enable row level security;
drop policy if exists templates_read_authenticated on templates;
create policy templates_read_authenticated on templates
  for select
  using (auth.role() = 'authenticated');

alter table statute_chunks enable row level security;
drop policy if exists statute_chunks_read_authenticated on statute_chunks;
create policy statute_chunks_read_authenticated on statute_chunks
  for select
  using (auth.role() = 'authenticated');

alter table state_rules enable row level security;
drop policy if exists state_rules_read_authenticated on state_rules;
create policy state_rules_read_authenticated on state_rules
  for select
  using (auth.role() = 'authenticated');

alter table rera_guides enable row level security;
drop policy if exists rera_guides_read_authenticated on rera_guides;
create policy rera_guides_read_authenticated on rera_guides
  for select
  using (auth.role() = 'authenticated');
