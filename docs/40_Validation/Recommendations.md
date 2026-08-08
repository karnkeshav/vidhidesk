> **Title:** Recommendations — Sprint 3.5.5
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for next steps arising from this round
> **Related Documents:** [`README.md`](README.md), [`Defect_Log.md`](Defect_Log.md), [`Go_No_Go_Decision.md`](Go_No_Go_Decision.md)

---

# Recommendations — 6 August 2026

## 1. Complete the AI-dependent validation before deciding on pleading generation (highest priority)

This round validated the deterministic third of the pipeline for real. The other two-thirds — everything the LLM synthesizes, everything the Citation Verifier confirms, the actual advocate-facing quality of the analysis — is exactly what pleading generation would be built on top of, and it remains completely unvalidated. Two ways to close this, not mutually exclusive:

- **(a) Provision this environment (or a fresh session) with real credentials** — at minimum a Gemini API key (free tier, per `ADR-003`/`ADR-009`) and Supabase project credentials — and re-run the same 26 scenarios end-to-end, this time for real. Given the free-tier architecture, this should be low-to-zero cost. An AI agent could then execute the full guide and produce genuine Section B.3–B.6 data for every scenario.
- **(b) Have Nitesh run the guide manually** against the live deployed app (`vidhidesk.onrender.com` / Vercel frontend), using `Product_Validation_Report_Template.md` per scenario. This is slower but has a distinct advantage (a) doesn't: it produces the one thing this round categorically cannot — an actual advocate's trust rating and professional judgment on whether the output is usable (Section B.5 of the template), which is the whole point of a *product* validation, not just a code-correctness check.

Either path should re-run the same known-defect scenarios (COM-01/02/03, IA-03, APP-01/02/03) as regression confirmation in a real environment, not just this session's direct function calls — closing the gap between "the function is correct in isolation" and "the deployed system behaves correctly," which is a distinction this project's own `Lessons_Learned.md` has already flagged as a real, previously-costly gap in Sprint 2.

## 2. Correct the COM-04 documentation drift (D-1) before the next round

Low effort, prevents a false "failure" signal in every future run of this scenario. A one-line edit to the guide's COM-04 "Expected Forum Result" text.

## 3. Do not treat this round's 100% deterministic-layer pass rate as a general "the system works" signal

It's real and it's good news, but it covers roughly a third of what each scenario's acceptance criteria actually ask for. Reporting "100% pass" without the qualification in `Metrics_Dashboard.md` to anyone outside this document would misrepresent the state of validation. If this report is summarized upward (to Nitesh, to any future stakeholder), carry the qualification with it.

## 4. Consider whether TICKET-7 should be prioritized ahead of pleading generation

Uttar Pradesh is one of exactly three officially in-scope Phase 1 states (`CLAUDE.md` Decision 2), and the Forum Advisor currently has no real data for it — a matter in UP silently gets the same generic fallback as a state the product was never meant to support at all (Bihar). If pleading generation for Litigation is meant to cover UP matters at launch, this gap should be closed before, not after, drafting depends on a jurisdictionally-generic forum recommendation. This is a scoping question for Nitesh/Keshav to decide together, not something this round can resolve on its own.

## 5. TICKET-8 (hearing-blindness) matters more once pleading generation exists

Right now it degrades the AI Case Analysis's usefulness for interim-application-heavy matters. Once pleading generation is built on top of the analysis (per `ADR-011`), a pleading drafted without any awareness of an imminent, pending interim application is a materially worse gap than an analysis that's merely incomplete — worth re-weighing its priority at that point, even though it's correctly out of scope for this sprint.

## 6. Standardize the defect-severity scheme across acceptance-testing artifacts

`Product_Validation_Report_Template.md` uses Critical/High/Medium/Low; this round was instructed to use Critical/Major/Minor/Enhancement. Pick one before the next round runs, so defect counts are comparable across rounds without a translation step.
