> **Title:** Technical Debt Report — Sprint 3.5.5B
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for this round's repository audit
> **Related Documents:** [`README.md`](README.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md), [`Repository_Baseline_2026-08-06.md`](Repository_Baseline_2026-08-06.md)

---

# Technical Debt Report — Part 9

Every finding below is backed by a real command run against the real repository during this sprint — grep/read output, a live query, or an actual script run — cited inline. This audit is real but time-boxed, not exhaustive; where depth was limited, that's stated rather than implied otherwise.

## Critical

**None found this sprint.** No hardcoded secrets, no committed credentials, no security-bypass code paths were found in the areas actually audited (see Configuration/Security below for what *was* checked).

## Major

### T-1: Three migrations violate the project's own RLS-policy idempotency convention

`0011_create_advocate_profiles.sql`, `0013_litigation_schema.sql`, and `0014_litigation_case_analysis.sql` use bare `CREATE POLICY` statements with no preceding `DROP POLICY IF EXISTS`, unlike `0002_rls.sql` and `0007_contracts_clause_review.sql`, which established that pattern specifically so migrations can be safely re-run. A genuine re-run of any of these three against a database where it already applied will error on the `CREATE POLICY` statements. Found by `api/scripts/verify_migrations.py`, a real static check, not a manual read. Filed as **TICKET-12**.

### T-2: A prior documentation claim about migration numbering was itself wrong

`20_Engineering/Database_Architecture.md` and `docs/README.md` both claimed migrations `0009_normalize_template_keys.sql` and a `0009_litigation_pleadings_and_citations.sql` shared a duplicate number prefix. Running `verify_migrations.py` for real found **no such duplicate exists** — the second file was never created; the real litigation migrations are `0013`/`0014`, correctly numbered. The original claim was sourced from `LITIGATION_ARCHITECTURE.md`'s *planned* migration name, never cross-checked against the actual `api/migrations/` directory. **Corrected in both documents this sprint.** Classified Major rather than Minor because it's a case of documentation actively asserting something false, not merely being incomplete — the exact failure mode this project's evidence-tagging discipline exists to catch, caught against itself.

## Minor

### T-3: Two backend endpoints appear unused by the frontend

`GET /api/citations/render` and `GET /api/retrieve` (from `api/app/routers/citations.py` and `api/app/routers/retrieval.py` respectively) do not appear anywhere in `web/src/` — no `fetch`/`authedFetch` call references either path. Checked by grepping the full frontend source tree for both path strings; zero matches for either. This may be intentional (an endpoint built ahead of its UI, or meant for direct/admin/future use) rather than genuinely dead — not enough evidence either way to classify higher than Minor. Worth a decision: wire it up, document it as intentionally headless, or remove it.

### T-4: Advocate Profile page bypasses the shared `api.ts` fetch helper

Every other frontend feature routes its backend calls through `web/src/lib/api.ts`'s `authedFetch()` helper (consistent auth-header attachment, consistent error handling). `web/src/app/profile/page.tsx` instead makes three raw `fetch()` calls directly (`/api/profile` GET/PUT, `/api/profile/avatar` POST), duplicating the auth-header logic inline rather than reusing the shared helper. Not a functional bug — found no evidence it behaves incorrectly — but it is inconsistent with the pattern the rest of the frontend follows, and duplicated logic in the one place is exactly what `Repository_Standards.md`'s own conventions ask new code to avoid.

### T-5: Advocate Profile schema drift already self-documented, still open

`advocate_profiles` was created with 9 additional fields (`enrollment_state`, `enrollment_year`, `high_court_roll_no`, `aor_code`, `firm_name`, `practice_areas`, `states_of_practice`, `languages_spoken`, `rera_advocate_reg_no`) in migration `0011`, all deliberately dropped again by `0012` "to match active production database state" per that migration's own header. Confirmed via `verify_database.py`'s live column check — the drops are correctly applied. Not new debt, but worth flagging as a pattern: this is the second instance (after the `case_analysis`/`draft_versions` design note from Sprint 3.5.3) of a table being scoped down after initial design rather than designed right the first time. Not itself actionable — just worth naming as a recurring shape.

## Observation

### T-6: No dedicated Python linter configured

`.github/workflows/ci.yml`'s `lint` job runs a bare import-sanity check for the backend (`python -c "from app.main import app"`) because there is no `ruff`/`flake8`/`pylint` configuration anywhere in the repository. The frontend has real linting (`npm run lint`, ESLint, 0 errors per every prior sprint's build check); the backend does not have an equivalent. Not fixed this sprint (adding a linter and then fixing everything it flags is a real scope decision, not a verification-framework task) — flagged for a future sprint to decide on.

### T-7: No dependency vulnerability scanning performed

`pip list --outdated` shows 40 packages with newer versions available (mostly minor/patch bumps — `fastapi` 0.139.2 → 0.141.1, `cryptography` 49.0.0 → 50.0.0, etc.), checked for real this sprint. No CVE/security-specific scan (`pip-audit`, `npm audit`) was run — that's a distinct check from "is a newer version available," and wasn't performed given this sprint's time-box. Recommend as a follow-up, not urgent given no specific vulnerability is known, just unconfirmed either way.

### T-8: No staging environment

Every reference to "the Supabase project" and "the deployed backend" in this documentation set (`Runtime_Architecture.md`, `Deployment.md`, this sprint's own verification scripts) refers to the single production instance — there is no separate staging/test Supabase project or Render/Vercel environment. This means `verify_database.py`/`verify_storage.py`/`verify_llm_providers.py`, run as written, always test production directly. Acceptable for a single-advocate tool at this scale (and consistent with `ADR-009`'s zero-cost posture — a second Supabase project would still be free-tier, but doubles operational surface for a one-user product), but worth naming explicitly rather than leaving implicit.

### T-9: No unused services or dead migrations found

Checked: every file in `api/app/services/` is imported by at least one other file (`case_analysis`, `citation_render`, `citations`, `contracts`, `forum`, `indian_kanoon`, `limitation`, `litigation`, `llm_gateway`, `pii_mask`, `retrieval` — all ≥1 real import found via grep). Every one of the 14 migration files is referenced by the schema `verify_database.py` confirms exists (or, for the 4 litigation tables, confirms is *supposed* to exist per TICKET-9). No file in either category appears to be dead weight. Recorded as a clean-audit finding, not skipped.

### T-10: Duplicate clause-review-preservation logic across seed scripts — already tracked, not new

`20_Engineering/Lessons_Learned.md` and `30_Implementation/Backlog.md`'s existing "Shared clause library formalization" entry already document that `_write_clauses_preserving_review()` and `_prune_orphaned_clauses()` are duplicated identically across all contract-template seed scripts. Re-confirmed present during this audit (`grep -l "_write_clauses_preserving_review" api/scripts/seed_*.py` matches all 10 seed scripts); not re-filed as a new item, since it already has one.

## What this audit did not cover (stated, not hidden)

Frontend component-level dead-code analysis (e.g., unused React props/exports) was not performed — only route/endpoint-level cross-referencing. No performance profiling. No accessibility audit. No deep dependency-tree vulnerability scan (T-7). These are reasonable follow-ups for a future sprint, not omissions this report is pretending didn't happen.
