> **Title:** Runtime Health Check
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents, anyone about to start a validation round
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for how to run and read the consolidated health report
> **Related Documents:** [`Infrastructure_Verification.md`](Infrastructure_Verification.md), [`Recovery_Procedure.md`](Recovery_Procedure.md), [`Release_Gates.md`](Release_Gates.md), [`../40_Validation/README.md`](../40_Validation/README.md)

---

# Runtime Health Check

## Run this before starting any validation round

```
cd api
python scripts/verify_project.py
```

One command, no flags needed for local use (it reads the repo-root `.env` automatically, starts and tears down its own local server for the runtime check). Exit code `0` means every section either `PASS`ed or was correctly `SKIP`ped with a stated reason; any other exit code means at least one section genuinely failed — check the section reports above the summary for exact evidence, not just the final line.

## Reading the output

Each section (`Environment`, `Migrations`, `Database`, `Storage`, `Providers`, `Runtime`, `Tests`) reports its own `PASS`/`FAIL`/`WARN`, followed by a consolidated `VIDHIDESK HEALTH REPORT` block and a final `Validation Ready: YES/NO` line. **`YES` requires every section to be clean** — a single `FAIL` anywhere anywhere makes it `NO`, by design (`verify_common.VerificationResult.overall` — see `Infrastructure_Verification.md`). A `WARN`-only run still exits non-zero; don't treat exit code `0` and "no WARNs at all" as the same question.

A real run of this command, captured 6 August 2026 as part of Sprint 3.5.5B, is preserved verbatim in `docs/40_Validation/Health_Report_Raw_Output_2026-08-06.txt` for reference — that run's actual result was `Environment: PASS`, `Migrations: WARN`, `Database: FAIL`, `Storage: FAIL`, `Providers: FAIL`, `Runtime: PASS`, `Tests: 214/214 PASS`, overall `FAIL` / `Validation Ready: NO`. If your own run differs from that, that's expected and correct — it means the state of the real infrastructure has changed (hopefully for the better, e.g. after applying TICKET-9/10/11's fixes per `Recovery_Procedure.md`).

## Running an individual section

Every `verify_*.py` in `api/scripts/` is independently runnable when you only need one answer, not the whole picture:

```
python scripts/verify_environment.py     # no credentials or network needed
python scripts/verify_migrations.py      # no credentials or network needed — reads migration files only
python scripts/verify_database.py        # needs SUPABASE_URL / SUPABASE_SERVICE_KEY
python scripts/verify_storage.py         # needs the same Supabase credentials
python scripts/verify_llm_providers.py   # needs the four LLM keys + Indian Kanoon token — makes real, minimal, billable-quota calls
python scripts/verify_runtime.py         # needs a server already running; point RUNTIME_VERIFY_BASE_URL at it, or leave default for localhost:8000
```

## When to run this

- Before starting a `docs/30_Implementation/Acceptance_Testing/` validation round (this is exactly what Sprint 3.5.5A should have run first, and didn't have — see `docs/40_Validation/Go_No_Go_Decision.md` for how that played out).
- After applying a migration, provisioning storage, or rotating a credential — to confirm the fix actually landed, not just that you believe it did.
- In CI, on every push to `main` (`.github/workflows/ci.yml`'s `infrastructure_verification` job runs `verify_database.py`, `verify_storage.py`, and `verify_llm_providers.py`; `migration_verification` runs `verify_migrations.py` separately since it needs no secrets).

## What "Validation Ready: YES" actually certifies — and what it doesn't

It certifies that the infrastructure the AI Case Analysis pipeline depends on is present, reachable, and passing its own unit tests. It does **not** certify AI output quality, hallucination rate, or citation correctness — those need an actual validation round against the Acceptance Testing Guide (`docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`), which is a separate, larger exercise this health check is a prerequisite for, not a substitute for. See `Release_Gates.md`.
