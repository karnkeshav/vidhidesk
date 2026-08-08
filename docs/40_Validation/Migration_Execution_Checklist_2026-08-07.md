> **Title:** Migration Execution Checklist — Deployment Recovery Sprint
> **Version:** 1.0
> **Status:** Active — planning artifact
> **Owner:** Keshav
> **Audience:** Whoever executes the recovery
> **Last Updated:** 7 August 2026
> **Canonical Reference:** Yes, for migration ordering, dependencies, idempotency, and per-file execution guidance
> **Related Documents:** [`README.md`](README.md), [`Production_Recovery_Plan_2026-08-07.md`](Production_Recovery_Plan_2026-08-07.md), [`Expected_Schema_Inventory_2026-08-07.md`](Expected_Schema_Inventory_2026-08-07.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Migration Execution Checklist

## Audit method

Every one of the 14 files in `api/migrations/` was read in full for this sprint (not re-derived from memory of earlier sprints) to answer, per file: does it state its dependencies, is it idempotent as claimed, does it assume a manual step outside the file itself, and is it safe to re-run. This repeats and extends the static check `api/scripts/verify_migrations.py` already automates (see Sprint 3.5.5B) — this document adds the dependency and manual-step analysis that script doesn't attempt.

## Per-migration audit

| # | File | Depends on | Idempotent as written? | Assumes a manual step? | Safe to re-run? |
|---|---|---|---|---|---|
| 1 | `0001_schema.sql` | Nothing (first migration) | ✅ Yes — `IF NOT EXISTS` throughout, `create extension if not exists` for `vector`/`pgcrypto` | No | ✅ Yes |
| 2 | `0002_rls.sql` | 0001 (tables must exist) | ✅ Yes — every policy uses `drop policy if exists` before `create policy` | No | ✅ Yes |
| 3 | `0003_sprint1_rag_and_citation_verifier.sql` | 0001, 0002 | ✅ Yes — `IF NOT EXISTS` on columns/indexes, `drop index if exists` before the one index it replaces | No | ✅ Yes |
| 4 | `0004_retrieval_rpc.sql` | 0003 (needs `statute_chunks.embedding`) | ✅ Yes — `create or replace function`, unconditional `revoke` (idempotent by nature) | No — the anon double-grant behavior it works around is a Supabase project default, not a step anyone needs to perform | ✅ Yes |
| 5 | `0005_case_name_normalization.sql` | 0001, 0003 (touches `citations`) | 🟡 Conditionally — `add column` has no `IF NOT EXISTS`, but it's preceded by an unconditional `drop column if exists` on the same column, making the net effect idempotent via drop-then-recreate rather than a guard. The file's own comment records `citations` had 0 rows when written, explicitly calling this "a clean drop+recreate, not a backfill." | No | 🟡 Yes, **conditionally** — safe as long as `citations` has 0 rows (still true as of this sprint — see `Gap_Analysis_2026-08-07.md`). If `citations` ever holds rows and this file is re-run, the drop would discard `case_name_normalized` values for those rows before recreating the column empty. Not a concern for *this* recovery (only 0013/0014 need a first-time apply), but worth knowing before ever re-running 0001-0012 as a block. |
| 6 | `0006_statute_fulltext_search.sql` | 0001, 0003 | ✅ Yes — `IF NOT EXISTS` on column/index, `create or replace function` | No | ✅ Yes |
| 7 | `0007_contracts_clause_review.sql` | 0001-0006 | ✅ Yes — `IF NOT EXISTS` on columns/indexes, `drop policy if exists` before every `create policy` | No | ✅ Yes |
| 8 | `0008_generic_clause_conditions_and_numbering.sql` | 0007 (needs `template_clauses`) | ✅ Yes — `IF NOT EXISTS` on both new columns, `drop column if exists` before dropping the old one | No | ✅ Yes |
| 9 | `0009_normalize_template_keys.sql` | 0007 (needs `templates.template_key`) | ✅ Yes — a plain `UPDATE ... WHERE`, re-running it is a no-op once the values already match | No | ✅ Yes |
| 10 | `0010_add_template_id_to_matters.sql` | 0001 (matters), 0001 (templates) | ✅ Yes — `ADD COLUMN IF NOT EXISTS` | No | ✅ Yes |
| 11 | `0011_create_advocate_profiles.sql` | 0001 (references `auth.users`, which Supabase provisions automatically, not a migration dependency) | ❌ **No** — all four `CREATE POLICY` statements have no preceding `DROP POLICY IF EXISTS`, unlike every other RLS-creating migration in this project. The backfill `INSERT ... ON CONFLICT (user_id) DO NOTHING` at the end *is* idempotent on its own. | No | ❌ **No** — a second run errors on `policy already exists` for all four policies (TICKET-12, `Backlog.md`) |
| 12 | `0012_simplify_advocate_profiles.sql` | 0011 (drops columns/indexes/constraint 0011 created) | ✅ Yes — every `DROP` uses `IF EXISTS` | No | ✅ Yes |
| 13 | `0013_litigation_schema.sql` | 0001 (extends `matters`, references it as FK target) | ❌ **No** — same gap as 0011: all twelve `CREATE POLICY` statements (four each on three tables) have no preceding `DROP POLICY IF EXISTS`. Table/column/index creation *is* correctly guarded with `IF NOT EXISTS`. | No | ❌ **No**, for the same reason — table/column/index portions alone would be safe to re-run, but the policy statements would error |
| 14 | `0014_litigation_case_analysis.sql` | 0013 (references `litigation_facts_evidence`, `matters`) | ❌ **No** — same gap, two `CREATE POLICY` statements with no `DROP POLICY IF EXISTS` guard. Table/column/index portions correctly guarded. | No | ❌ **No**, same reason |

## What "assumes a manual step" turned up

**No migration file assumes a prior manual step it doesn't itself account for.** The one thing that *looked* like it might qualify — Supabase's automatic `anon`-execute grant on newly created functions — is explicitly handled inside 0004 and 0006 themselves (the double `REVOKE`, with a comment explaining why both are needed), not left as an unstated assumption.

**The one genuine manual/separate-mechanism step in this whole recovery is Storage bucket creation**, and it isn't "assumed" by any migration because no migration touches it at all — `avatars` and `evidence` are Supabase Storage objects, not schema DDL that any of these 14 files create. See `Production_Recovery_Plan_2026-08-07.md` for how to provision them without dashboard access, via the `storage.buckets` table directly.

## Execution order and expected objects — this recovery, specifically

Per `Gap_Analysis_2026-08-07.md`, migrations `0001`–`0012` are already confirmed applied and correct. **Only two files need to be executed for the first time:**

| Step | File | Expected new objects | Verify with (see `SQL_Verification_Checklist_2026-08-07.md`) |
|---|---|---|---|
| 1 | `0013_litigation_schema.sql` | Tables: `litigation_parties`, `litigation_facts_evidence`, `litigation_hearings`. Columns: 7 new additive columns on `matters`. Indexes: `idx_litigation_parties_matter`, `idx_litigation_facts_matter`, `idx_litigation_hearings_matter`. RLS policies: 12 (4 per new table). | §1 |
| 2 | `0014_litigation_case_analysis.sql` | Table: `litigation_case_analyses`. Columns: 4 new on `litigation_facts_evidence`. Index: `idx_litigation_case_analyses_matter`. RLS policies: 2. | §2 |

**Do not re-run `0011` as part of this recovery**, even though nothing about this recovery requires touching `advocate_profiles` — it's already correctly applied (`Gap_Analysis_2026-08-07.md` confirms all 11 final columns present, the 9 deprecated columns correctly absent). Re-running it would error on the policy statements for no benefit. Listed here only so the person executing this doesn't reach for "let's just re-run everything from 0001 to be safe" as a shortcut — per the audit above, that shortcut is unsafe for exactly this file.
