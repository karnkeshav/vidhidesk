> **Title:** Metrics Dashboard — Sprint 3.5.5
> **Version:** 1.0
> **Status:** Active — every figure below is either directly measured or explicitly marked unmeasured; none are estimated placeholders
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for this round's quantitative results
> **Related Documents:** [`README.md`](README.md), [`Product_Validation_Report_2026-08-06.md`](Product_Validation_Report_2026-08-06.md)

---

# Metrics Dashboard — 6 August 2026

## Legend

- 🟢 **Measured** — a real number from actually executing code this round.
- ⚪ **Not measured** — cannot be honestly produced without live LLM/Supabase/Indian Kanoon access, which this environment does not have. No estimate is given in place of a real number; where a qualitative expectation exists (e.g. "cost should be near-zero under the free-tier architecture"), it is labeled as expectation, not measurement.

## Limitation accuracy 🟢

**23 / 23 = 100%** of executed Limitation calculations matched the acceptance guide's stated expected value exactly (expiry date, `is_barred`, days remaining, and article all checked). Two additional variant runs (CONT-01's "wrong discovery date" input, PROP-02's Article 64 override) also matched their documented expectations, for 25 total limitation calls, all correct.

This includes direct, live re-confirmation of the TICKET-5 fix on both affected articles (APP-01: Article 116 → 2026-09-18/43 days, not the pre-fix 2026-09-17/42; APP-02: Article 115 → 2026-08-19/13 days, not the pre-fix 2026-08-18/12) and on a third instance combined with a barred/condonation result (APP-03).

Two scenarios (CIV-05, IA-01) correctly had no limitation calculation run, per the guide's own design — not counted as failures or as untested gaps.

## Forum accuracy 🟢

**22 / 23 = 95.7%** against the guide's currently-written text; **23 / 23 = 100%** against the guide's *intended, correct* behavior (see the COM-04 note below — the one mismatch is the guide's own text being stale post-TICKET-6-fix, not the system producing a wrong answer).

This includes direct, live re-confirmation of the TICKET-6 fix across four states (Delhi: COM-01, COM-03; Maharashtra: COM-02, APP-03; Karnataka: IA-03) and one scenario (COM-04) where the fix's *correct* effect wasn't yet reflected in the guide text. The RERA positive-control ordering (RERA-01/02/03) and the cross-state ambiguity logic (COM-03) both continue to behave correctly, as previously documented. TICKET-7 (UP/Bihar state-coverage gap) reproduced consistently in every applicable scenario (PROP-01, PROP-04, RERA-02, IA-02) — expected, unchanged, not counted as a new "failure" since it's a documented, open, out-of-scope-this-sprint limitation, not a regression.

## AI issue-identification accuracy ⚪ Not measured

Requires the LLM-synthesized `possible_causes_of_action` output. No LLM call was made this round.

## Evidence-gap detection rate 🟢 (partial) / ⚪ (partial)

🟢 **Deterministic seed layer: 3 / 3 test cases behaved correctly** — a fully-evidenced fact set produced zero flagged gaps; an under-evidenced fact set correctly flagged the one fact missing both an exhibit number and a file; a matter with no limitation/forum/hearings data supplied correctly produced all four expected missing-information seed items.

⚪ **LLM-elaborated layer: not measured.** The guide's evidence-gap expectations for most scenarios (e.g. PROP-03's missing encumbrance certificate, CONT-01's missing forensic corroboration) depend on the LLM reading the facts and reasoning about what's absent — untestable without a live call.

## Citation correctness ⚪ Not measured

Requires both an LLM proposing a case name and a live call to the Indian Kanoon API to verify it. Neither is possible without `INDIAN_KANOON_API_TOKEN` and an LLM provider key, neither of which exists in this environment. The two scenarios designed specifically to test this (PROP-03, CONT-02) were not run.

## Hallucination count ⚪ Not measured (with one narrow, real exception)

No LLM output was generated this round, so nothing could be inspected for fabricated facts, dates, statutes, or case names — the count is genuinely unknown, not zero.

The one thing that *can* be said with certainty: the deterministic-only code paths exercised this round (Limitation Engine, Forum Advisor, chronological sort, rule-based gap detection) are, by construction, incapable of hallucination — they perform no generation at all, only arithmetic and rule evaluation over the exact inputs given. This is a narrow, structural guarantee about a specific slice of the pipeline, not a measurement of the system's hallucination rate as a whole.

## Runtime 🟢 (deterministic layer only) / ⚪ (LLM layer)

🟢 Directly measured via `time.perf_counter()` around each real function call:

| Function | Calls | Min | Max | Avg |
|---|---|---|---|---|
| `calculate_limitation()` | 25 | 0.019 ms | 4.629 ms | 0.217 ms |
| `determine_forum()` | 23 | 0.004 ms | 0.030 ms | 0.009 ms |

These numbers are essentially instantaneous, as expected for in-memory Python with no I/O — and are **not representative of real end-to-end request latency**, which in production would add HTTP round-trip, auth, and (for the deterministic engines specifically) essentially nothing else, since neither touches the database. They say nothing about AI Case Analysis latency, which is dominated by LLM generation time and was not measured this round.

⚪ AI Case Analysis end-to-end runtime: not measured — no live calls made.

## Token usage ⚪ Not measured

Cannot be produced without a real LLM call — token counts depend on the actual prompt sent (including whatever the RAG retriever returns, which itself requires a live Supabase query) and the actual response length, neither of which exists this round. No estimate is substituted.

## Estimated AI cost ⚪ Not measured

Same reasoning as token usage — an honest cost figure requires a real token count from a real call. The one thing worth stating as *expectation, not measurement*: per `ADR-009` (Freeware / Zero-Recurring-Cost Constraint), the architecture's primary provider is Gemini 2.5 Flash's free tier, with Groq/SambaNova/Cerebras free tiers as failover — a full 26-scenario validation round, run for real, would be expected to cost **$0** provided usage stays within free-tier quotas. This is a design expectation carried over from the architecture, not a number derived from this round's execution.

## Summary table

| Metric | Status | Result |
|---|---|---|
| Limitation accuracy | 🟢 Measured | 100% (23/23, +2 verified variants) |
| Forum accuracy | 🟢 Measured | 100% vs. correct behavior; 95.7% vs. stale guide text (1 doc issue, not a product defect) |
| AI issue-identification accuracy | ⚪ Not measured | — |
| Evidence-gap detection rate | 🟢 Partial / ⚪ Partial | Deterministic seed layer: 3/3 correct. LLM-elaborated layer: not measured |
| Citation correctness | ⚪ Not measured | — |
| Hallucination count | ⚪ Not measured | Deterministic-only paths: 0 by construction (narrow guarantee, not a system-wide measurement) |
| Runtime | 🟢 Partial / ⚪ Partial | Deterministic layer: sub-millisecond (measured). LLM layer: not measured |
| Token usage | ⚪ Not measured | — |
| Estimated AI cost | ⚪ Not measured | Design expectation: $0 under free-tier architecture (not a measured figure) |
