> **Title:** Runtime Validation Report — Sprint 3.5.5A
> **Version:** 1.0
> **Status:** Active — Phase 1 complete, Phases 2–6 **not executed**, stopped per explicit sprint instruction
> **Owner:** Keshav (executed)
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for this session's real infrastructure state
> **Related Documents:** [`README.md`](README.md), [`Go_No_Go_Decision.md`](Go_No_Go_Decision.md) (6 August 2026, prior round — different blocker, see note below), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)

---

# Runtime Validation Report — Sprint 3.5.5A

## Outcome: Phase 1 found real, hard blockers. Per explicit sprint rules ("if a dependency is missing, stop and report it"), Phases 2–6 were not attempted.

## Correction to the prior round's premise

The Sprint 3.5.5 round (`Go_No_Go_Decision.md`, `Metrics_Dashboard.md`, same date) concluded no live credentials were available, based on checking `api/.env` only. That was an incomplete check — `api/app/config.py` documents that environment variables load from the **monorepo-root `.env`**, not `api/.env` (`find_dotenv(usecwd=True)` walks up from cwd). A repo-root `.env` exists and contains real, working values for all eight credentials. **The prior round's "no credentials" framing was wrong** — restated here plainly rather than quietly superseded, since an inaccurate blocker report is exactly the kind of thing this project's evidence-tagging discipline exists to catch.

This round's finding is different and more specific: **credentials work; the target database is not provisioned for the Litigation feature set that depends on them.**

## Phase 1 — Environment Validation Results

