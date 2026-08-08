> **Title:** SQL Verification Checklist — Deployment Recovery Sprint
> **Version:** 1.0
> **Status:** Active — planning artifact; these queries are written but **not executed** by this sprint (no Postgres/dashboard access assumed or used)
> **Owner:** Keshav
> **Audience:** Whoever executes the recovery, via the Supabase SQL Editor
> **Last Updated:** 7 August 2026
> **Canonical Reference:** Yes, for the exact SQL to confirm each migration's objects landed correctly
> **Related Documents:** [`README.md`](README.md), [`Migration_Execution_Checklist_2026-08-07.md`](Migration_Execution_Checklist_2026-08-07.md), [`Production_Recovery_Plan_2026-08-07.md`](Production_Recovery_Plan_2026-08-07.md)

---

# SQL Verification Checklist

**A scoping note before the queries:** this project's only route into the database from outside the SQL Editor is Supabase's PostgREST REST API (`api/scripts/verify_database.py` uses exactly this), which exposes tables/views/RPCs but **not** `pg_indexes`, `pg_constraint`, `pg_policies`, or `pg_trigger` — those system catalogs require a direct SQL connection. That means the queries below marked "SQL Editor only" cannot be run by `verify_database.py`, by me, or by any REST-API-only tool — they need to be run by a human (or an agent with real SQL Editor access) inside the Supabase SQL Editor itself. This document was **written, not executed** — consistent with this sprint's explicit "do not execute migrations, do not modify production" boundary.

## §1 — After `0013_litigation_schema.sql`

**Tables** (SQL Editor, or equivalently `verify_database.py`'s PostgREST-based table check):
```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('litigation_parties', 'litigation_facts_evidence', 'litigation_hearings')
order by table_name;
-- Expect: 3 rows.
```

**Columns added to `matters`** (SQL Editor):
```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public' and table_name = 'matters'
  and column_name in ('court_category', 'jurisdiction_state', 'cnr_number',
                       'case_number_formatted', 'litigation_stage', 'court_name', 'bench_name')
order by column_name;
-- Expect: 7 rows, all is_nullable = 'YES' (additive, non-required columns).
```

**Indexes** (SQL Editor only — not reachable via PostgREST):
```sql
select indexname, tablename
from pg_indexes
where schemaname = 'public'
  and indexname in ('idx_litigation_parties_matter', 'idx_litigation_facts_matter', 'idx_litigation_hearings_matter')
order by indexname;
-- Expect: 3 rows.
```

**RLS enabled** (SQL Editor only):
```sql
select relname, relrowsecurity
from pg_class
where relname in ('litigation_parties', 'litigation_facts_evidence', 'litigation_hearings');
-- Expect: 3 rows, relrowsecurity = true for all.
```

**RLS policies** (SQL Editor only):
```sql
select tablename, policyname, cmd
from pg_policies
where schemaname = 'public'
  and tablename in ('litigation_parties', 'litigation_facts_evidence', 'litigation_hearings')
order by tablename, policyname;
-- Expect: 12 rows (4 per table: select/insert/update/delete owner policies).
```

**Behavioral RLS check** (works via REST API — this is what `verify_database.py` actually does, no direct Postgres connection needed): query each of the three tables with the **anon** key, unauthenticated. Expect an empty result or an outright access-denied error, never real rows, since there's no owning matter for an anonymous caller.

## §2 — After `0014_litigation_case_analysis.sql`

**Table:**
```sql
select table_name from information_schema.tables
where table_schema = 'public' and table_name = 'litigation_case_analyses';
-- Expect: 1 row.
```

**Columns added to `litigation_facts_evidence`:**
```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public' and table_name = 'litigation_facts_evidence'
  and column_name in ('file_url', 'file_name', 'file_size_bytes', 'mime_type')
order by column_name;
-- Expect: 4 rows. file_size_bytes should be data_type = 'bigint'.
```

**Index** (SQL Editor only):
```sql
select indexname from pg_indexes
where schemaname = 'public' and indexname = 'idx_litigation_case_analyses_matter';
-- Expect: 1 row.
```

**RLS policies** (SQL Editor only):
```sql
select policyname, cmd from pg_policies
where schemaname = 'public' and tablename = 'litigation_case_analyses'
order by policyname;
-- Expect: exactly 2 rows (select_owner, insert_owner) — no update/delete policy is
-- correct here, not a gap; analysis versions are immutable by design (ADR-011).
```

**Unique constraint** (SQL Editor only):
```sql
select conname from pg_constraint
where conrelid = 'public.litigation_case_analyses'::regclass and contype = 'u';
-- Expect: 1 row, the (matter_id, version_no) unique constraint.
```

## §3 — Storage buckets (after provisioning, not a migration step)

```sql
select id, name, public from storage.buckets where id in ('avatars', 'evidence') order by id;
-- Expect: 2 rows, both with public = true (matching what the existing application
-- code's get_public_url() calls assume — see the confidentiality flag in
-- Expected_Schema_Inventory_2026-08-07.md and Production_Recovery_Plan_2026-08-07.md
-- before treating "public = true" as an unquestioned default).
```

This one **is** reachable outside the SQL Editor too — `service_client().storage.list_buckets()` via the REST/Storage API, which is what `verify_storage.py` already uses.

## §4 — Whole-repository sanity checks (not migration-specific)

**RPCs still correctly locked down** (confirms 0013/0014 didn't accidentally touch grants — they shouldn't have, but this is cheap to re-check):
```sql
select routine_name from information_schema.routines
where routine_schema = 'public'
  and routine_name in ('match_statute_chunks', 'search_statute_chunks_fulltext');
-- Expect: 2 rows. (Reachable via REST too — verify_database.py already checks these.)
```

**No unexpected new tables** (catches a typo'd or duplicate migration accidentally creating something not in the inventory):
```sql
select table_name from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE'
order by table_name;
-- Expect: exactly the 17 tables in Expected_Schema_Inventory_2026-08-07.md, no more, no fewer.
```

**No views exist** (per the inventory — zero are expected; if this ever returns a row, something outside these 14 migrations created it):
```sql
select table_name from information_schema.views where table_schema = 'public';
-- Expect: 0 rows.
```

## §5 — The fastest single re-check, after everything above

```
cd api && python scripts/verify_project.py
```

Covers §1, §2, §3 (buckets), and §4's RPC/table-count checks automatically via the REST API — it just can't reach the SQL-Editor-only index/constraint/named-policy queries. Treat a `Validation Ready: YES` from this command as necessary but not fully sufficient on its own; run at least the `pg_indexes`/`pg_policies` queries above once, manually, to close the gap this project's verification framework has always been explicit about not being able to check itself (see `40_Operations/Infrastructure_Verification.md`).
