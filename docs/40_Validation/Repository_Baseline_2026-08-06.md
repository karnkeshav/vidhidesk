> **Title:** Repository Baseline — Sprint 3.5.5B
> **Version:** 1.0
> **Status:** Active — snapshot as of this date; supersede with a newer dated baseline rather than editing this one in place
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for the engineering state of the project as of this sprint
> **Related Documents:** [`README.md`](README.md), [`Technical_Debt_Report_2026-08-06.md`](Technical_Debt_Report_2026-08-06.md), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Repository Baseline — 6 August 2026

## Versions

| Component | Version / State |
|---|---|
| Architecture | Per `10_Architecture/Engineering_Architecture_Handbook.md` — unchanged this sprint (no architecture redesign performed, per this sprint's own rules) |
| Database (live schema) | 13 of 17 expected tables present in production. Migrations `0001`–`0012` fully applied and verified; `0013`/`0014` (Litigation) **not applied** — TICKET-9 |
| Migration files (repository) | 14 files, `0001`–`0014`, sequentially numbered with no gaps or duplicates (verified live this sprint — see the Technical Debt Report's T-2 correction) |
| API | 27 routes registered (26 application routes + `/health`), confirmed via a real `/openapi.json` fetch against a locally-started instance this sprint |
| Frontend | 13/13 static routes building cleanly, 0 ESLint errors (per Sprint 3.5.3's last full build check — not re-run this sprint since no frontend code changed) |
| Validation | One full acceptance-testing round completed for the deterministic layer only (Sprint 3.5.5); AI-dependent layer still unvalidated (Sprint 3.5.5A found the reason: database/storage provisioning gaps, now diagnosed with a reusable tool in this sprint) |
| Documentation | `docs/` hierarchy at the structure established in the documentation-refactor sprint, now with `40_Validation/` added; two stale claims corrected this sprint (see Technical Debt Report T-2) |
| Backend test suite | 214/214 passing (verified live this sprint, `python -m pytest tests/ -q`, ~1 minute runtime) |
| Infrastructure verification framework | New this sprint: 6 real verification scripts + 1 orchestrator in `api/scripts/`, all executed for real against production during this sprint (see `Technical_Debt_Report_2026-08-06.md`'s evidence and the raw output preserved alongside this baseline) |

## Outstanding backlog (as of this baseline)

| Ticket | Description | Severity | Status |
|---|---|---|---|
| TICKET-7 | UP/Bihar missing from Forum Advisor's state table | Major | Open |
| TICKET-8 | AI Case Analysis blind to hearing/IA data | Major | Open |
| TICKET-9 | Litigation migrations never applied to production | Critical | Open |
| TICKET-10 | No Supabase Storage buckets provisioned | Major | Open |
| TICKET-11 | `CEREBRAS_API_KEY` invalid | Minor | Open |
| TICKET-12 | Three migrations violate RLS-policy idempotency convention | Major | Open |

Full detail for every ticket: `30_Implementation/Backlog.md`.

## Known limitations (standing, not new to this sprint)

- No pleading generation (by design — `ADR-011`, gated on full validation)
- Phase 1 state coverage: Delhi, Maharashtra, UP officially in scope; Forum Advisor's actual pecuniary-limits table only covers Delhi/Maharashtra/Karnataka + a generic default (TICKET-7 is the UP-specific instance of this gap)
- RERA and Consulting modules: designed only, no implementation
- No staging environment (Technical Debt Report T-8)
- No dedicated Python linter (Technical Debt Report T-6)
- No dependency vulnerability scan performed (Technical Debt Report T-7)

## Deployment status

Frontend (Vercel) and backend (Render) both confirmed live and auto-deploying from `main`. CI pipeline now exists (`.github/workflows/ci.yml`, new this sprint) covering Lint/Unit Tests/Migration Verification/Infrastructure Verification automatically; the Deployment/Runtime Verification stages are structurally present but not yet a real gate on production deploys — see `40_Operations/Deployment_Verification_Guide.md` for exactly what's missing (branch protection or a deploy-hook secret, neither of which a documentation/tooling sprint can configure).

## Production readiness score

**Not a single number** — a single score would flatten two very different kinds of readiness that this sprint went to some length to keep separate:

- **Infrastructure/engineering readiness for the Litigation feature set: not ready.** Concrete, diagnosed, low-effort-to-fix blockers (TICKET-9, TICKET-10) prevent the feature from being exercised in production at all right now. This is the part `verify_project.py`'s `Validation Ready: NO` result measures, honestly.
- **Contracts module production readiness: ready and has been since Sprint 3.5.3** — 214/214 tests passing, live schema fully verified this sprint (13/13 non-litigation tables, both RPCs, RLS enforcing correctly on every checkable table), no new defects found.
- **AI Case Analysis *quality* readiness: unknown**, not "not ready" — Sprint 3.5.5/3.5.5A never got to execute it against real infrastructure, and this sprint's rules explicitly forbade attempting that (no new features, no business-logic changes). This remains the biggest open question blocking `ADR-011`'s pleading-generation gate.

If a single qualitative label is required: **HOLD**, same call as the prior two validation rounds, now backed by a reusable, re-runnable tool (`verify_project.py`) instead of a one-off manual check — and now with a precise, evidenced punch list instead of an open-ended "something's wrong somewhere."

## Recommendation for the next development sprint

1. Apply TICKET-9 and TICKET-10 (migrations + storage buckets) — both are provisioning actions, not code changes, and both are now precisely diagnosed with exact commands (`Recovery_Procedure.md`).
2. Re-run `python scripts/verify_project.py` and confirm `Validation Ready: YES`.
3. **Only then** run Sprint 3.5.5A's originally-intended full 26-scenario validation round for real — this is the actual next sprint that matters, and everything in Sprint 3.5.5B exists to make sure that round measures genuine AI quality instead of tripping over infrastructure gaps partway through, the way 3.5.5A did.
4. Fix TICKET-12 (migration idempotency) and TICKET-11 (Cerebras key) opportunistically — low effort, don't need to block anything above.
5. Decide on TICKET-7's scope question (does UP need real pecuniary data before Litigation ships, or is the documented fallback acceptable for now) — a product decision, not an engineering one.
