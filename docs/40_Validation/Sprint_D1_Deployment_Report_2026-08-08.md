> **Title:** Sprint D1 — Production Synchronization Deployment Report
> **Version:** 1.0
> **Status:** Final for this sprint
> **Owner:** Keshav (executed) / Nitesh (to review before Sprint 3.5.6 begins)
> **Audience:** Nitesh, Keshav, future AI agents assessing release readiness
> **Last Updated:** 8 August 2026
> **Canonical Reference:** Yes, for what Sprint D1 actually did to production and what it found
> **Related Documents:** [`Production_Recovery_Plan_2026-08-07.md`](Production_Recovery_Plan_2026-08-07.md), [`Gap_Analysis_2026-08-07.md`](Gap_Analysis_2026-08-07.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md) (TICKET-9/10 closed, TICKET-13/14/15 filed), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md) (Evidence E35)

---

## 1. Deployment execution log

Chronological, real actions taken against the real production Supabase
project (`pgwemjswxdlnshrfoggj`), in order:

1. **Baseline re-verification.** `verify_project.py` run once more before
   any change, confirming `Gap_Analysis_2026-08-07.md`'s state still
   held: 4 litigation tables missing, 0 storage buckets.
2. **Migration `0013_litigation_schema.sql` applied** via
   `supabase db query --linked --file api/migrations/0013_litigation_schema.sql`
   (Management API — the sanctioned execution path, since this
   environment has no raw `DATABASE_URL`/Postgres password). Verified by
   direct SQL query against the live catalog: `litigation_parties`,
   `litigation_facts_evidence`, `litigation_hearings` all present with
   expected columns; 7 new columns on `matters`; 3 indexes; 12 RLS
   policies, all present with exact expected names.
3. **Migration `0014_litigation_case_analysis.sql` applied** the same
   way. Verified: `litigation_case_analyses` present; 4 new columns on
   `litigation_facts_evidence`; 1 index; 2 RLS policies present.
4. **Storage buckets.** `avatars` created directly
   (`insert into storage.buckets (id, name, public) values ('avatars',
   'avatars', true) on conflict (id) do nothing;`). For `evidence`, the
   sprint's required stop-and-decide gate was honored: Option A (public,
   matches the already-shipped `get_public_url()` code, ships today) vs.
   Option B (private + signed URLs, stronger confidentiality, needs a
   code change out of scope for an infrastructure-sync sprint) were
   presented; **Option A approved**. `evidence` bucket created as
   `public: true`. **TICKET-13** filed immediately per the approval,
   tracking the future migration to Option B.
5. **Post-provisioning verification.** `verify_project.py` re-run:
   Environment PASS, Database PASS, Storage PASS (real upload/download/
   cleanup round-trip against both buckets), Providers FAIL (Cerebras
   only — pre-existing TICKET-11, judged out of scope, not retried),
   Runtime PASS, Tests 214/214 PASS.
6. **Smoke test, attempt 1.** Real Supabase Auth user created
   (`e2e-smoketest-d1@vidhidesk.local`), real JWT obtained, real HTTP
   calls against a local server pointed at production: Matter → 2
   Parties → Fact (text) → Evidence (file upload) → Limitation →
   Forum all succeeded (`201`/`200`). `POST .../case-analysis` returned
   **HTTP 500** after 60.9s.
7. **Root cause diagnosis** from the server's actual stdout/stderr
   traceback (not guessed): `postgrest.exceptions.APIError: new row
   violates row-level security policy for table "pii_masks"` (`42501`),
   raised from `case_analysis.py:310`'s `mask_store.save(mask_map)`.
   Traced to `case_analysis.py:267` constructing `SupabaseMaskStore(db)`
   with the RLS-scoped `user.db` the router passes in, against a table
   that by design (`0002_rls.sql`) has zero RLS policies and is
   reachable only via the service-role client. Confirmed as an isolated
   deviation, not a systemic pattern, by checking the two other
   `SupabaseMaskStore` call sites (`matters.py:214`, `contracts.py:335`)
   — both already correct.
8. **Fix approved and applied** as a scoped exception to Sprint D1's
   "no feature development" rule, given the defect left AI Case Analysis
   completely non-functional in production. One-line change:
   `case_analysis.py:267` → `SupabaseMaskStore(service_client())`, plus
   a corrected `app/db.py` module docstring (previously, incorrectly,
   listed `pii_mask` under `user_client()`'s intended use — plausibly
   the actual source of the original mistake). Filed as **TICKET-14**,
   marked SHIPPED same day.
