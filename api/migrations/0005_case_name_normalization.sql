-- VidhiDesk — Sprint 1: case_name_normalized becomes app-populated
-- (app.services.citations.normalize_case_name()), not a DB-generated
-- column — a generated column can only run a fixed SQL expression, and
-- the real normalization (vs/v./versus/bare-v collapsing, "and Anr"/
-- "and Ors" party-count suffix stripping, ellipsis handling) needs to be
-- testable and evolvable the same way the rest of this codebase is,
-- which means Python, not a DDL expression.
--
-- Run after 0004_retrieval_rpc.sql. The citations table has 0 rows at
-- time of writing (confirmed via direct query) — this is a clean
-- drop+recreate, not a backfill.

drop index if exists citations_normalized_uq;

alter table citations drop column if exists case_name_normalized;
alter table citations add column case_name_normalized text not null;

create unique index if not exists citations_normalized_uq
  on citations (case_name_normalized, coalesce(neutral_citation, ''));

comment on column citations.case_name_normalized is
  'Populated by app.services.citations.normalize_case_name() on every '
  'insert — NOT a generated column. verify_citation() is currently the '
  'only writer to this table; that single-writer property is what keeps '
  'this from drifting. Sprint 2 follow-up (deliberately deferred, not a '
  'Sprint 1 blocker): a structural drift guarantee — either a trigger '
  'that populates this from case_name when left NULL, or a CHECK '
  'constraint — for whenever a second writer shows up.';
