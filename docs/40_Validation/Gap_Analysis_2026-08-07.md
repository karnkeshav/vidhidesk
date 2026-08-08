> **Title:** Gap Analysis — Deployment Recovery Sprint
> **Version:** 1.0
> **Status:** Active — reflects verified production state as of this sprint; re-run and supersede with a new dated file after the recovery plan executes, don't edit this one in place
> **Owner:** Keshav
> **Audience:** Whoever executes `Production_Recovery_Plan_2026-08-07.md`
> **Last Updated:** 7 August 2026
> **Canonical Reference:** Yes, for the exact, evidenced difference between expected and actual production schema as of this sprint
> **Related Documents:** [`README.md`](README.md), [`Expected_Schema_Inventory_2026-08-07.md`](Expected_Schema_Inventory_2026-08-07.md), [`Production_Recovery_Plan_2026-08-07.md`](Production_Recovery_Plan_2026-08-07.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Gap Analysis

## Evidence basis

The verified-state column below is built from real checks against `pgwemjswxdlnshrfoggj.supabase.co` made earlier in this same session (Sprint 3.5.6's two full `verify_project.py` runs, plus a third, targeted direct check made specifically to answer "does this project contain the Litigation tables and buckets"). All three independent checks agree exactly — table count, table names, bucket count. This document reuses that evidence rather than re-running the full provider-touching verification suite a fourth time in immediate succession, since doing so would burn real LLM/API quota to reconfirm something already independently confirmed three times with no discrepancy between runs. Anyone acting on this document should still re-run `python api/scripts/verify_project.py` themselves immediately before executing `Production_Recovery_Plan_2026-08-07.md`, per that plan's own Step 0 — this analysis is the basis for the plan, not a substitute for the plan's own pre-flight check.

## Tables

| Expected (17) | Verified present? |
|---|---|
| `matters` | ✅ Present |
| `messages` | ✅ Present |
| `citations` | ✅ Present |
| `templates` | ✅ Present |
| `draft_versions` | ✅ Present |
| `statute_chunks` | ✅ Present |
| `state_rules` | ✅ Present |
| `rera_guides` | ✅ Present |
| `pii_masks` | ✅ Present |
| `template_clauses` | ✅ Present |
| `clause_reviews` | ✅ Present |
| `draft_clause_fills` | ✅ Present |
| `advocate_profiles` | ✅ Present |
| `litigation_parties` | ❌ **MISSING** |
| `litigation_facts_evidence` | ❌ **MISSING** |
| `litigation_hearings` | ❌ **MISSING** |
| `litigation_case_analyses` | ❌ **MISSING** |

**Gap: 4 of 17 tables missing — all four, entirely, from the two unapplied migrations (`0013`, `0014`).**

## Columns

All columns on the 13 present tables were checked (column-by-column, per `Expected_Schema_Inventory_2026-08-07.md`'s list) across multiple runs this session — every one matches expected, including the three deliberately-*absent* columns/constraints from `advocate_profiles`'s 0012 reduction, correctly confirmed absent. **No column-level gap on any existing table.**

The 4 columns `0014` would add to `litigation_facts_evidence` (`file_url`, `file_name`, `file_size_bytes`, `mime_type`) are, unsurprisingly, also missing — moot as a separate finding, since the table itself doesn't exist yet.

## Indexes

**Not directly verifiable this session** — confirmed, real limitation, not a gap in the schema itself: this project has no `DATABASE_URL`/direct Postgres connection configured, and Supabase's PostgREST REST API (the only access this session has) does not expose `pg_indexes`. Status for all 17 expected indexes on the 13 existing tables: **unknown, not FAIL** — someone with SQL Editor access needs to run `SQL_Verification_Checklist_2026-08-07.md`'s `pg_indexes` query to actually close this. The 4 indexes belonging to the 4 missing tables are, definitionally, also missing.

## Constraints

Same limitation as indexes — `pg_constraint` isn't reachable via REST either. **Unknown for existing tables, not FAIL.** Missing for the tables that don't exist.

## RLS policies

**Behaviorally verified correct on all 13 existing tables**, repeatedly, this session — an anon-key (unauthenticated) client reads 0 rows from every one of them, matching the expected owner-only/authenticated-only policy design. This does not confirm the *exact named* policies from the inventory (that needs `pg_policies`, SQL-Editor-only, same limitation as above) but does confirm RLS is genuinely enforcing, not just enabled-but-toothless. **No behavioral gap found on any existing table.** The 35 named policies expected across the 4 missing tables are, of course, also missing, since the tables aren't there to hold them.

## RPCs

**Both present and correctly locked down** — `match_statute_chunks` and `search_statute_chunks_fulltext` both exist, and an anon-key client attempting to call either is denied, matching the explicit double-`REVOKE` both migrations implement. **No gap.**

## Views

**None expected, none found. No gap** — this is a clean match, not an oversight (see `Expected_Schema_Inventory_2026-08-07.md`'s note on a false-positive "view" match this sprint corrected in itself before finalizing the inventory).

## Storage buckets

| Expected (2) | Verified present? |
|---|---|
| `avatars` | ❌ **MISSING** |
| `evidence` | ❌ **MISSING** |

`storage.list_buckets()` returns an empty list. **Gap: both buckets entirely absent.** Neither is created by any SQL migration (see the Migration Execution Checklist) — this gap exists independent of whether `0013`/`0014` are applied, and needs the separate Step 3 in the recovery plan.

## Summary

| Category | Expected | Verified matching | Missing | Unknown (can't check without SQL Editor access) |
|---|---|---|---|---|
| Tables | 17 | 13 | 4 | 0 |
| Columns (on existing tables) | ~100+ | all checked, all match | 4 (on the missing table) | 0 |
| Indexes | 17 | 0 confirmed | 4 (on missing tables) | 13 |
| Constraints | ~15 named + FKs | 0 confirmed | on missing tables | all on existing tables |
| RLS policies | 35 (+1 intentional zero) | 13 tables behaviorally confirmed | 12 (on 3 missing tables) + 2 (on 1 missing table) = 14 | exact policy names on the 13 existing tables |
| RPCs | 2 | 2 | 0 | 0 |
| Views | 0 | 0 | 0 | 0 |
| Storage buckets | 2 | 0 | 2 | 0 |

**Everything this session's tooling can directly verify is either confirmed correct or confirmed missing — nothing was found in an ambiguous or partially-applied state.** The only genuinely open questions (index/constraint/exact-policy-name verification on the 13 already-applied tables) are open because of a tooling access limitation stated plainly in `SQL_Verification_Checklist_2026-08-07.md`, not because of an inconclusive check.
