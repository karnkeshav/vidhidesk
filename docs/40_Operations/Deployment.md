> **Title:** Deployment
> **Version:** 1.3
> **Status:** Active — partial (backend now live on GCP over HTTPS, not Render; CI/deploy pipeline fixed but has not yet completed a successful automated end-to-end run — see remaining gaps below)
> **Owner:** Keshav
> **Audience:** Engineers, operations
> **Last Updated:** 6 September 2026 (GCP Migration Sprint — cutover + CI/CD pipeline fixes)
> **Canonical Reference:** Yes, for the facts that are documented; explicitly not a complete deployment runbook — see remaining gaps
> **Supersedes:** N/A
> **Related Documents:** [`../10_Architecture/Runtime_Architecture.md`](../10_Architecture/Runtime_Architecture.md), [`Local_Development_Setup.md`](Local_Development_Setup.md), [`Deployment_Verification_Guide.md`](Deployment_Verification_Guide.md), [`Infrastructure_Verification.md`](Infrastructure_Verification.md), [`Runtime_Health_Check.md`](Runtime_Health_Check.md)

---

# Deployment

## Confirmed live targets

- **Frontend:** Vercel (Hobby tier), auto-deploying the `/web` Next.js app.
- **Backend:** GCP Compute Engine VM (`gcp-ai-node-1`), behind Caddy over HTTPS at `https://vidhidesk-api.duckdns.org` — Render's free tier was replaced (2026-09-05/06) after this document's original Render facts below were written; see "GCP cutover" below for the full story and verification. This paragraph is what's true now — the rest of this file below records the migration history in the order it actually happened, including the now-superseded Render facts.
- **Database/Auth/Storage:** Supabase free-tier project (shared by both frontend and backend).

Confirmed working end-to-end per `30_Implementation/Build_Tracker.md` Evidence E15 (original Render setup); GCP cutover confirmed live per this session's own `HTTP 200` check against `/version` — see below.

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

## Oracle migration — on hold; GCP migration started instead (2026-09-05)

A live SSH audit this session found the Oracle claims above were not
actually true: neither Oracle Always-Free VM (`ai-orchestration-vm`,
`sensex-bot`) has Docker installed or a vidhidesk checkout, both are
already near their ~1GB RAM ceiling running unrelated projects, and an
automated harvester script on `ai-orchestration-vm` had made 2,870+
failed attempts to obtain Oracle's larger free Ampere ARM tier (host
capacity has been exhausted in that region this whole time). The four
Oracle files above are left in place — inert, since no `ORACLE_SSH_*`
secrets exist — as a fallback if Ampere capacity ever frees up, but are
not an active migration target right now.

