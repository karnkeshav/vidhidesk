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

Render and Vercel currently auto-deploy directly from a push to `main`, through their own git integration — entirely outside GitHub Actions. That means, as configured today, **a bad push still reaches production regardless of what this CI workflow reports.** The `deploy_gate` job exists as a status marker and a place to wire real gating into, not as a gate yet. To make it a real gate, do one or both of:

1. **Branch protection on `main`** (GitHub repo Settings → Branches → Branch protection rules) requiring this workflow's jobs to pass before a merge is allowed. This is the standard, low-effort fix — it doesn't stop Render/Vercel's own auto-deploy-on-push-to-main, but it does stop a broken PR from *reaching* `main` in the first place, which is most of the practical value.
2. **Switch Render/Vercel from auto-deploy-on-push to a deploy hook**, triggered only from the `deploy_gate` job after it passes. Requires generating a deploy hook URL in the Render/Vercel dashboard, adding it as a `RENDER_DEPLOY_HOOK_URL` GitHub Secret, and adding a `curl -X POST $RENDER_DEPLOY_HOOK_URL` step to `deploy_gate`. Not done in this sprint — it's a real, deliberate change to how production deploys are triggered, and belongs to whoever owns that decision (Nitesh/Keshav), not to a verification-framework sprint.

## `runtime_verification`'s target

Points `RUNTIME_VERIFY_BASE_URL` at `https://vidhidesk.onrender.com` (the confirmed-live backend per `10_Architecture/Runtime_Architecture.md`) and runs `verify_runtime.py` against it for real — this job only runs on push to `main`, after `deploy_gate`, so it's checking the state of production after whatever Render's own auto-deploy just did, not a staging environment (this project has no separate staging environment; see the technical debt report for this as a noted gap, not something fixed here).