| Dependency | Status | Evidence |
|---|---|---|
| `GEMINI_API_KEY` | ✅ **Working** | Real call to `gemini-2.5-flash-lite`, 1246ms, returned expected response |
| `GROQ_API_KEY` | ✅ **Working** | Real call to `llama-3.1-8b-instant`, 271ms, returned expected response |
| `SAMBANOVA_API_KEY` | ✅ **Working** | Real call to `Meta-Llama-3.3-70B-Instruct`, 2582ms, returned expected response |
| `CEREBRAS_API_KEY` | ❌ **Invalid** | Real call to `gpt-oss-120b` → HTTP 401 `"Wrong API Key"`, 457ms. Last-tier fallback only; Gemini/Groq/SambaNova all healthy, so this does not block the pipeline in practice, but it is a real, reproducible finding. |
| `INDIAN_KANOON_API_TOKEN` | ✅ **Working** | Real search call ("Ramesh Kumar vs State of Delhi"), 7812ms, 10 results returned |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_KEY` | ✅ **Working** | Real authenticated query against `matters` table, 1317ms, 71 existing rows read |
| **Database schema — Contracts-era tables** | ✅ **Present** | `matters`(71), `messages`(8), `citations`(0), `templates`(10), `draft_versions`(6), `statute_chunks`(**633** — RAG corpus is populated), `state_rules`(27), `pii_masks`(79), `template_clauses`(100), `clause_reviews`(0), `draft_clause_fills`(18), `advocate_profiles`(1) — all reachable and match the schema `api/app/services/*.py` expects for the Contracts module |
| **Database schema — Litigation tables** | ❌ **MISSING — hard blocker** | `litigation_parties`, `litigation_facts_evidence`, `litigation_hearings`, `litigation_case_analyses` all return `PGRST205: Could not find the table 'public.<name>' in the schema cache`. Independently re-confirmed via a direct PostgREST OpenAPI schema fetch: **13 total tables exposed, zero containing "litigation."** Migrations `0013_litigation_schema.sql` and `0014_litigation_case_analysis.sql` — both already written, reviewed, and merged as part of Sprint 3.5.3 — have never been run against this Supabase project. |
| **Object storage** | ❌ **MISSING — hard blocker for Evidence Upload** | `service_client().storage.list_buckets()` returns an empty list. Zero buckets exist. Both `evidence` (litigation evidence upload) and `avatars` (profile photo upload) buckets referenced in code are unprovisioned. |

## Why this stops the sprint here

Phase 2's documented workflow is Matter → Parties → Facts → Evidence Upload → Limitation → Forum → ... → AI Case Analysis → Version → Structured Review. The **Parties** step alone — `POST /api/matters/{id}/parties` inserting into `litigation_parties` — would fail immediately against this database with a real `PGRST205` error for all 26 scenarios, because that table does not exist. Every scenario requires at least one party before an AI Case Analysis can even be requested (`CaseAnalysisError` precondition in `case_analysis.py`), so nothing past step 2 of the documented workflow is reachable, for any scenario, regardless of how healthy the LLM providers are.

This is precisely the situation the sprint's own rules anticipate: *"If infrastructure is unavailable, stop and report the exact blocker."* Continuing anyway would require either (a) fabricating what Phases 2–6 would produce, which is explicitly forbidden and would be dishonest, or (b) unilaterally applying schema migrations and provisioning storage buckets against a live database holding 71 real existing matter records without being asked to — a real, consequential, and not-trivially-reversible action on shared infrastructure that this sprint's instructions did not authorize ("do NOT redesign architecture" and the general practice of confirming before acting on shared systems both counsel against it). Neither is the right call. Stopping and reporting precisely is.

## What is and is not a "defect" here

- The **migrations not being applied** and the **storage buckets not being provisioned** are not code defects — `0013_litigation_schema.sql` and `0014_litigation_case_analysis.sql` are correct, idempotent, already-reviewed migration files (confirmed present and syntactically sound by `test_migration_0013_idempotency_syntax` and equivalent checks in the existing test suite, which run against a mocked DB and therefore never caught that they'd never been run for real). This is a **deployment/provisioning gap**, not an application bug — nothing in `api/app/services/*.py` needs to change.
- The **Cerebras key being invalid** is a credentials/provisioning issue, not a code defect either — the failover logic itself worked correctly (it's just that the tier being tested standalone here, outside the full failover chain, has no earlier tier to fail over from).

## Files modified this session

- `docs/40_Validation/Runtime_Validation_Report_2026-08-06.md` (this file — new)
- `docs/30_Implementation/Backlog.md` (three new entries: TICKET-9, TICKET-10, TICKET-11 — see below)
- `docs/30_Implementation/Build_Tracker.md` (evidence log entry E31)

No application code, migrations, or infrastructure were modified. No matter, party, fact, evidence, or case-analysis record was created (the schema gap made this impossible for the Litigation tables; no Contracts-module data was touched either).

## Recommendation: GO / GO WITH CONDITIONS / HOLD / NO GO

**HOLD.** Not a NO GO — nothing found indicates a defect in the reviewed, tested, already-shipped code; every blocker found is a provisioning gap with a known, low-effort fix. Not a GO or GO WITH CONDITIONS either, because the validation this sprint exists to produce (Phases 2–6) never ran — there is no new evidence about AI quality, hallucination rate, citation correctness, or cost this round, only a clearer picture of exactly what stands between "credentials exist" and "the pipeline can be exercised for real." The prior round's Hold (`Go_No_Go_Decision.md`) stands, now for a more precise and more fixable reason.

## Remaining blockers before Sprint 3.5.6 (AI Pleading Generation) — and before a real Sprint 3.5.5B/6A validation re-run

1. **Apply migrations `0013_litigation_schema.sql` and `0014_litigation_case_analysis.sql`** to this Supabase project (`pgwemjswxdlnshrfoggj`), via the Supabase SQL Editor per `40_Operations/Local_Development_Setup.md` §4 — the documented process for this exact situation. Both are idempotent and additive; low risk to the 71 existing Contracts-module matters, but this is a real production database and the action should be taken deliberately, by someone who can confirm it, not silently by an agent mid-validation-run.
2. **Provision the `evidence` and `avatars` Supabase Storage buckets.** Neither exists. `api/app/routers/litigation.py::upload_evidence` and `api/app/routers/profile.py::upload_avatar` both degrade gracefully (they log a warning and continue without a `file_url` rather than crash) when the bucket is missing — so this doesn't hard-block the workflow the way the missing tables do, but it does mean Evidence Upload cannot be genuinely exercised, only its graceful-failure path.
3. **Replace or remove the invalid `CEREBRAS_API_KEY`.** Low priority — the failover chain works without it — but worth fixing so the fourth tier is a real safety net rather than a guaranteed-fail no-op.
4. **Once 1–2 are done, re-run this sprint's Phases 2–6 for real** — the actual objective this sprint set out to achieve, now blocked purely on provisioning rather than credentials.