AWS and Azure were also surveyed and found in a similar state: a single
small instance each (`cheapest-test-instance` on AWS, t4g.nano/0.5GB RAM;
`azure-ai-node-1` on Azure, Standard_B1s/1GB, 12-month free-trial only,
not perpetual like Oracle's Always Free tier), both running unrelated
projects, neither with Docker.

Migration is now targeting a GCP Compute Engine VM instead:
`gcp-ai-node-1` (project `calm-catfish-464514-t6`, zone `us-central1-a`,
public IP `35.253.123.223`), confirmed idle this session — Ubuntu 24.04,
e2-micro, no Docker, no competing processes, ~580MB RAM free of ~955MB
total. (The other GCP VM in the account, `cbse-pyq-harvester`, is running
an unrelated project and is explicitly out of scope for this migration.)

The GCP pipeline mirrors the Oracle one exactly, retargeted:
`deploy/gcp_deploy.sh`, `.github/workflows/gcp-deploy.yml`, and
`deploy/gcp_Caddyfile` are the GCP counterparts of the three Oracle files
above (`api/scripts/check_deployment_drift.py` is reused unmodified — it
already takes a SHA and a base URL as plain arguments). Same invariants:
`git fetch` + detached-HEAD checkout by exact SHA, never `git pull`;
health-gate a candidate on a throwaway port before promoting; automatic
rollback on failure; a domain for `deploy/gcp_Caddyfile` does not exist
yet, so HTTPS is not live.

As with the Oracle files, **treat every claim in the GCP files as only as
verified as what was actually SSH-checked in this session** — this
section exists specifically because the Oracle files' earlier "verified
against the real box" language turned out to be false, and that mistake
should not repeat here. The cutover described below supersedes the
"Render remains the live production backend" claim above — Render's
role after the cutover is documented in the next section.

## GCP cutover — live in production (2026-09-05/06)

The first cutover attempt failed immediately: pointing Vercel's
`NEXT_PUBLIC_API_URL` straight at the GCP box's bare HTTP IP broke every
API call from the HTTPS-served frontend — browsers hard-block a
`fetch`/XHR from an HTTPS page to a plain-HTTP endpoint (mixed content),
failing in ~1ms before any network activity, confirmed via a direct JS
test in the browser console. This is a browser-level security policy,
not a bug to route around.

Fixed by giving the GCP box a real HTTPS endpoint instead of an IP:
free dynamic DNS via DuckDNS (`vidhidesk-api.duckdns.org` →
`35.253.123.223`), Caddy as a reverse proxy in front of the API
container (`deploy/gcp_Caddyfile`) obtaining and renewing a Let's
Encrypt certificate automatically, and the prod container itself
rebound from `-p "${PROD_PORT}:8000"` (publicly exposed, bypassing
Caddy) to `-p "127.0.0.1:${PROD_PORT}:8000"` (loopback-only, reachable
only through Caddy) in both `deploy/gcp_deploy.sh` and
`deploy/oracle_deploy.sh`.

**Confirmed live as of this writing:** `https://vidhidesk-api.duckdns.org/version`
returns `HTTP 200` over real HTTPS, and Vercel's `NEXT_PUBLIC_API_URL`
(production) was last updated ~21 hours before this note — set to this
HTTPS URL, then the production deployment was rebuilt with `vercel
redeploy --target production` so the new value actually took effect at
build time (a bare promote does not re-evaluate env vars). **Render is
no longer the live backend the frontend talks to.** Its free-tier
512MB RAM / 0.15 vCPU limits were confirmed (via the Render dashboard)
too small for this app's `sentence-transformers` + `spacy` + `torch`
dependencies, visible as a repeating "Instance failed" OOM crash-loop
in Render's own Event Timeline every 2-5 minutes — this, not just
cost or CI/CD control, is what made staying on Render untenable
regardless of the pipeline work below. The Render service has not been
deleted (no destructive action taken), but nothing points at it anymore.

## GCP deploy pipeline — six bugs found and fixed; automated end-to-end run not yet demonstrated

Getting `.github/workflows/gcp-deploy.yml` to actually deploy on push
took six separate, independent fixes, in the order found:

1. **Invalid `if:` syntax silently killed every automated run.**
   `if: ${{ secrets.GCP_BASE_URL != '' }}` on a step is not valid GitHub
   Actions syntax (`Unrecognized named-value: 'secrets'`) — `push`/
   `workflow_run` triggers swallowed this into a bare "failure" with
   zero jobs and no visible error; only a manual `workflow_dispatch` run
   surfaced the real HTTP 422 parse error. Fixed by moving the
   empty-string check into the shell script body instead
   (`gcp-deploy.yml`, `oracle-deploy.yml`).
2. **`GCP_SSH_KEY` secret was corrupted by a UTF-8 BOM.** Setting it via
   a PowerShell pipe into `gh secret set` silently prepended a BOM,
   producing `ssh: no key found` on every SSH step. Fixed by writing the
   key to a file with `[System.IO.File]::WriteAllText(path, content,
   (New-Object System.Text.UTF8Encoding $false))` and piping that file
   in via `cmd /c "gh secret set ... < file"` (true OS redirection, no
   PowerShell pipe involved) — regenerated and reset once this way.
3. **SSH step's default 10-minute timeout was too short for a
   cold-cache Docker build.** A from-scratch `pip install` of `torch` +
   `spacy` + `sentence-transformers` measured past 10 minutes on the
   box's shared 2-vCPU capacity, confirmed by a real `workflow_dispatch`
   run that hit "Run Command Timeout" mid-`pip install`. Fixed by
   raising `appleboy/ssh-action`'s `command_timeout` to `20m`.
4. **`unit_tests` job had no Supabase secrets wired in at all.** CI
   failed 32 tests with `"supabase_key is required"` — two layered
   causes: `SUPABASE_URL`/`SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_KEY`
   didn't exist as GitHub secrets yet, and even after adding them the
   `unit_tests` job's `env:` block never referenced them (only
   `infrastructure_verification` did). Fixed by adding them as repo
   secrets and mirroring the same `env:` block into `unit_tests`
   (`.github/workflows/ci.yml`). Result: 32 failed → 1 failed, 598
   passed.
