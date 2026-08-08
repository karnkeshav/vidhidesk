> **Title:** Production Recovery Plan — Deployment Recovery Sprint
> **Version:** 1.0
> **Status:** Active — a plan to execute, not a record that execution happened. No migration was run and no infrastructure was touched while producing this document.
> **Owner:** Keshav (authored) / Nitesh or Keshav (executes)
> **Audience:** Whoever performs the actual recovery
> **Last Updated:** 7 August 2026
> **Canonical Reference:** Yes, for the ordered procedure to bring production in sync with the repository
> **Related Documents:** [`README.md`](README.md), [`Expected_Schema_Inventory_2026-08-07.md`](Expected_Schema_Inventory_2026-08-07.md), [`Migration_Execution_Checklist_2026-08-07.md`](Migration_Execution_Checklist_2026-08-07.md), [`SQL_Verification_Checklist_2026-08-07.md`](SQL_Verification_Checklist_2026-08-07.md), [`Gap_Analysis_2026-08-07.md`](Gap_Analysis_2026-08-07.md), [`../40_Operations/Recovery_Procedure.md`](../40_Operations/Recovery_Procedure.md)

---

# Production Recovery Plan

## Scope and how this differs from `40_Operations/Recovery_Procedure.md`

`Recovery_Procedure.md` is a general-purpose runbook: "here's the fix for each category of FAIL `verify_project.py` can report." This document is specific and ordered: "here is the exact sequence to run, right now, to close the exact gap `Gap_Analysis_2026-08-07.md` found in this specific production project." Read this one to execute; read that one if a *different* future gap shows up that isn't this one.

## Pre-conditions (confirmed, not assumed)

Per `Gap_Analysis_2026-08-07.md`: migrations `0001`–`0012` are already correctly applied to `pgwemjswxdlnshrfoggj` (13/13 non-litigation tables present and column-correct, both RPCs present and correctly access-controlled, RLS enforcing on every checkable table). Only `0013` and `0014` remain unapplied, and neither Storage bucket exists. This plan addresses exactly that gap — it is not a from-scratch deployment procedure.

## Step 0 — Baseline snapshot

Before changing anything, capture the current state so the "before" is on record, not just asserted from memory:

```
cd api && python scripts/verify_project.py > /tmp/pre_recovery_baseline.txt 2>&1
```

Expected result at this point: `Database: FAIL`, `Storage: FAIL`, everything else `PASS`/`WARN` as already documented in `Gap_Analysis_2026-08-07.md`. If this baseline run shows something *different* from the gap analysis (e.g., a table that's now unexpectedly present, or a different table missing), **stop and reconcile that difference before proceeding** — this plan is written against a specific, dated gap analysis, and executing it against a state that has already silently drifted from that analysis risks applying the wrong fix.

## Step 1 — Apply `0013_litigation_schema.sql`

**Where:** Supabase SQL Editor (Project → SQL Editor → New query) — no Dashboard table/storage browser needed, just the SQL Editor's query interface, which is the one piece of Supabase access this plan assumes is available (per `40_Operations/Local_Development_Setup.md` §4, the project's own documented process for every prior migration).

**What:** paste the entire contents of `api/migrations/0013_litigation_schema.sql` and run it as one script. Per the Migration Execution Checklist, this file's table/column/index creation is `IF NOT EXISTS`-guarded and safe even if partially run before; its `CREATE POLICY` statements are **not** guarded (TICKET-12) — but since this is confirmed to be a genuine first-time run (the tables don't exist yet), that gap doesn't bite here. It would only matter on a *second* attempt — see the rollback section for what to do if this run needs to be redone.

**Verify:** run every query in `SQL_Verification_Checklist_2026-08-07.md` §1. Do not proceed to Step 2 until all of them return the expected row counts — in particular, confirm the RLS-enabled and RLS-policy-count queries, since those are the ones a partial or interrupted paste is most likely to have skipped silently (a syntax error partway through a multi-statement SQL Editor run can leave later statements un-executed without always making that obvious from the editor's own success/failure signal).

## Step 2 — Apply `0014_litigation_case_analysis.sql`

**Where:** same SQL Editor.

**What:** paste the entire contents of `api/migrations/0014_litigation_case_analysis.sql`, run as one script. Depends on `0013` having actually landed (it references `litigation_facts_evidence` and `matters`) — this is why it's Step 2, not run in parallel with Step 1.

**Verify:** `SQL_Verification_Checklist_2026-08-07.md` §2.

## Step 3 — Provision the Storage buckets

**Not a SQL migration** — no file in `api/migrations/` does this, and this plan does not assume Supabase Dashboard/Storage-browser access is available. Supabase exposes its storage bucket registry as a normal table, `storage.buckets`, reachable from the same SQL Editor used in Steps 1–2:

```sql
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('evidence', 'evidence', true)
on conflict (id) do nothing;
```

**Decision point before running this — do not treat `public: true` as a silent default.** The existing application code (`api/app/routers/profile.py::upload_avatar`, `api/app/routers/litigation.py::upload_evidence`, both already shipped, neither touched by this sprint) calls `get_public_url()` on uploaded objects in both buckets, which only produces a working, permanently-accessible URL if the bucket is public. That's a reasonable default for `avatars` (a profile photo isn't sensitive). It's a **real confidentiality question** for `evidence` — uploaded documents are client evidence, and `CLAUDE.md`'s own confidentiality principle and the Product Constitution's Legal Safety Principles both weigh against "anyone with the URL can read it" for that kind of material. Two honest options, not a recommendation to pick one silently:

- **Match existing code as-is (`public: true` for both):** the SQL above. Works immediately with zero code changes. The tradeoff above is real and should be a conscious choice, not an accident of which SQL snippet got pasted.
- **Make `evidence` private instead:** change `true` to `false` for the `evidence` bucket only. This is safer for confidentiality but **breaks the existing `upload_evidence` endpoint's `get_public_url()` call** — a private bucket's "public URL" doesn't resolve to anything a client can actually fetch without a signed URL. Switching to signed URLs (`create_signed_url()`) is an application code change, explicitly out of scope for this sprint ("Do NOT modify application code"). If this option is chosen, treat "switch `upload_evidence` to signed URLs" as a new, separate backlog item, not something this recovery silently half-does.

This plan defaults to matching the existing code (public: true for both) so the feature actually works after this recovery, while stating the tradeoff plainly rather than deciding it invisibly.

**Verify:** `SQL_Verification_Checklist_2026-08-07.md` §3.

## Step 4 — Full post-deployment check

```
cd api && python scripts/verify_project.py
```

Expected result now: `Environment PASS`, `Database PASS`, `Storage PASS`, `Providers` — depends on whether `CEREBRAS_API_KEY` (TICKET-11) has also been fixed; if not, this section will still `FAIL` on that one specific check even though it's unrelated to this recovery's scope (Litigation schema + Storage). That's expected and correct, not a sign this recovery failed — see the note in `Gap_Analysis_2026-08-07.md`. `Runtime PASS`, `Tests 214/214 PASS`, and — the one that actually gates the next sprint — `Validation Ready: YES` **provided** Providers also passes (TICKET-11 fixed) or the overall aggregation is read section-by-section rather than as a single boolean (see `Infrastructure_Verification.md` on why a single dead fallback provider tier still fails its own section even though it doesn't block real usage).

Then run the manual SQL-Editor-only queries in `SQL_Verification_Checklist_2026-08-07.md` §4, since `verify_project.py` cannot reach `pg_indexes`/`pg_policies` on its own.

## Rollback considerations

Both migrations are purely additive — new tables, new columns on existing tables, new indexes, new policies. Nothing existing is altered or dropped. No existing table has a foreign key pointing *into* `litigation_parties`/`litigation_facts_evidence`/`litigation_hearings`/`litigation_case_analyses` (the reference direction is the other way — those new tables point at `matters`), so rolling back cannot cascade into any of the 71+ existing `matters` rows or any other pre-existing data.

If Step 1 or Step 2 needs to be undone (e.g., a verification query in that step's section fails and the cause isn't obvious):

```sql
-- Reverses 0014:
drop table if exists litigation_case_analyses cascade;
alter table litigation_facts_evidence
  drop column if exists file_url,
  drop column if exists file_name,
  drop column if exists file_size_bytes,
  drop column if exists mime_type;

-- Reverses 0013 (only if 0014 has already been reversed first, since 0014 references litigation_facts_evidence):
drop table if exists litigation_parties cascade;
drop table if exists litigation_facts_evidence cascade;
drop table if exists litigation_hearings cascade;
alter table matters
  drop column if exists court_category,
  drop column if exists jurisdiction_state,
  drop column if exists cnr_number,
  drop column if exists case_number_formatted,
  drop column if exists litigation_stage,
  drop column if exists court_name,
  drop column if exists bench_name;
```

`cascade` on the `drop table` statements is there specifically to also drop the RLS policies and indexes that live on those tables — since nothing else references them, `cascade` here cannot touch any other object. Re-running Steps 1–2 after a rollback is then a genuine first-time apply again (the `IF NOT EXISTS` guards remain valid), **except** the `CREATE POLICY` statements will still be un-guarded (TICKET-12) — if a rollback-and-retry is ever actually needed, fix TICKET-12 first, or manually add `drop policy if exists ... ;` lines ahead of each `create policy` before re-pasting, since the same unguarded-policy gap that doesn't matter on a clean first run would matter on a second attempt.

Storage bucket rollback, if ever needed: `delete from storage.buckets where id in ('avatars', 'evidence');` — safe as long as the buckets are still empty, which they will be immediately after Step 3 and remain until real uploads happen.

## Post-deployment checks beyond schema correctness

- Confirm the RAG corpus is still intact after all this (`statute_chunks` row count — should still read 633, unaffected by any of the above, but worth a glance since Contracts/Litigation share this table).
- Confirm no *unexpected* data appeared in the new tables — they should all read 0 rows immediately after this recovery, since nothing in this plan inserts a matter, party, fact, or analysis.
- This plan does **not** include running the 26-scenario acceptance validation — that's the next sprint's job, gated on this recovery landing cleanly first (see `Recommendations.md` from the prior validation round).
