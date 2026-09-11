> **Title:** Deployment Verification Guide
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for how CI verification connects to deployment
> **Related Documents:** [`Infrastructure_Verification.md`](Infrastructure_Verification.md), [`Runtime_Health_Check.md`](Runtime_Health_Check.md), [`Deployment.md`](Deployment.md), [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

---

# Deployment Verification Guide

## Where credentials actually live (a correction worth stating plainly)

`api/app/config.py` loads environment variables from the **monorepo-root `.env`**, not `api/.env` (`find_dotenv(usecwd=True)` walks up from wherever the process starts). Two earlier validation sessions (Sprint 3.5.5, Sprint 3.5.5A's initial framing) checked `api/.env` specifically, found nothing, and incorrectly concluded no credentials were configured. They were configured the whole time, at the repo root. If you're debugging "why does nothing have credentials," check the repo root first.

## The CI pipeline (`.github/workflows/ci.yml`)

```
Lint  →  Unit Tests  →  Migration Verification  →  Infrastructure Verification  →  Deployment  →  Runtime Verification
                    ↘_____________________________↗
```

- **Lint**: backend import sanity (no dedicated Python linter configured yet — see the technical debt report for this gap) + frontend `npm run lint`.
- **Unit Tests**: `python -m pytest tests/ -q` (backend) + `npm run build` (frontend typecheck + static generation).
- **Migration Verification**: `verify_migrations.py` — static file checks, no secrets needed, runs in parallel with the credential-requiring jobs below it in the dependency graph.
- **Infrastructure Verification**: `verify_database.py` + `verify_storage.py` + `verify_llm_providers.py` — needs real credentials as GitHub Secrets (see below).
- **Deployment** / **Runtime Verification**: see the honesty note below — this half of the pipeline is not fully wired yet, and the workflow file says so explicitly rather than silently pretending it is.

### GitHub Secrets this workflow expects

Same set the pre-existing `.github/workflows/recheck_citations.yml` already uses (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`), extended with `GEMINI_API_KEY`, `GROQ_API_KEY`, `SAMBANOVA_API_KEY`, `CEREBRAS_API_KEY`, `INDIAN_KANOON_API_TOKEN`. None of these have been added to this repository's GitHub Secrets as part of this sprint — that's a repository-settings action outside what a file-only change can do. Until they're added, the `infrastructure_verification` job will fail with empty-credential errors, correctly, per this project's "never produce a false PASS" rule — it should not be treated as a workflow bug when that happens before the secrets exist.

## What "Deployment" does and does not mean in this pipeline right now

**Update (2026-09-11):** the backend migrated off Render to a GCP Compute Engine VM behind Caddy/HTTPS on 2026-09-05/06 — see `Deployment.md` for the authoritative, current story. The backend is now deployed by `.github/workflows/gcp-deploy.yml`, which triggers on this CI workflow completing successfully on `main`, so backend deploys ARE gated on CI passing. The paragraph below describes the pre-migration state (Render auto-deploy) and is kept for history; only Vercel's frontend auto-deploy-on-push is still independent of this workflow today.

Render and Vercel previously auto-deployed directly from a push to `main`, through their own git integration — entirely outside GitHub Actions. That meant, as configured then, **a bad push still reached production regardless of what this CI workflow reported.** The `deploy_gate` job exists as a status marker and a place to wire real gating into. To close the remaining (frontend) gap, do one or both of:

1. **Branch protection on `main`** (GitHub repo Settings → Branches → Branch protection rules) requiring this workflow's jobs to pass before a merge is allowed. This is the standard, low-effort fix — it doesn't stop Vercel's own auto-deploy-on-push-to-main, but it does stop a broken PR from *reaching* `main` in the first place, which is most of the practical value.
2. **Switch Vercel from auto-deploy-on-push to a deploy hook**, triggered only from the `deploy_gate` job after it passes. Not done — it's a real, deliberate change to how production deploys are triggered, and belongs to whoever owns that decision (Nitesh/Keshav), not to a verification-framework sprint.

## `runtime_verification`'s target

Points `RUNTIME_VERIFY_BASE_URL` at `https://vidhidesk-api.duckdns.org` (the confirmed-live backend per `10_Architecture/Runtime_Architecture.md` — a GCP Compute Engine VM behind Caddy/HTTPS, migrated from Render 2026-09-05/06) and runs `verify_runtime.py` against it for real — this job only runs on push to `main`, after `deploy_gate`, so it's checking the state of production after whatever the GCP deploy pipeline just did, not a staging environment (this project has no separate staging environment; see the technical debt report for this as a noted gap, not something fixed here).
