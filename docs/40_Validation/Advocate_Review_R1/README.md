> **Title:** Review Milestone R1 — Advocate Validation — Facilitation Guide
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Nitesh (primary — this is your entry point), Keshav, future AI agents picking up Sprint 3.6 Phase 2A
> **Last Updated:** 9 August 2026
> **Canonical Reference:** Yes, for how this review round is conducted and what its output feeds into
> **Related Documents:** [`../Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md`](../Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md) (the engineering report this milestone follows), [`../../30_Implementation/Backlog.md`](../../30_Implementation/Backlog.md)

---

# Review Milestone R1 — Advocate Validation

## What this is, in one paragraph

Sprint 3.6 Phase 2 built and live-tested an AI Clause Generator and Document Composer — 14 independent clause types, assembled into 6 real draft pleadings from 6 real test matters. The engineering evaluation found the architecture works and measured what it could measure (reliability, latency, whether citations trace back to something real). It **cannot** measure whether the legal content is actually correct, complete, or fit to file — that requires a practicing advocate. This milestone exists to get that judgment from Nitesh, in a structured, recordable form, without requiring him to touch any code, database, or engineering tool.

**Nothing in this milestone changes the product.** No prompts were tuned, no code was fixed, no backlog items were closed. Every number in this folder is either a real measurement from the already-completed Phase 2 evaluation, or a blank field waiting for Nitesh's judgment. If this round finds real problems, they get *documented* here and picked up as engineering work in the next sprint (Sprint 3.6 Phase 2A) — not fixed mid-review.

---

## What's in this folder

| File | What it's for | Who fills it in |
|---|---|---|
| `README.md` | This file — start here | — |
| `Review_Package_APP-01.md` … `Review_Package_RERA-01.md` (6 files) | The actual content to review — matter facts, AI Case Analysis, Pleading Outline, all 14 generated clauses with confidence/citations/version info, the composed draft status, and matter-specific known limitations | Read-only — Keshav assembled these from real, already-generated system output; don't edit |
| `Clause_Review_Questionnaire.md` | The structured form — one 14-row table per matter plus an Overall Pleading Assessment | **Nitesh fills this in** |
| `Feedback_Capture_Template.md` | Where any finding worth more than a table cell gets recorded in detail, in a format that converts directly into engineering tickets | **Nitesh fills this in** |
| `Review_Dashboard.md` | Consolidated view across all 6 matters — system metrics are already filled in (real); legal-quality columns are blank pending this review | **Nitesh fills in the blank columns**, after finishing the questionnaire |
| `Engineering_Backlog_Mapping.md` | How Keshav will turn a completed Feedback Log into new `Backlog.md` tickets after this round ends | Reference only — not something Nitesh needs to fill in, but worth skimming to understand where the feedback goes |

## How to conduct the review

**Suggested order**, matter by matter (doing all 6 in one sitting is a lot — splitting into two sessions of 3 matters each is entirely reasonable):

1. Open `Review_Package_<ID>.md` for one matter. Read sections 1–6 first (Matter Summary through Pleading Outline) to build context — don't jump straight to the clauses without knowing the underlying facts.
2. Read section 7 clause by clause, in order. For each clause, fill in the matching row in `Clause_Review_Questionnaire.md` for that matter.
3. Where a clause shows **two versions** (a version actually in the composed draft, plus a newer unreviewed regeneration shown for comparison) — review the *first* one for "would you file this," since that's what's actually in the draft. The second is there so you can see whether regeneration tends to help or hurt, not because it needs its own separate judgment.
4. Read section 8 (Composed Draft) and section 9 (Known Limitations) before answering the Overall Pleading Assessment questions at the bottom of that matter's questionnaire block — the known limitations are there specifically so you're not rediscovering an already-known system defect and wondering if it's a legal problem.
5. For anything you'd flag beyond a single table cell — a wrong citation, a missing argument, a clause you'd never file — add a row to `Feedback_Capture_Template.md` before moving to the next clause, while the specific problem is still fresh.
6. After all 6 matters: fill in the Cross-Matter Reflection section at the end of `Clause_Review_Questionnaire.md`, then fill in `Review_Dashboard.md`'s blank columns and its final Overall Readiness section.

**Estimated time:** roughly 30–40 minutes per matter for the clause-by-clause review (reading + judging 14 clauses), plus 10–15 minutes for that matter's Overall Pleading Assessment — call it 45 minutes to an hour per matter, ~5 hours total across all 6. The Cross-Matter Reflection and Dashboard sign-off at the end add another 20–30 minutes. This does not need to happen in one sitting.

## System-wide limitations (apply to every matter — read once, here, not repeated 6 times)

These are real, already-diagnosed engineering findings from the Phase 2 evaluation. They explain *why* certain things look the way they do — they are not something for Nitesh to "find," but worth knowing before judging any individual clause:

- **Every AI-drafted clause in every one of these 6 matters was generated by a weaker model than the system's top tier.** `gemini-2.5-pro` (the architecture's intended first choice) served zero of the 30 AI-generated clauses in the original evaluation round — every one landed on a secondary or tertiary fallback model due to free-tier rate limits. If a clause reads as slightly generic or misses a nuance a stronger model might have caught, this is the most likely reason, not a fundamental flaw in the approach.
- **No verified case-law precedent was available to any clause in any of these 6 matters** — not because none exists, but because the upstream retrieval step (built in an earlier sprint) didn't surface one. Every "no precedents cited" you see is the system correctly declining to fabricate one, not a claim that none exists. If you know of a real, relevant precedent for any of these matters that never appears anywhere in the review package, that's a valuable, specific finding — record it.
- **Regenerating a clause is not guaranteed to reuse the same underlying AI model**, so two regenerations of "the same" clause can differ more than expected — not because the system is inconsistent by design, but because of the same rate-limit pressure above. Where you see two versions of a clause in a review package, this is why they can look meaningfully different.
- **One specific, known defect:** in at least one matter (CIV-01; check others for the same pattern), a clause's exhibit references show `PARTY_I1`-style tokens instead of real exhibit numbers (e.g. `P-1`) — an internal privacy-masking placeholder that failed to convert back to the real label. Treat any token starting with `PARTY_` as "exhibit number to be confirmed," not as case data. This is flagged inline wherever it appears.
- **Two of the six matters (COM-01, PROP-03) have an incomplete composed draft** — the Legal Grounds clause failed to generate valid output for both. This is the system's single least-reliable clause type; see each matter's review package §8–9 for what's missing.

## What NOT to worry about in this round

- Formatting/typography of the clause text (no page layout, numbering style, or court-filing formatting has been applied yet — this is content review, not a proofread of a filing-ready document).
- The specific wording of "AI-generated draft" disclaimers or notices — those are a fixed product requirement (CLAUDE.md Hard Rule 5), not something this review is meant to evaluate.
- Whether the system used your exact preferred phrasing/style — the review questions are about legal correctness and completeness, not stylistic preference (though "would you rewrite it" captures style concerns too, if worth recording).

---

## Recommendation for Sprint 3.6 Phase 2A

This is a **provisional** recommendation — the real one is whatever Nitesh's `Review_Dashboard.md` §4 Overall Readiness verdict says, once the review is done. Based only on what's known before that review starts:

**Sprint 3.6 Phase 2A should be scoped around three things, in this order:**

1. **Whatever Nitesh's review surfaces as Critical or high-frequency Major** — by definition, unknowable until the review happens, but it takes priority over everything below by design (see `Engineering_Backlog_Mapping.md` §1).
2. **TICKET-25 (Legal Grounds reliability)** — already the clause engine's most reliable engineering-side signal of a real weakness: worst success rate (67%), worst grounding rate, and the direct cause of 2 of 6 matters having an incomplete draft. Worth a focused diagnostic pass (prompt length? model-tier sensitivity? something else?) before any broader prompt-quality work.
3. **TICKET-24 (PII placeholder leak)** — low estimated engineering cost relative to its visibility; it's the kind of defect that undermines trust in every other clause's polish even though it isn't a legal-correctness problem.

**Do not scope Phase 2A to include full-pleading auto-generation, removing the Human Review gate, or building a filing-ready export** — none of that is supported by this round's evidence either way, and Phase 2's own recommendation (CLAUSE ENGINE REQUIRES FURTHER WORK) plus this round's job (get legal sign-off on *content*, not workflow) both argue for closing the content gaps first.

---

## Return

1. **Files created:** `README.md` (this file), 6× `Review_Package_<ID>.md`, `Clause_Review_Questionnaire.md`, `Feedback_Capture_Template.md`, `Review_Dashboard.md`, `Engineering_Backlog_Mapping.md` — all under `docs/40_Validation/Advocate_Review_R1/`. No application code, migrations, or prompts were touched.
2. **Review package summary:** 6 packages, each built entirely from real, already-generated Phase 2 output (matter facts, AI Case Analysis, Pleading Outline, all 14 clauses with version/confidence/citation detail, composed draft status, matter-specific known limitations) — no new AI generation was run to produce them.
3. **Questionnaire summary:** one 14-row per-clause table per matter (84 rows total) plus a 7-question Overall Pleading Assessment per matter and a 5-question Cross-Matter Reflection at the end — organized exactly per this milestone's Work Item 2 spec.
4. **Dashboard summary:** system-side metrics are real and pre-filled (84/84 clauses generated, 82/84 succeeded, 4/6 matters composed a complete draft, 0.89 average AI confidence on composed clauses, 3 concrete ungrounded-but-plausibly-correct citation instances found and explained); every legal-quality column is intentionally blank, pending this review.
5. **Feedback workflow:** Nitesh records findings in `Clause_Review_Questionnaire.md` (quick, per-clause) and `Feedback_Capture_Template.md` (detailed, anything worth more than a table cell) → Keshav triages via `Engineering_Backlog_Mapping.md`'s classification scheme and known-issues cross-reference → new tickets filed in `Backlog.md` starting at TICKET-28 → scoped into Sprint 3.6 Phase 2A.
6. **Recommendation for Sprint 3.6 Phase 2A:** provisional scope is (1) whatever this review surfaces as Critical/high-frequency-Major, (2) TICKET-25 Legal Grounds reliability, (3) TICKET-24 PII placeholder leak — see above for the reasoning. Final scope should be re-derived from the completed `Review_Dashboard.md`, not taken from this provisional list unchanged.
