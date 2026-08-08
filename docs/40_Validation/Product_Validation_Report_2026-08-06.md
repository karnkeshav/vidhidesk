> **Title:** Product Validation Report — Sprint 3.5.5 Round
> **Version:** 1.0
> **Status:** Active — Partial validation round, completed for the deterministic layer only
> **Owner:** Keshav (executed) / Nitesh (must complete Section B's AI Case Analysis columns and B.5 trust ratings)
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for this specific round's results — a later round producing a newer dated report supersedes this one for currency, not for history
> **Related Documents:** [`README.md`](README.md), [`../30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`](../30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md), [`../30_Implementation/Acceptance_Testing/Product_Validation_Report_Template.md`](../30_Implementation/Acceptance_Testing/Product_Validation_Report_Template.md)

---

# Product Validation Report — 6 August 2026

Filled in against the structure of `Product_Validation_Report_Template.md`. Where that template's Section B asks for per-scenario detail across Limitation, Forum, and AI Case Analysis, this report gives real per-scenario data for the first two and an explicit **NOT EXECUTED** for the third, across all 26 scenarios — rather than a fabricated fill-in. A condensed table is used instead of 26 copies of the full template block, since most of that block's fields are identically "not executed" this round; anything with a real finding gets its own note.

## A. Round metadata

| Field | Value |
|---|---|
| Validation round date | 6 August 2026 |
| Tester | Keshav (AI agent), executing directly against the codebase — **not** Nitesh, and **not** a substitute for Nitesh's own review |
| Scenarios planned | All 26 |
| Scenarios with deterministic-layer execution | 24 of 26 (CIV-05 and IA-01's limitation/forum are correctly not applicable per the guide's own design, not a gap in this round) |
| Scenarios with AI Case Analysis execution | 0 of 26 — no live LLM/Supabase credentials in this environment |
| Environment | Local backend code, direct Python function calls (`api/app/services/limitation.py::calculate_limitation`, `api/app/services/forum.py::determine_forum`, `api/app/services/case_analysis.py::_chronological_facts` / `_deterministic_evidence_gaps` / `_deterministic_missing_information`) — **not** the running FastAPI app, **not** a browser session, **not** production |
| Backend commit / deploy reference | Working tree as of this session, immediately after the TICKET-5/TICKET-6 fixes and their regression tests (214/214 backend tests passing) |
| Known pre-existing issues going into this round | TICKET-7 (UP/Bihar forum state-coverage gap), TICKET-8 (AI Case Analysis blind to hearing/IA data) — both explicitly out of scope to modify this sprint |

## B. Per-scenario results

### B.1–B.2: Limitation and Forum (real, executed)

Every row below is a real function call against the live code, not a transcription of the guide's text. "Match" means the actual output equals the guide's stated expected value; where it doesn't, the reason is given rather than silently noted.

| ID | Limitation input | Actual expiry | Actual barred | Actual days remaining | Article | Lim. match? | Forum input | Actual recommended forum | Unambiguous | Forum match? |
|---|---|---|---|---|---|---|---|---|---|---|
| CIV-01 | 2024-03-10, Money Recovery | 2027-03-10 | False | 216 | Art 19 | ✅ | Civil Suit, ₹8,50,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| CIV-02 | 2023-08-20, Declaratory | 2026-08-20 | False | 14 | Art 58 | ✅ | Civil Suit, ₹30,00,000, Delhi | District Court/Addl. District Judge, Delhi | True | ✅ |
| CIV-03 | 2025-01-15, "Injunction" (no match → residuary) | 2028-01-15 | False | 527 | Art 58/113 | ✅ (residuary fallback confirmed, as documented) | Civil Suit, ₹2,00,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| CIV-04 | 2020-01-05, Money Recovery | 2023-01-05 | **True** | -1309 | Art 19 | ✅ (barred by exactly 1,309 days, as documented) | Civil Suit, ₹3,20,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| CIV-05 | *(not run — by design)* | N/A | N/A | N/A | N/A | N/A | *(not run — by design)* | N/A | N/A | N/A |
| COM-01 | 2025-07-01, Breach of Contract | 2028-07-01 | False | 695 | Art 55 | ✅ | Commercial Dispute, ₹3,00,000, Delhi | **Designated Commercial Court, Delhi** | True | ✅ (TICKET-6 fix confirmed) |
| COM-02 | 2025-11-01, Breach of Contract | 2028-11-01 | False | 818 | Art 55 | ✅ | Commercial Dispute, ₹45,00,000, Maharashtra | **Designated Commercial Court, Maharashtra** | True | ✅ (TICKET-6 fix confirmed, 2nd state) |
| COM-03 | 2026-01-15, Breach of Contract | 2029-01-15 | False | 893 | Art 55 | ✅ | Commercial Dispute, ₹18,00,000, Delhi, defendant residence Karnataka | **Designated Commercial Court, Delhi**, 3 options, unambiguous=False | False | ✅ (TICKET-6 fix + ambiguity logic both confirmed together) |
| COM-04 | 2024-08-01, Breach of Contract | 2027-08-01 | False | 360 | Art 55 | ✅ | Commercial Dispute, ₹1,20,00,000, Delhi | **Designated Commercial Court, Delhi** | True | ⚠️ **Guide text is stale** — see note below |
| PROP-01 | 2014-04-01, Possession | 2026-04-01 | **True** | -127 | Art 65 | ✅ (barred by exactly 127 days) | Property Dispute, ₹35,00,000, UP | "District Court" (generic DEFAULT band) | True | ✅ (TICKET-7 gap re-confirmed, as documented — open, not a new finding) |
| PROP-02 | 2019-04-12, Possession (Art 65 default AND Art 64 override both run) | 2031-04-12 (both) | False (both) | 1710 (both) | Art 65 / Art 64 | ✅ | Property Dispute, ₹8,00,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| PROP-03 | 2025-09-30, Specific Performance | 2028-09-30 | False | 786 | Art 54 | ✅ | Property Dispute, ₹95,00,000, Maharashtra | Civil Judge Senior Division, Maharashtra | True | ✅ |
| PROP-04 | 2026-05-01, "Easement" (no match → Declaratory used per guide) | 2029-05-01 | False | 999 | Art 58 | ✅ | Property Dispute, ₹5,00,000, Bihar | "Civil Judge Junior Division" (generic DEFAULT band) | True | ✅ (TICKET-7 gap re-confirmed) |
| RERA-01 | 2024-06-30, Breach of Contract (proxy) | 2027-06-30 | False | 328 | Art 55 | ✅ | RERA, ₹75,00,000, Delhi | **RERA Tribunal, Delhi** | True | ✅ (positive control confirmed) |
| RERA-02 | 2025-08-01, Breach of Contract (proxy) | 2028-08-01 | False | 726 | Art 55 | ✅ | RERA, ₹4,50,000, UP | **RERA Tribunal, Uttar Pradesh** (state-name correct despite general-civil UP gap) | True | ✅ |
| RERA-03 | 2024-03-31, Breach of Contract (proxy) | 2027-03-31 | False | 237 | Art 55 | ✅ | RERA, ₹22,00,000, Maharashtra | RERA Tribunal, Maharashtra | True | ✅ |
| CONT-01 (correct date) | 2024-11-20, Breach of Contract | 2027-11-20 | False | 471 | Art 55 | ✅ | Civil Suit, ₹25,00,000, Delhi | District Court/Addl. District Judge, Delhi | True | ✅ |
| CONT-01 (wrong/discovery date) | 2026-01-25, Breach of Contract | 2029-01-25 | False | 903 | Art 55 | ✅ (confirms the input-validation gap: both dates produce equally confident, differently-wrong-if-misdated output) | *(same forum run as above)* | — | — | — |
| CONT-02 | 2026-01-10, Breach of Contract | 2029-01-10 | False | 888 | Art 55 | ✅ | Civil Suit, ₹15,00,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| CONT-03 | 2025-05-01, Breach of Contract | 2028-05-01 | False | 634 | Art 55 | ✅ | Civil Suit, ₹6,00,000, Maharashtra | Civil Judge Senior Division, Maharashtra | True | ✅ (boundary confirmed: 6L > 5L threshold) |
| CONT-04 | 2025-08-01, Breach of Contract | 2028-08-01 | False | 726 | Art 55 | ✅ | Civil Suit, ₹4,00,000, Karnataka | Civil Judge Junior Division, Karnataka | True | ✅ |
| APP-01 | 2026-06-20, Appeal (Art 116 default) | **2026-09-18** | False | **43** | Art 116 | ✅ (TICKET-5 fix confirmed — was 2026-09-17/42 pre-fix) | Civil Suit, ₹8,00,000, Delhi | Civil Judge Court, Delhi | True | ✅ |
| APP-02 | 2026-07-20, Appeal (Art 115 override) | **2026-08-19** | False | **13** | Art 115 | ✅ (TICKET-5 fix confirmed on the 2nd article — was 2026-08-18/12 pre-fix) | *(no concrete value given — not run)* | N/A | N/A | N/A |
| APP-03 | 2025-11-01, Appeal (Art 116 default) | 2026-01-30 | **True** | -188 | Art 116 | ✅ (barred by exactly 188 days, TICKET-5-corrected figure) | Commercial Dispute, ₹35,00,000, Maharashtra | **Designated Commercial Court, Maharashtra** | True | ✅ (TICKET-6 fix confirmed, 3rd state, combined with Appeal category) |
| IA-01 | *(not independently specified by guide)* | N/A | N/A | N/A | N/A | N/A | *(not independently specified)* | N/A | N/A | N/A |
| IA-02 | 2026-05-10, Appeal | **2026-08-08** | False | **2** | Art 116 | ✅ (extremely urgent — 2 days remaining as of this test run; matches the guide's own framing that this scenario's hearing, dated 2026-08-09, is imminent) | Property Dispute, ₹28,00,000, Bihar | "District Court" (generic DEFAULT band) | True | ✅ (TICKET-7 gap re-confirmed a 3rd time) |
| IA-03 | *(not independently specified)* | N/A | N/A | N/A | N/A | N/A | Commercial Dispute, ₹52,00,000, Karnataka | **Designated Commercial Court, Karnataka** | True | ✅ (TICKET-6 fix confirmed, 4th state) |

**Note on COM-04:** the acceptance guide's written "Expected Forum Result" for COM-04 still says "District Court/Additional District Judge, Delhi" — text written before the TICKET-6 fix, for a scenario that was never in the fix's originally-flagged list (COM-01/02/03, IA-03) because COM-04 was tagged for AI-synthesis testing, not forum-ordering. It was overlooked when the guide was updated post-fix. The **system's actual behavior is correct** (COM-04 is a Commercial Dispute above the ₹3,00,000 threshold, so it now correctly gets the Commercial Court recommendation, consistent with every other qualifying scenario) — the mismatch is between the system and a stale line in the guide, not a product defect. Logged in [`Defect_Log.md`](Defect_Log.md) as a documentation-accuracy item; not corrected in this round per the "do not fix defects during validation" rule.

### B.3–B.6: AI Case Analysis, acceptance-criteria scoring, trust ratings, free-text notes

**NOT EXECUTED for any of the 26 scenarios.** No matter was created in a live database, no LLM call was made, no evidence file was uploaded, no citation was verified against Indian Kanoon, and no advocate reviewed any output — because none of the infrastructure required for any of that exists in this environment. Every acceptance-criteria checkbox in the guide that concerns Matter Summary, Chronological Facts *narrative*, Missing Information (LLM-elaborated portion), Applicable Statutes (retrieval), Possible Causes of Action, Jurisdiction/Limitation Summary pass-through *as rendered in the AI output*, Potential Risks, Evidence Gaps (LLM-elaborated portion), Recommended Next Steps, and Possible Precedents is **unscored**, not failed.

Two narrow exceptions — the deterministic sub-components of the AI Case Analysis pipeline that don't need an LLM or database at all — were executed directly:

- **Chronological fact sorting** (`_chronological_facts`): tested against PROP-02's exact out-of-order entry instruction from the guide (facts entered 2019-05-01, 2019-04-14, 2019-04-12 — deliberately reverse order). **Result: correctly re-sorted to 2019-04-12, 2019-04-14, 2019-05-01.** Confirms the deterministic sort is entry-order-independent, as designed.
- **Deterministic evidence-gap and missing-information seed lists** (`_deterministic_evidence_gaps`, `_deterministic_missing_information`): tested against CIV-01-style fully-evidenced facts (correctly produced zero gaps) and PROP-04-style under-evidenced facts (correctly flagged the undocumented historical-use fact). Tested against a CIV-04-style matter with no limitation/forum/hearings supplied (correctly produced all four expected seed items: no case number, no hearings logged, limitation not calculated, forum not determined).

These two checks give real, if narrow, confidence that the parts of the AI Case Analysis pipeline that don't depend on the LLM are working as designed. They say nothing about the LLM-synthesized majority of each analysis.

## C. Defect log

See [`Defect_Log.md`](Defect_Log.md) for the full classified list. Summary: zero new product defects found; TICKET-7 and TICKET-8 re-confirmed (where testable) as still open, unchanged per this sprint's instructions; one test-documentation staleness item (COM-04) found and logged, not fixed.

## D. Round rollup

See [`Metrics_Dashboard.md`](Metrics_Dashboard.md) for full metrics and [`Go_No_Go_Decision.md`](Go_No_Go_Decision.md) for the gate decision. Headline: **100% match rate on every deterministic Limitation and Forum check that could be executed (46 of 46 real function calls); 0% of the AI-dependent evaluation dimensions executed.** Overall recommendation: **Hold** — see the Go/No-Go document for the full reasoning.
