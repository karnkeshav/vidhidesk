# VidhiDesk Documentation

This is the documentation homepage. If you are new to this project — human or AI agent — start here.

## How this hierarchy is organized

```
docs/
├── 00_Product/        — why this exists, what it does, where it's going
├── 10_Architecture/    — how the system is shaped, cross-cutting
├── 20_Engineering/     — standards engineers follow day to day
├── 30_Implementation/  — sprint/build status, module-specific technical design, decision records
├── 40_Operations/      — running, deploying, and gating releases of the thing
├── 40_Validation/      — dated product-validation round evidence (acceptance-testing execution records, metrics, defect logs, go/no-go decisions)
├── 50_Reference/       — design system, UI governance, navigation
├── 90_Historical/      — superseded documents, preserved for the record
└── golden_tests.json   — NOT documentation; a runtime test fixture (see exception below)
```

The number prefixes are a reading-priority ordering, not a strict folder importance ranking: `00_Product` is where you should start if you're new, `90_Historical` is where you go only if you need to understand *why* a decision changed.

## Reading order for a new contributor

1. [`00_Product/Product_Constitution.md`](00_Product/Product_Constitution.md) — the values every decision must fit inside.
2. [`00_Product/Product_Vision.md`](00_Product/Product_Vision.md) — what the four modules actually do.
3. [`10_Architecture/Engineering_Architecture_Handbook.md`](10_Architecture/Engineering_Architecture_Handbook.md) — how the system is shaped, then follow into `Business_Architecture.md` / `AI_Architecture.md` / `Runtime_Architecture.md` as needed.
4. [`30_Implementation/Build_Tracker.md`](30_Implementation/Build_Tracker.md) — what's actually built right now, evidence-tagged.
5. [`20_Engineering/`](20_Engineering/) and [`40_Operations/Local_Development_Setup.md`](40_Operations/Local_Development_Setup.md) — before writing any code.
6. [`30_Implementation/ADR/`](30_Implementation/ADR/) — read individually as you touch the area each decision governs.

## Reading order by audience

| Audience | Start here |
|---|---|
| Founders / product leaders | `00_Product/` in full, then `00_Product/Roadmap.md` |
| Architects | `10_Architecture/` in full, then `30_Implementation/ADR/` |
| Engineers (new) | The 6-step order above |
| Engineers (returning, checking status) | `30_Implementation/Build_Tracker.md` directly |
| Legal expert (Nitesh) | `00_Product/Product_Constitution.md` §5–§6, `00_Product/Product_Vision.md` — everything else is implementation detail |
| Designers | `50_Reference/UI_UX_Guidelines.md`, `50_Reference/Stitch_Guidelines.md` |
| QA | `40_Operations/Release_Gates.md`, `20_Engineering/Lessons_Learned.md`, `30_Implementation/Acceptance_Testing/`, `40_Validation/` |
| Future AI agents | This file, then whichever of the above matches the task at hand — do not assume a document's filename alone tells you its status; check its metadata header |

## Documentation Precedence Policy

When two documents conflict, resolve in this order — highest wins:

1. **[`00_Product/Product_Constitution.md`](00_Product/Product_Constitution.md)** — enduring values. Overrides everything, including anything below that contradicts it.
2. **[`10_Architecture/Engineering_Architecture_Handbook.md`](10_Architecture/Engineering_Architecture_Handbook.md)** — cross-cutting architecture (and its companion documents: Business/AI/Runtime Architecture).
3. **[`30_Implementation/ADR/`](30_Implementation/ADR/)** — individual architecture decisions. These are more specific than the Handbook and should be consulted when the Handbook is silent on a detail.
4. **`20_Engineering/` standards** (Technical, API, Database, Repository) — how to build within the architecture above.
5. **`30_Implementation/Technical_Design/`** — module-specific technical designs (e.g. Litigation Module Architecture). More specific than general engineering standards, but must not contradict the Architecture layer above.
6. **`30_Implementation/Build_Tracker.md`** — current implementation status. This is the ground truth for "is X actually built," but it does not set direction — it reports against the layers above it.
7. **`90_Historical/`** — lowest precedence. Never authoritative for a current decision; consulted only to understand why something changed.

**In practice:** if the Build Tracker says something is built a certain way, and an ADR says it should be built a different way, the ADR describes the target and the Build Tracker's status tag tells you whether that target has been reached yet — this is not usually a real conflict, just two documents answering different questions ("what should be true" vs. "what is currently true"). A genuine conflict — where a lower document asserts something the Constitution or an ADR actively forbids — should be escalated and the lower document corrected, not treated as a tie.

