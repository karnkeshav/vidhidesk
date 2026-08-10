> **Title:** ADR-010 — Phase 1 State Coverage Scope
> **Version:** 1.0
> **Status:** Accepted (narrowed from an earlier decision)
> **Owner:** Keshav / Nitesh
> **Audience:** Product, engineering, legal
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../10_Architecture/Business_Architecture.md`](../../10_Architecture/Business_Architecture.md)

---

# ADR-010: Phase 1 State Coverage Scope

## Status
Accepted. Narrowed from the original Scope of Work's five-state target to three states.

## Context
Indian state-level law (stamp duty, registration requirements, RERA rules) varies materially by state, and each state added to Phase 1 scope requires curated, source-linked data (stamp/registration notes, RERA filing walkthroughs) that must be kept current as state rules drift. The original Scope of Work targeted five states (Delhi, Maharashtra, UP, Bihar, Haryana); the revised Project Plan narrowed this to three (Delhi, Maharashtra, UP) explicitly reasoning "three states done well rather than twenty-eight done badly."

## Decision
Phase 1 supports Delhi, Maharashtra, and Uttar Pradesh only. Any other state falls back to Central law plus a "verify state rules" flag on the relevant draft or note, rather than attempting partial or unverified state-specific coverage.

## Alternatives Considered
The original five-state target (adding Bihar and Haryana) was the starting scope — narrowed because state-rules data quality depends on the advocate's own curation bandwidth (explicitly finite, ~6 hrs/week during Phase 1 alongside clause review), and partial or unverified coverage for additional states was judged worse than an honest fallback flag.

## Consequences
- Any new state-specific feature (jurisdiction selector option, RERA filing walkthrough) defaults to unsupported-with-flag rather than best-effort guessing, consistent with the Product Constitution's Legal Safety Principles ("silence is safer than confident error").
- Expanding state coverage beyond these three is a scoped, deliberate decision requiring new curated `state_rules`/`rera_guides` data with source URLs and a `last_verified` date — not a default assumption for future work.

## Source
`90_Historical/Original_Scope_of_Work.md` §2.3 ("Phase 1 state coverage: Delhi, Maharashtra, UP, Bihar, Haryana"); `90_Historical/Original_Project_Plan_Revised.md` §5, §7 ("Three states done well rather than twenty-eight done badly"); `CLAUDE.md` Decision 2 (final narrowed scope: Delhi, Maharashtra, UP only).
