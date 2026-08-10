> **Title:** ADR-006 — Human-in-the-Loop Review (Clause-by-Clause)
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers, legal
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../00_Product/Product_Constitution.md`](../../00_Product/Product_Constitution.md) §6, [`../../10_Architecture/Business_Architecture.md`](../../10_Architecture/Business_Architecture.md)

---

# ADR-006: Human-in-the-Loop Review (Clause-by-Clause)

## Status
Accepted. Whole-document human review was the original design intent; clause-by-clause review was adopted specifically once it was confirmed no gold-standard sample drafts would be supplied.

## Context
Every AI output in VidhiDesk requires advocate sign-off before reaching a client — this alone was always the design (`CLAUDE.md` Hard Rule 5, X-2). Separately, once it was confirmed that no prior client drafts would be supplied as a quality reference, there was no gold-standard corpus to imitate and no worked examples to steer generation quality.

## Decision
Templates are reviewed clause-by-clause, not document-by-document: the advocate marks each clause *keep / redraft / delete* with a required note on redraft/delete, rather than approving a whole document at once. A template not yet clause-reviewed ships labeled "beta — unreviewed skeleton" and is excluded from release gates. This produces the house style that missing sample drafts would otherwise have provided, and every edit the advocate makes to a generated draft becomes part of the corpus that improves future templates.

## Alternatives Considered
Whole-document approval (the simpler process) was the default assumption before the no-sample-drafts constraint was confirmed — rejected because approving or rejecting an entire multi-clause document gives no signal about which specific clauses are correct, and offers no incremental path to improving quality without a reference corpus.

## Consequences
- Review status (`kept`/`redrafted`/`unreviewed`) is tracked per clause in `clause_reviews`/`template_clauses`, not per template.
- Re-seeding a template must never silently destroy a human's redraft or reset a review status without an explicit content-change check — this failure mode was found live (see [`../../20_Engineering/Lessons_Learned.md`](../../20_Engineering/Lessons_Learned.md)) and fixed via `_write_clauses_preserving_review()`.
- The advocate's review time (~6 hrs/week during Phase 1) is treated as a hard project constraint, not a nice-to-have — the explicit fallback if that time isn't available is to cut the template library size, not to skip review.

## Source
`CLAUDE.md` Hard Rule 5, Cross-Cutting Requirement X-2; `90_Historical/Original_Project_Plan_Revised.md` §6 ("Working without sample drafts" — revised quality process); `20_Engineering/Lessons_Learned.md` (re-seed-preserves-review fix).
