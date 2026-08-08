> **Title:** Recovery Procedure
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for what to do when `verify_project.py` reports FAIL
> **Related Documents:** [`Runtime_Health_Check.md`](Runtime_Health_Check.md), [`Infrastructure_Verification.md`](Infrastructure_Verification.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md), [`Local_Development_Setup.md`](Local_Development_Setup.md)

---

# Recovery Procedure

Concrete fixes for every FAIL condition `scripts/verify_project.py` can currently produce. This is a runbook, not a re-explanation of *why* each check exists — see `Infrastructure_Verification.md` for that.

## Database: table/column/RPC missing

**Symptom:** `verify_database.py` reports `Table exists: <name>` or `Column exists: <table>.<col>` as `FAIL`.

**Fix:** the corresponding migration in `api/migrations/` has not been applied to this Supabase project. Apply it via the Supabase Dashboard → SQL Editor → New query, pasting the migration file's contents, per `Local_Development_Setup.md` §4. Migrations are additive and idempotent — safe to run even if you're unsure whether it already partially applied (with the caveat in TICKET-12 below for three specific files). **This is a real production database** — apply migrations deliberately, one at a time, confirming each with `verify_database.py` before moving to the next, not as a batch you don't watch.

Current known instance: `litigation_parties`, `litigation_facts_evidence`, `litigation_hearings`, `litigation_case_analyses` are missing because `0013_litigation_schema.sql` and `0014_litigation_case_analysis.sql` have never been run (TICKET-9).

## Database: RLS blocks anon → FAIL (anon-key client can read rows)

**Symptom:** `RLS blocks anon: <table>` reports `FAIL` with a nonzero row count.

**This is a security-severity finding — treat it as urgent.** It means RLS is either not enabled on that table, or its policy is not correctly scoping to the owning user / authenticated role. Check the table's RLS state in the Supabase Dashboard → Authentication → Policies, and re-apply the relevant migration's `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and `CREATE POLICY` statements if missing.

## Database: anon can execute an app RPC → FAIL

**Symptom:** `Anon cannot execute RPC: <name>` reports `FAIL`.

Also security-severity. Re-run the `REVOKE EXECUTE ON FUNCTION <name> FROM PUBLIC` and `... FROM anon` statements from the RPC's defining migration (`0004_retrieval_rpc.sql` or `0006_statute_fulltext_search.sql`) — see those files' own comments for why *both* revokes are needed (Supabase grants execute to `anon` twice, through two different mechanisms).

## Storage: bucket missing

**Symptom:** `Bucket exists: avatars` or `Bucket exists: evidence` reports `FAIL`.

**Fix:** Supabase Dashboard → Storage → New bucket. Create `avatars` and `evidence`. Match the access policy to what the application code assumes: `api/app/routers/profile.py::upload_avatar` calls `get_public_url()` on the `avatars` bucket, so it needs public read access (or a corresponding signed-URL policy if you'd rather keep it private — that would require a matching code change, out of scope for this recovery procedure). Re-run `verify_storage.py` after creating each bucket — it will perform a real upload/download round-trip automatically. (TICKET-10.)

## Providers: a specific LLM provider FAILs

**Symptom:** `verify_llm_providers.py` reports `FAIL` for one provider with an HTTP 401/403 or connection error.

1. Check the "LLM Gateway failover chain has at least one working tier" line first — if it's `PASS`, the application itself is unaffected; real requests will succeed via the next healthy tier. This is a "fix when convenient," not an outage.
2. If it's the *only* working tier that failed, or if it says `FAIL` (no tier works), this is urgent — `generate()` will fail for every real request.
3. Fix: rotate/replace the credential in the repo-root `.env` (never commit it), then re-run `verify_llm_providers.py` to confirm.

Current known instance: `CEREBRAS_API_KEY` returns `HTTP 401 Wrong API Key` — last-tier fallback only, Gemini/Groq/SambaNova all healthy, no practical impact today (TICKET-11).

## Runtime: server unreachable

**Symptom:** `verify_runtime.py` reports `GET /health` as `FAIL` with a connection error.

- **Local:** the server isn't running. `cd api && uvicorn app.main:app --reload` in one terminal, then re-run the check in another (or just run `verify_project.py`, which starts and tears down its own instance automatically).
- **Against a deployed target** (`RUNTIME_VERIFY_BASE_URL` pointed at Render): check the Render dashboard for a crashed/sleeping instance (free-tier cold starts are expected and can cause a single slow-but-not-failed first request — see `Runtime_Architecture.md`'s cold-start note; a genuine connection *refused*, not just slow, is the real failure signal).

## Migrations: idempotency WARN/FAIL

**Symptom:** `verify_migrations.py` reports an `Idempotency:` line as `WARN` or `FAIL`.

Most of these are informational (a migration that doesn't explicitly claim idempotency in its header but has no unsafe pattern either — `WARN`, low urgency, just add the header line for consistency). The one that matters: `0011_create_advocate_profiles.sql`, `0013_litigation_schema.sql`, and `0014_litigation_case_analysis.sql` use bare `CREATE POLICY` without a preceding `DROP POLICY IF EXISTS` — if any of these three is ever genuinely re-run against a database where it already applied, the `CREATE POLICY` statements will error. **This does not block a first-time apply** (which is the immediate need for TICKET-9) — it only matters if the same migration is run twice. Tracked as TICKET-12; fix is adding the same `drop policy if exists <name> on <table>;` line before each `create policy` that `0002_rls.sql`/`0007_contracts_clause_review.sql` already use as the house pattern.

## Everything failed at once

Check `verify_environment.py` first, in isolation — if the `.env` file itself is missing, wrong-located, or a credential is a placeholder, everything downstream will cascade-fail for the same root cause. Confirm you're running from a checkout with a real repo-root `.env` (not `api/.env` — see `Deployment_Verification_Guide.md`) before treating a wall of failures as five separate problems.
