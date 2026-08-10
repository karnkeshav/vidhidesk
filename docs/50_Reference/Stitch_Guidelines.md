> **Title:** Google Stitch Guidelines
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Designers, frontend engineers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for the UI design governance process
> **Supersedes:** N/A — extracted from `30_Implementation/Build_Tracker.md` §0.2, which remains the source
> **Related Documents:** [`UI_UX_Guidelines.md`](UI_UX_Guidelines.md), [`../40_Operations/Release_Gates.md`](../40_Operations/Release_Gates.md)

---

# Google Stitch Guidelines

Google Stitch is the single authoritative source for all UI/UX design across VidhiDesk. Implementation must never become the source of UI design. Full governance detail lives in `30_Implementation/Build_Tracker.md` §0.2; this document summarizes the process for quick reference.

## The 6-step lifecycle (mandatory before any screen's code is written)

1. **Architecture Design** — business workflow, user journey, information architecture, required components. No UI implementation yet.
2. **Google Stitch Verification** — audit whether an appropriate Stitch design already exists (project ID, screen ID, availability, confidence %, screenshot evidence, gap analysis). A screen cannot be marked "Verified Existing/Partial" without reviewed screenshot evidence.
3. **Visual Design Review** — open the actual Stitch screen; inspect full-size screenshot, UX, missing/incorrect elements, design inconsistencies, mobile considerations, accessibility, workflow coverage. Ends in one of: Approved without changes / Minor refinement required / Major redesign required.
4. **Design Generation & Refinement** — if Partial or needing refinement, produce an updated Stitch prompt, regenerate, re-review.
5. **Design Approval** — explicit user (Nitesh) sign-off on the generated/verified design. Approved designs become the UI source of truth.
6. **Implementation** — only after approval: build React/Next.js components, wire APIs, integrate business logic and AI services.

## Tracker lifecycle states

`Verified Existing (Screenshot attached)` → `Verified Partial (Screenshot attached)` → `Visual Design Review Completed` → `Newly Generated in Stitch` → `Pending Schema Alignment` → `Approved for Implementation` → `Implemented`.

**No screen may move directly from "Designed" to "Implemented."**

## Litigation-specific gate

Implementation of Litigation features is strictly gated: no Litigation implementation may begin until all Litigation Stitch designs complete this full lifecycle and obtain user sign-off. Per `30_Implementation/Build_Tracker.md` §0.3, this gate has not yet been cleared.
