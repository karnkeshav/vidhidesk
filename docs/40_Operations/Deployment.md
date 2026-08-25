> **Title:** Deployment
> **Version:** 1.2
> **Status:** Active — partial (see remaining gaps below; CI now exists, full deploy-gating does not yet; Oracle migration artifacts drafted but unexecuted)
> **Owner:** Keshav
> **Audience:** Engineers, operations
> **Last Updated:** 25 August 2026 (Oracle Migration Sprint)
> **Canonical Reference:** Yes, for the facts that are documented; explicitly not a complete deployment runbook — see remaining gaps
> **Supersedes:** N/A
> **Related Documents:** [`../10_Architecture/Runtime_Architecture.md`](../10_Architecture/Runtime_Architecture.md), [`Local_Development_Setup.md`](Local_Development_Setup.md), [`Deployment_Verification_Guide.md`](Deployment_Verification_Guide.md), [`Infrastructure_Verification.md`](Infrastructure_Verification.md), [`Runtime_Health_Check.md`](Runtime_Health_Check.md)

---

# Deployment

## Confirmed live targets

- **Frontend:** Vercel (Hobby tier), auto-deploying the `/web` Next.js app.
- **Backend:** Render (free tier), auto-deploying the `/api` FastAPI app — live at `vidhidesk.onrender.com`.
- **Database/Auth/Storage:** Supabase free-tier project (shared by both frontend and backend).

Confirmed working end-to-end per `30_Implementation/Build_Tracker.md` Evidence E15.

## CI pipeline now exists — see `Deployment_Verification_Guide.md`

As of Sprint 3.5.5B, `.github/workflows/ci.yml` runs Lint → Unit Tests → Migration Verification → Infrastructure Verification → Deployment → Runtime Verification on every push/PR to `main`. Full detail, including exactly what is and isn't wired yet, lives in [`Deployment_Verification_Guide.md`](Deployment_Verification_Guide.md) — not duplicated here.

## Remaining gap — deployment is not actually gated on CI passing yet

Render/Vercel auto-deploy directly from a push to `main`, independent of GitHub Actions — a bad push currently still reaches production regardless of what the new CI workflow reports. Closing this needs either branch protection on `main` or a Render/Vercel deploy-hook wired to the workflow's `deploy_gate` job, both of which require access this documentation change doesn't have (repo settings, and a deploy-hook secret respectively). See `Deployment_Verification_Guide.md` for the exact two options and what each needs. No rollback procedure is documented yet either — see `Recovery_Procedure.md` for what recovery guidance does exist (infrastructure-state fixes), which is not the same thing as a deployment rollback runbook.

## Oracle migration — draft artifacts exist, none of it is live yet

The Oracle Migration Sprint's target is to replace Render with a
self-hosted backend on an Oracle Cloud VM, fronted by Caddy over HTTPS,
with every deploy traceable to an exact Git SHA and drift between
GitHub's `main` and Oracle's running commit actively checked for. As of
this note, the backend already carries what that migration needs
(`GET /version`, `api/Dockerfile`'s `GIT_COMMIT_SHA` build ARG), and four
supporting files have been **authored but never executed or applied**,
because no session doing this work has had SSH access to a real Oracle
VM, a domain/DNS registrar, or Vercel/Render dashboard env-var access:

- `.github/workflows/oracle-deploy.yml` — SSH-deploy workflow, gated on
  the existing CI workflow succeeding on `main`.
- `deploy/oracle_deploy.sh` — the on-box script it invokes: `git fetch` +
  `git checkout --detach <SHA>` (never `git pull`), Docker build tagged
  with that SHA, health-gate on a throwaway port before promoting, and
  automatic rollback if the promoted container fails its own check.
- `deploy/Caddyfile` — draft reverse proxy + automatic HTTPS config;
  still has a placeholder domain, since no real one exists yet.
- `api/scripts/check_deployment_drift.py` — compares GitHub `main`'s HEAD
  SHA against Oracle's own `GET /version` response, in the same
  `verify_*.py` Status/VerificationResult shape as every other script in
  `api/scripts/`.

**Render is still the live production backend and must not be
disconnected until Oracle + Vercel's cutover passes real verification.**
Each file above says so in its own header comment — treat all four as a
draft for a human with Oracle/DNS/Vercel access to review, dry-run, and
adjust before ever wiring them live, not as something already proven to
work.