This policy itself supersedes the "where /docs conflict... [Project Plan] wins" clause previously stated in `CLAUDE.md` (now historical: see `90_Historical/Original_Project_Plan_Revised.md`'s header for that reclassification). `CLAUDE.md`'s own instructions (build order, states, LLM providers, hard rules) remain in force — they are largely restated and extracted into ADRs 001–010 here for citability, not replaced.

## Canonical documents (current source of truth)

- `00_Product/Product_Constitution.md`, `Product_Vision.md`, `Roadmap.md`
- `10_Architecture/` — all four files
- `20_Engineering/` — all four files, plus `Lessons_Learned.md`
- `30_Implementation/Build_Tracker.md`, `Backlog.md`, `Technical_Design/Litigation_Module_Architecture.md`, all of `ADR/`, all of `Acceptance_Testing/` (the Sprint 3.5.3 acceptance testing guide and its validation report template — gates the pleading-generation go/no-go decision)
- `40_Operations/Local_Development_Setup.md`, `Release_Gates.md`, `Infrastructure_Verification.md`, `Runtime_Health_Check.md`, `Recovery_Procedure.md`, `Deployment_Verification_Guide.md` (Monitoring/Runbooks remain honest stubs — see their own Status fields)
- `api/scripts/verify_*.py` and `verify_project.py` — the infrastructure verification framework (Sprint 3.5.5B). Real, re-runnable checks, not documentation, but canonical for "is the environment actually healthy" the same way a test suite is canonical for "does the code work." See `40_Operations/Infrastructure_Verification.md`.
- `40_Validation/` — all files from each dated validation round (each round is canonical for its own results; a newer round supersedes an older one for currency, not for history)
- `50_Reference/UI_UX_Guidelines.md`, `Stitch_Guidelines.md` (`Navigation.md` is a documented gap, not a canonical spec)

## Historical documents (preserved, not authoritative)

All under `90_Historical/`: `Original_Scope_of_Work.md`, `Original_Technical_Requirements.md`, `Original_Implementation_Plan.md`, `Original_Project_Plan_Revised.md`. Each carries a `Superseded By` and `Reason` in its header. Read these when you need to understand *why* a current decision exists, not to find out what's currently true.

## Exception: `golden_tests.json`

This file remains at `docs/golden_tests.json` (not moved into the hierarchy) because `api/tests/test_golden.py` reads it from a hardcoded path at runtime. It is a test fixture, not a documentation artifact. See [`20_Engineering/Repository_Standards.md`](20_Engineering/Repository_Standards.md) for detail.

## Known gaps in this documentation set (stated, not hidden)

- No Engineering Architecture Handbook existed before this refactor — the current one was synthesized from existing approved content. See its header for the provenance note.
- Two ADRs named in the original restructuring request ("AI Runtime DAG", "Prompt Registry") were not created — no approved decision in this repository substantiates either. See `30_Implementation/ADR/README.md`.
- `Stitch_Mockup_Plan.md` and `Navigation_and_Functional_Spec.md` are cited by the Build Tracker but do not exist in this repository. See `50_Reference/Navigation.md`.
- `40_Operations/Deployment.md`, `Monitoring.md`, and `Runbooks.md` are honest stubs, not complete operational documentation.
- ~~Migration files `0009_normalize_template_keys.sql` and `0009_litigation_pleadings_and_citations.sql` share a numeric prefix~~ — **corrected 6 August 2026 (Sprint 3.5.5B): this was wrong.** The second file was never actually created; the real litigation migrations are `0013_litigation_schema.sql`/`0014_litigation_case_analysis.sql`, uniquely numbered. Verified live via `api/scripts/verify_migrations.py`. See `20_Engineering/Database_Architecture.md`'s correction note and `40_Validation/Technical_Debt_Report_2026-08-06.md`. A different, real migration-hygiene finding replaces it: three migrations (`0011`, `0013`, `0014`) use bare `CREATE POLICY` without the `DROP POLICY IF EXISTS` guard the project's earlier migrations established, meaning a genuine re-run would error (TICKET-12, `30_Implementation/Backlog.md`).
- The first `40_Validation/` round (6 August 2026) is explicitly partial — it validated the deterministic Limitation/Forum layer only, because the execution environment had no live LLM/Supabase/Indian Kanoon credentials. See `40_Validation/Go_No_Go_Decision.md` for what remains unvalidated and why that means a Hold, not a Go, on AI Pleading Generation.

## Contribution guidelines

- **New product-level decisions** (values, what VidhiDesk will never become) go through the Product Constitution — amend deliberately, not via drift.
- **New architectural decisions** get a new ADR in `30_Implementation/ADR/`, numbered sequentially, following the existing template (Status / Context / Decision / Alternatives Considered / Consequences / Source). Do not silently change an existing ADR's Decision section — if a decision is reversed, write a new ADR that supersedes it and update the old one's Status.
- **Every active document must carry the standard metadata header** (Title, Version, Status, Owner, Audience, Last Updated, Canonical Reference, Supersedes, Related Documents) and a Related Documents section with relative links.
- **When a document is superseded**, move it to `90_Historical/`, set `Status: Historical`, and fill in `Superseded By` and `Reason` — do not delete it, and do not leave the change undocumented (see the discipline in `Build_Tracker.md` §0.1's evidence-tagging system, which exists precisely because status claims decay silently otherwise).
- **When updating `Build_Tracker.md`**, don't upgrade a status tag without a fresh evidence citation, per its own §0.1/§10 rules — that discipline is unchanged by this reorganization.