5. **Deploy/rollback scripts crashed under `set -e` on a first-ever
   deploy.** `rollback_to_previous()` assumed a `-previous` container
   already existed; extracted a shared helper (mirrored into both
   `deploy/gcp_deploy.sh` and `deploy/oracle_deploy.sh`) that checks
   `docker inspect` first.
6. **Post-promotion health check was a single 3-second sleep.** Real
   cold start measured ~25s; extended to a 20-try/3s retry loop (60s
   budget), matching the pre-promotion candidate health-gate.

**Current, verified state of the automated pipeline (checked via `gh run
list`, not assumed):** the latest push to `main` (`478ca5f`, this
session) still fails CI — `infrastructure_verification`'s
`test_golden_patterns` fails with `Illegal header value b'Bearer '`
because the four LLM provider secrets it needs
(`GEMINI_API_KEY`/`GROQ_API_KEY`/`SAMBANOVA_API_KEY`/`CEREBRAS_API_KEY`)
and `INDIAN_KANOON_API_TOKEN` are not yet added as GitHub secrets. Since
`gcp-deploy.yml` only fires on a `workflow_run` of CI completing with
`conclusion: success`, every automated GCP deploy run to date shows as
`skipped`, and the one manual `workflow_dispatch` attempt was
cancelled — **an automated push-to-deploy run has not yet completed
successfully end-to-end.** The container currently live and healthy on
the GCP box (`vidhidesk-api:3365d7f...`, confirmed via `docker ps` —
`Up 21 hours (healthy)`, bound to `127.0.0.1:8000` behind Caddy) was
deployed by hand over SSH during this session, at a commit predating
the CI/pipeline fixes above, not by this workflow. Adding the five
missing LLM/Indian-Kanoon secrets so CI goes green is the direct next
step to prove the full push → CI → deploy chain end-to-end; tracked in
`Backlog.md`.

## Two-step CNR search/save (Litigation, 2026-09-06)

Motivated by a real-CNR test (`DLHC010163362026`) that revealed a stale
bug: re-entering an existing tracked matter's CNR field with a different
CNR that then failed to look up left the *previous* CNR's court data
(`provider_metadata`) sitting in place under the new, failed CNR — a
silent, misleading stale-data bug. Fixed at the data layer
(`court_sync.py`'s failure branch now explicitly nulls
`provider_metadata`; `court_tracking.py::update_tracking` resets
`sync_status`/`provider_metadata`/`last_synced_at`/`last_error` to fresh
defaults whenever `cnr_number` is present in an update payload).

Separately, this raised a product question: should every CNR an advocate
searches get saved to their matter, even ones they were just checking
and don't want tracked? Resolved by splitting the single "save" action
into two: a new `GET /api/court-lookup-preview` endpoint
(`court_tracking.py`) that looks up a CNR and returns court/party/status
details **without persisting anything** (covered by a dedicated test
asserting `court_case_tracking` stays empty), and the existing save
endpoint, now only called once the advocate confirms the preview looks
right. The frontend (`matter-workspace.tsx`) replaced the single
input+button with a Search → preview card (parties/court/status) →
"Looks right — Save & Track" / "Discard" flow; editing the CNR after a
preview clears it.