9. **Smoke test, attempt 2** (fresh matter, fresh throwaway user, same
   flow): `POST .../case-analysis` → **201 Created**, real Gemini
   2.5 Flash output, in 55.7s. Persistence verified directly: 1
   `litigation_case_analyses` row, 9 `pii_masks` rows, both confirmed
   via service-role query (not just trusting the 201 response). Party
   names round-tripped correctly (masked in the LLM prompt, restored in
   the response).
10. **Full backend suite re-run**: 214 unit/integration tests pass; 1
    pre-existing e2e (`test_no_auto_pdf_download.py`) fails on a
    Playwright timeout waiting for a frontend dev server that was never
    started this session — read its own traceback to confirm this is
    unrelated to the fix, not silently dismissed.
11. **Cleanup**, both smoke-test rounds: both throwaway matters
    cascade-deleted (parties/facts/hearings/case-analyses all confirmed
    gone by re-query), `pii_masks` rows explicitly checked and confirmed
    zero remaining per matter, the uploaded evidence PDF removed from
    Storage, both throwaway Supabase Auth users deleted via
    `auth.admin.delete_user()`, local smoke-test server processes
    killed, temporary credential files removed from `/tmp`.

## 2. Verification report (final state, post-fix)

| Check | Result | Evidence |
|---|---|---|
| Environment | PASS | `verify_environment.py` |
| Database (live schema) | PASS | `verify_database.py` — all litigation tables/columns/indexes/RLS confirmed via direct query |
| Storage | PASS | `verify_storage.py` — real round-trip on both buckets |
| Providers | FAIL | Cerebras only (TICKET-11, pre-existing, out of scope) — Gemini/Groq/SambaNova/Indian Kanoon all PASS, failover chain has 3 working tiers |
| Runtime | PASS | `verify_runtime.py` against a live local instance |
| Tests | 214/216 | 1 unrelated pre-existing e2e failure (missing frontend dev server), confirmed unrelated by traceback |
| Smoke test (full pipeline) | PASS (2nd attempt) | Matter → Parties → Fact → Evidence upload → Limitation → Forum → AI Case Analysis, real 201, real persistence confirmed by direct query |

## 3. Remaining issues

- **TICKET-11** (Minor) — Cerebras key invalid, fourth-tier failover only, no practical impact. Not addressed this sprint; explicitly judged out of scope rather than silently ignored.
- **TICKET-12** (Major) — `0011`/`0013`/`0014` use bare `CREATE POLICY` without `DROP POLICY IF EXISTS`, unlike the project's own established idempotency convention. Not addressed this sprint (documentation/hygiene, not a live blocker since these three migrations have each only been run once).
- **TICKET-13** (Major, security posture) — `evidence` bucket is public; approved as this sprint's scope, tracked for migration to private + signed URLs before production client use.
- **TICKET-15** (Minor) — PII auto-detector over-masks some non-name capitalized phrases as `PARTY` entities. Observed, not investigated further this sprint.
- **No commit created.** All code changes (`case_analysis.py`, `db.py`) and this sprint's documentation remain uncommitted, per this session's standing rule of only committing when explicitly asked. `git status` at end of sprint shows these as the only application-code changes; everything else touched was documentation or already-untracked pre-existing work from Sprint 3.5.3.

## 4. Git commit hash

**None.** No commit was made this session. The working tree contains
the `case_analysis.py`/`db.py` fix (TICKET-14) plus this report and the
Backlog/Build Tracker updates, all uncommitted. Say the word and I will
stage and commit these with a message describing the fix and the
infrastructure sync — but per this session's standing instruction, I
will not do so without being asked.

## 5. May Sprint 3.5.6 begin?

**Yes — the infrastructure and code blockers that stopped Sprint 3.5.6
in E33 are resolved and independently re-verified.** Specifically:

- TICKET-9 (migrations missing) — closed, re-confirmed live.
- TICKET-10 (buckets missing) — closed, re-confirmed live.
- TICKET-14 (AI Case Analysis 500 on every real call) — found *this*
  sprint via the required smoke test, fixed, and re-verified end-to-end
  against real production infrastructure the same day.

Nothing else discovered this sprint blocks the 26-scenario validation
run. The two open items (TICKET-11, TICKET-15) are both classified
Minor/no-practical-impact and don't block a validation round from
proceeding. Sprint 3.5.6 can now run its full, real, 26-scenario
execution against production without hitting the wall E33 hit.
