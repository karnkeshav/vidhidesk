> **Title:** Deployment
> **Version:** 1.1
> **Status:** Active — partial (see remaining gaps below; CI now exists, full deploy-gating does not yet)
> **Owner:** Keshav
> **Audience:** Engineers, operations
> **Last Updated:** 6 August 2026 (Sprint 3.5.5B)
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
