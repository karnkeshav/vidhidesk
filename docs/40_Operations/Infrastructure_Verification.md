> **Title:** Infrastructure Verification
> **Version:** 1.0
> **Status:** Active — Canonical for the `scripts/verify_*.py` framework
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for what each verification script checks and — just as importantly — what it cannot check and why
> **Supersedes:** N/A
> **Related Documents:** [`Runtime_Health_Check.md`](Runtime_Health_Check.md), [`Deployment_Verification_Guide.md`](Deployment_Verification_Guide.md), [`Recovery_Procedure.md`](Recovery_Procedure.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Infrastructure Verification

Six real scripts live in `api/scripts/`: `verify_environment.py`, `verify_database.py`, `verify_storage.py`, `verify_llm_providers.py`, `verify_migrations.py`, `verify_runtime.py`, orchestrated by `verify_project.py`. Every one of them runs a real check against real infrastructure when credentials are available — none of them mock, estimate, or simulate a result. A check that genuinely cannot be performed with the credentials configured reports `SKIP` with the reason, never a fabricated `PASS`. This is not a style preference; it's the direct lesson of Sprint 3.5.5 (see `docs/40_Validation/`), where 214/214 mocked-DB unit tests passing said nothing about whether the real production database had the tables the code needed.

Each script is independently runnable (`python scripts/verify_<name>.py`) and importable (`from verify_<name> import run`) — `verify_project.py` does the latter to build the consolidated report in `Runtime_Health_Check.md`.

## `verify_environment.py` (Part 5)

Checks the real `.env` (repo root — not `api/.env`; see `Deployment_Verification_Guide.md` for why this distinction matters) and `web/.env.local`: every required variable present, non-empty, not an obvious placeholder; no duplicate keys silently shadowing each other; CORS origins have no wildcard; `SUPABASE_URL` has the right shape. Does not check whether a credential actually *works* — that's `verify_llm_providers.py`'s and `verify_database.py`'s job. Needs no network access.

## `verify_database.py` (Part 2, live state)

Talks to the real Supabase project via PostgREST's own OpenAPI schema introspection (`GET {SUPABASE_URL}/rest/v1/`) — no extra dependency beyond `httpx`, which the project already depends on. Checks:

- **Table and column existence** — against a manifest built by reading every migration in `api/migrations/` in full, including `DROP` statements, so a deliberately-removed object (e.g. `advocate_profiles`'s columns dropped by migration 0012) doesn't get flagged as a false failure.
- **RPC existence** (`match_statute_chunks`, `search_statute_chunks_fulltext`).
- **RLS enforcement, behaviorally** — compares what an anon-key (unauthenticated) client can see against what should be visible per the policies in `0002_rls.sql`/`0007`/`0011`/`0013`/`0014`. A real, live security check, not a read of the policy SQL.
- **Anon cannot execute the app's RPCs** — verifies the explicit `REVOKE EXECUTE ... FROM anon` in migrations 0004/0006 actually holds at runtime.
- **Row counts**, informational (e.g. `statute_chunks` being empty would silently break RAG retrieval; this surfaces that immediately rather than as a confusing downstream symptom).

**What it cannot check, and says so explicitly:** named index existence, named constraint existence, triggers. PostgREST does not expose Postgres system catalog metadata (`pg_indexes`, `pg_constraint`, `pg_trigger`) — that requires a direct Postgres connection string (`DATABASE_URL`), which this project does not currently have configured anywhere. These checks report `SKIP` with this exact reason, not a guessed `PASS`.

## `verify_migrations.py` (Part 2, file hygiene)

Distinct from `verify_database.py` on purpose: this one needs no credentials at all, because it only reads the migration files themselves. Checks sequential numbering (no gaps, no duplicate prefixes), and a structural idempotency check per file (every `CREATE TABLE`/`CREATE INDEX`/`ADD COLUMN` uses `IF NOT EXISTS`; every `CREATE POLICY` has a preceding `DROP POLICY IF EXISTS`, matching the pattern the project's own earlier migrations established). Running this for real during Sprint 3.5.5B found two things worth knowing:

1. A previously-documented claim (in an earlier version of `20_Engineering/Database_Architecture.md` and this doc set's own `README.md`) that migrations `0009_normalize_template_keys.sql` and a `0009_litigation_pleadings_and_citations.sql` shared a duplicate number prefix — **that second file was never actually created**; the litigation schema migration that shipped is `0013_litigation_schema.sql`, correctly numbered. The claim was stale and has been corrected (see `docs/40_Validation/Technical_Debt_Report_2026-08-06.md`).
2. Migrations `0011_create_advocate_profiles.sql`, `0013_litigation_schema.sql`, and `0014_litigation_case_analysis.sql` all use bare `CREATE POLICY` without the `DROP POLICY IF EXISTS` guard that `0002_rls.sql` and `0007_contracts_clause_review.sql` established — meaning a genuine re-run of any of these three would error. See TICKET-12 in `../30_Implementation/Backlog.md`.

## `verify_storage.py` (Part 3)

Checks bucket existence for `evidence` and `avatars`, then — only for buckets that actually exist — performs a real upload of a small, clearly-named disposable test object, downloads it back, verifies the bytes match exactly, checks the public URL resolves, and deletes the test object. Never creates a missing bucket itself (that's a real, consequential infrastructure change outside a verification script's remit — see TICKET-10) and never attempts upload/download against a bucket that doesn't exist (that would just restate "the bucket is missing," not test anything new).

## `verify_llm_providers.py` (Part 4)

One real, minimal call (a few tokens) to each of Gemini, Groq, SambaNova, Cerebras, and one real minimal search call to Indian Kanoon. Reports configured/reachable/latency/failure-reason per provider, plus a distinct "does the failover chain have at least one working tier" check — because a single dead tier (see TICKET-11, Cerebras) has zero practical impact on `generate()` if the tiers ahead of it work, and collapsing that nuance into one boolean would misrepresent the system's actual resilience.

**Cost note:** every call here is real and minimal by design, but it is still a real call against real (usually free-tier) quota. Don't run this in a tight loop.

## `verify_runtime.py` (Part 1/7)

The odd one out: it doesn't talk to Supabase/LLM providers/storage directly at all — it talks to a *running instance of the VidhiDesk API* the way a real client would (`GET /health`, `GET /openapi.json`, an unauthenticated request to a protected route to confirm the auth boundary actually rejects it). Base URL is configurable via `RUNTIME_VERIFY_BASE_URL` (or passed directly to `run(base_url=...)`); defaults to `http://localhost:8000`. `verify_project.py` starts its own ephemeral local `uvicorn` instance for this rather than assuming one is already running — see `Runtime_Health_Check.md`.

## `verify_project.py` — the orchestrator

Runs all of the above (starting and tearing down its own local server for `verify_runtime.py`) plus the full backend `pytest` suite, and produces the consolidated Health Report described in `Runtime_Health_Check.md`. The aggregation rule is fixed in `verify_common.VerificationResult.overall` and cannot be bypassed by an individual script: any `FAIL` anywhere makes the overall result `FAIL`. There is no code path that produces an overall `PASS` while a section underneath it failed.
