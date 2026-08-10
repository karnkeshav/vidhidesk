> **Title:** Sprint 3.5.3 Acceptance Testing Guide — AI Case Analysis Vertical Slice
> **Version:** 1.0
> **Status:** Active — Canonical, gates the go/no-go decision for pleading generation
> **Owner:** Keshav (authored) / Nitesh (executes, signs off)
> **Audience:** Nitesh (advocate — primary tester), QA, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for how the Sprint 3.5.3 vertical slice is validated before any pleading-generation work begins
> **Supersedes:** N/A
> **Related Documents:** [`../Build_Tracker.md`](../Build_Tracker.md), [`../ADR/ADR-011-ai-case-analysis-before-pleading.md`](../ADR/ADR-011-ai-case-analysis-before-pleading.md), [`../Technical_Design/Litigation_Module_Architecture.md`](../Technical_Design/Litigation_Module_Architecture.md), [`Product_Validation_Report_Template.md`](Product_Validation_Report_Template.md), [`../../40_Operations/Release_Gates.md`](../../40_Operations/Release_Gates.md)

---

# Sprint 3.5.3 Acceptance Testing Guide

## 0. Purpose and scope

Sprint 3.5.3 shipped the first complete Litigation workflow: create matter → add parties → record facts → upload evidence → run the Limitation Calculator → run the Forum Advisor → generate an AI Case Analysis → review it in a structured workspace. Per [ADR-011](../ADR/ADR-011-ai-case-analysis-before-pleading.md), this is deliberately **not** pleading generation — it is the checkpoint the advocate reviews *before* deciding whether, and how, to draft anything.

This guide exists to answer one question with evidence, not opinion: **is this checkpoint trustworthy enough to build pleading generation on top of?** It does that by giving Nitesh 26 realistic fact patterns to run through the live system, each with an objectively stated expected result, so that "the AI got this wrong" and "the AI got this right" are both falsifiable claims, not impressions.

**This guide was authored by re-reading the actual implementation** (`api/app/services/limitation.py`, `forum.py`, `case_analysis.py`), not by guessing at expected behavior. Several scenarios below were deliberately designed around specific gaps found by hand-tracing the code during authoring — these are called out explicitly in §4 and in the scenario text itself, so a tester doesn't waste time thinking they made a data-entry mistake when the system produces the flagged result. Finding these before pleading generation is built on top of them is the entire point of this exercise.

**Every exact date and day-count claim below was additionally verified by running the real `calculate_limitation()` and `determine_forum()` functions directly against every scenario's stated inputs**, not left as hand arithmetic. Where a scenario's "Expected" result depends on the AI-synthesized layer rather than the deterministic engines, it could not be verified this way — those expectations are informed judgment, not a run result, and are written accordingly.

> **Update, 6 August 2026 — TICKET-5 and TICKET-6 fixed before the first validation round.** While authoring this guide, running `calculate_limitation()` and `determine_forum()` against the scenarios below surfaced two real defects: an off-by-one-day error in Article 115/116 computation (originally exposed by APP-01/APP-02/APP-03) and a forum-recommendation-ordering error for Commercial Disputes meeting the Commercial Courts Act threshold (originally exposed by COM-01/COM-02/COM-03/IA-03). Both were fixed in `api/app/services/limitation.py` and `api/app/services/forum.py` respectively, confirmed by re-running the same scenarios against the corrected code, and locked in with new regression tests (`test_limitation_appeal_article_116_ninety_days_exact`, `test_limitation_appeal_article_115_thirty_days_exact`, `test_forum_commercial_courts_act_recommends_commercial_court_not_general_civil`). The scenario text below has been updated to state the **now-correct** expected values — a tester following this guide today should see the fixed behavior, not the original bug. Each affected scenario retains a note on what the original defect was and how it was fixed, since that history is exactly the kind of finding this exercise exists to produce, and the fact that it was caught and closed before a single human validation round ran is itself worth recording. See `docs/30_Implementation/Backlog.md` (TICKET-5, TICKET-6) for the fix record.

**What this guide does not cover:** UI polish, performance, mobile layout, or anything about pleading drafting (it doesn't exist yet). It covers correctness and trustworthiness of the analysis pipeline only.

## 1. How to use this guide

For each scenario:

1. Create a new litigation matter in the app (title it `[TEST] <Scenario ID> — <short label>` per the project's existing test-data convention — see `20_Engineering/Lessons_Learned.md`).
2. Enter the parties exactly as listed.
3. Enter the facts. Unless a scenario explicitly says to enter them out of order (a few do, deliberately — see §4.2), enter them in the order given.
4. Upload evidence as described (a real file is fine — content doesn't matter, only that exhibit metadata and, where noted, an actual file attachment are present, since evidence-gap detection checks specifically for `file_url`, not just an exhibit label).
5. Run the Limitation Calculator with the inputs given. Compare the output to **Expected Limitation Result**.
6. Run the Forum Advisor with the inputs given. Compare the output to **Expected Forum Result**.
7. Generate the AI Case Analysis (pass the limitation and forum results through, as the UI does automatically). Compare against **Expected Legal Issues**, **Expected Evidence Gaps**, and **Expected AI Case Analysis Outcomes**.
8. Score every item in **Acceptance Criteria** as Pass / Fail / Partial.
9. Record the run in the [Product Validation Report](Product_Validation_Report_Template.md) — one report per scenario, plus one rollup report across all 26.

**On the scenarios flagged as known-likely-to-fail:** a Fail on a flagged criterion is not a testing error — it's the guide doing its job. A Pass on a flagged criterion (the system behaved better than the code trace predicted) is equally worth recording; it may mean the codebase changed since this guide was written, or that the hand-trace was wrong somewhere, either of which is useful to know.

## 2. Coverage matrix

| ID | Category | Suit Category (Limitation) | Suit Type (Forum) | State | Primary Stress Target(s) |
|---|---|---|---|---|---|
| CIV-01 | Civil Suit | Money Recovery | Civil Suit | Delhi | Limitation (article ambiguity), baseline canary |
| CIV-02 | Civil Suit | Declaratory | Civil Suit | Delhi | Limitation (near-expiry urgency) |
| CIV-03 | Civil Suit | *(no clean fit — residuary)* | Civil Suit | Delhi | Limitation (category-fit gap) |
| CIV-04 | Civil Suit | Money Recovery | Civil Suit | Delhi | Limitation (stale condonation nuance) |
| CIV-05 | Civil Suit | Money Recovery | Civil Suit | Delhi | Fact extraction, AI synthesis (sparse input) |
| COM-01 | Commercial Dispute | Breach of Contract | Commercial Dispute | Delhi | Forum (recommendation-ordering — TICKET-6, fixed 6 Aug 2026, now a regression check) |
| COM-02 | Commercial Dispute | Breach of Contract | Commercial Dispute | Maharashtra | Forum (pecuniary band; TICKET-6 regression check), baseline canary |
| COM-03 | Commercial Dispute | Breach of Contract | Commercial Dispute | Delhi / Karnataka | Forum (cross-state ambiguity — positive control; also a TICKET-6 regression check) |
| COM-04 | Commercial Dispute | Breach of Contract | Commercial Dispute | Delhi | AI synthesis (multi-cause-of-action) |
| PROP-01 | Property Matter | Possession | Property Dispute | Uttar Pradesh | Forum (state-coverage gap — open, TICKET-7) |
| PROP-02 | Property Matter | Possession | Property Dispute | Delhi | Limitation (article selection), Chronology |
| PROP-03 | Property Matter | Specific Performance | Property Dispute | Maharashtra | Citation/statute grounding |
| PROP-04 | Property Matter | *(no clean fit — residuary)* | Property Dispute | Bihar | Limitation + Forum (compound gap — Forum half open, TICKET-7) |
| RERA-01 | RERA Matter | Breach of Contract *(proxy)* | RERA | Delhi | Forum (positive control — contrast with the now-fixed COM-01) |
| RERA-02 | RERA Matter | *(no clean fit)* | RERA | Uttar Pradesh | Limitation (no DLP category), Forum (state gap — open, TICKET-7) |
| RERA-03 | RERA Matter | Breach of Contract *(proxy)* | RERA | Maharashtra | Fact extraction (similar names, multi-party) |
| CONT-01 | Contract Dispute | Breach of Contract | Civil Suit | Delhi | Limitation (trigger-date input validation) |
| CONT-02 | Contract Dispute | Breach of Contract | Civil Suit | Delhi | AI synthesis (substantive nuance — Section 27 ICA) |
| CONT-03 | Contract Dispute | Breach of Contract | Civil Suit | Maharashtra | AI synthesis (substantive nuance — Section 74 ICA), Forum (pecuniary boundary) |
| CONT-04 | Contract Dispute | Breach of Contract | Civil Suit | Karnataka | Baseline canary |
| APP-01 | Appeal | Appeal (Art. 116) | Civil Suit | Delhi | Limitation (off-by-one-day — TICKET-5, fixed 6 Aug 2026, now a regression check) |
| APP-02 | Appeal | Appeal (Art. 115) | Civil Suit | Delhi | Limitation (off-by-one-day, urgent — TICKET-5 regression check) |
| APP-03 | Appeal | Appeal (Art. 116) | Commercial Dispute | Maharashtra | Limitation (barred + TICKET-5 regression check), Forum |
| IA-01 | Interim Application | Possession *(underlying suit)* | Property Dispute | Delhi | AI synthesis (hearing/IA data blindness — open, TICKET-8) |
| IA-02 | Interim Application | Possession *(underlying suit)* | Property Dispute | Bihar | AI synthesis (hearing blindness, TICKET-8) + Forum (state gap, TICKET-7) |
| IA-03 | Interim Application | Breach of Contract *(underlying suit)* | Commercial Dispute | Karnataka | AI synthesis (hearing blindness, TICKET-8) + Forum (TICKET-6 regression check) |

## 3. Scenarios

### 3.1 Civil Suits

#### CIV-01 — Unsecured personal loan, comfortably within limitation (canary)

**Matter Description:** Ramesh Kumar Gupta lent ₹8,50,000 to a friend, Sanjay Malhotra, repayable on demand with 9% p.a. interest, evidenced by a signed promissory note. Repeated informal requests for repayment went nowhere; a formal legal notice finally drew a reply disputing the debt.

**Parties:**
- Petitioner/Plaintiff #1: Ramesh Kumar Gupta, Delhi
- Respondent/Defendant #1: Sanjay Malhotra, Delhi

**Facts:**
- 2024-03-10 — Loan of ₹8,50,000 disbursed via NEFT to Defendant.
- 2024-03-10 — Promissory note signed acknowledging the loan, repayable on demand, 9% p.a. interest.
- 2026-05-15 — Legal notice of demand sent via registered post.
- 2026-06-02 — Defendant's reply disputes the amount, alleges part of the sum was a gift.

**Evidence:** Exhibit P-1 (promissory note, uploaded PDF), Exhibit P-2 (NEFT transfer receipt), Exhibit P-3 (legal notice + postal tracking), Exhibit P-4 (Defendant's reply letter).

**Expected Limitation Result:** Suit category "Money Recovery." Cause-of-action date should be the loan disbursement date (2024-03-10) — that is what Article 19's trigger event ("when the loan is made or money is paid") requires. Expiry = **2027-03-10**. `is_barred = False`. Days remaining ≈ **216** (as of 2026-08-06). **Flag:** the note explicitly makes the loan "repayable on demand" — the legally precise article is arguably Article 20 or 22, not Article 19, but the tool's "Money Recovery" bucket lists Article 19 first and auto-selects it unless the advocate explicitly overrides via `selected_article`. Test whether the advocate notices this without prompting.

**Expected Forum Result:** Suit type "Civil Suit," claim value ₹8,50,000, jurisdiction state Delhi. Falls in Delhi's 0–20,00,000 band → **Civil Judge Court, Delhi**, District Courts, confidence "Deterministic," `is_unambiguous = True` (both parties in Delhi, cause of action in Delhi).

**Expected Legal Issues:** Recovery of money / breach of loan agreement; alternative framing as money had and received.

**Expected Evidence Gaps:** None, if all four exhibits are uploaded with actual files (not just exhibit-number labels).

**Expected AI Case Analysis Outcomes:** Matter summary correctly identifies a straightforward loan-recovery matter. Applicable statutes should surface Indian Contract Act, 1872 provisions if the corpus retrieval finds them — or explicitly say none were retrieved, never invent a section number. Possible causes of action should center on recovery of the loan with interest. Potential risks should mention the Defendant's gift-characterization defense. Recommended next steps might reasonably include considering an Order XXXVII (summary suit) route given the written acknowledgment — note whether the AI surfaces this on its own; it is not required to, but if it does, it's a positive signal of legal sophistication worth recording.

**Acceptance Criteria:**
- [ ] `is_barred == False`
- [ ] Limitation expiry date == 2027-03-10 (±0 days if COA date entered exactly as above)
- [ ] Days remaining within ±2 of 216
- [ ] Recommended forum == Civil Judge Court, Delhi (or the correct Delhi tier for the claim value if the advocate adjusts it)
- [ ] `is_unambiguous == True`
- [ ] No statute or section number appears in the analysis that is not either (a) retrieved from the corpus or (b) explicitly labeled as unconfirmed
- [ ] No case citation renders as a live hyperlink unless independently confirmed by the advocate on Indian Kanoon

---

#### CIV-02 — Declaratory suit, near-expiry (urgency test)

**Matter Description:** Meera Devi Agarwal seeks a declaration that she holds a one-third co-ownership share in the ancestral family house in Delhi. Her brother, Suresh Agarwal, first publicly denied her claim to any share over three years ago; she is only now consulting counsel.

**Parties:**
- Petitioner/Plaintiff #1: Meera Devi Agarwal, Delhi
- Respondent/Defendant #1: Suresh Agarwal, Delhi

**Facts:**
- 2023-08-20 — Suresh Agarwal, at a family gathering, explicitly and in writing (via a family WhatsApp group message, later screenshotted) denies Meera has any ownership share in the property.
- 2024-01-10 — Meera requests a copy of the property's mutation records; Suresh refuses to cooperate.
- 2026-07-28 — Meera consults counsel for the first time.

**Evidence:** Exhibit P-1 (screenshot of the WhatsApp denial, with visible timestamp), Exhibit P-2 (property mutation record request correspondence).

**Expected Limitation Result:** Suit category "Declaratory." Cause-of-action date = 2023-08-20 (when the right to sue first accrued, per Article 58's trigger event — the explicit denial, not the later refusal to share records, which is merely confirmatory). Expiry = **2026-08-20**. `is_barred = False`. Days remaining = **14** (as of 2026-08-06). This is a genuinely urgent filing window.

**Expected Forum Result:** Suit type "Civil Suit," claim value = stated property value for court-fee purposes (use ₹30,00,000 as a reasonable estimate), Delhi. Falls in Delhi's 0–20,00,000 or 20L–2Cr band depending on the exact figure entered — verify the tool's band assignment matches the claim value entered.

**Expected Legal Issues:** Declaration of title/co-ownership share; likely to be followed by a partition suit if the declaration succeeds.

**Expected Evidence Gaps:** Should flag that a formal legal notice asserting the ownership claim has not yet been sent, and that no valuation/title document (sale deed, will, or succession certificate establishing the ancestral chain) has been uploaded.

**Expected AI Case Analysis Outcomes:** Given the 14-day window, this is the single best test in the set of whether the tool's output *foregrounds* urgency rather than burying it as one data point among many. Check specifically whether "Recommended Next Steps" or "Potential Risks" leads with the limitation deadline, or whether it appears only in the passed-through Limitation Summary card with no narrative emphasis elsewhere.

**Acceptance Criteria:**
- [ ] `is_barred == False`
- [ ] Limitation expiry date == 2026-08-20
- [ ] Days remaining within ±1 of 14
- [ ] At least one of Potential Risks / Recommended Next Steps explicitly references the imminent limitation deadline, not just the passed-through Limitation Summary card
- [ ] Missing information correctly flags absence of a formal notice and title-chain documentation

---

#### CIV-03 — Injunction suit with no clean limitation category (category-fit gap)

**Matter Description:** A shopkeeper, Anil Chawla, has been running his provisions store from a rented shopfront in Karol Bagh, Delhi, for eleven years. Beginning early 2025, the landlord's nephew began repeatedly obstructing deliveries and threatening to physically lock Anil out, without any court order. Anil seeks a permanent injunction restraining interference with his peaceful possession — he is not seeking a money decree, a declaration of title, or possession of anything he doesn't already hold.

**Parties:**
- Petitioner/Plaintiff #1: Anil Chawla, Delhi
- Respondent/Defendant #1: Vikram Bhalla (landlord's nephew), Delhi

**Facts:**
- 2025-01-15 — First incident: Defendant blocks the shop's delivery entrance for several hours.
- 2025-03-02 — Defendant verbally threatens to change the locks.
- 2025-06-10 — Defendant physically obstructs a supplier's delivery van.
- 2026-07-01 — Defendant leaves a written notice at the shop threatening lockout "within 30 days."

**Evidence:** Exhibit P-1 (CCTV screenshot of the delivery obstruction), Exhibit P-2 (the written lockout threat notice).

**Expected Limitation Result:** **There is no Limitation Act article in the tool's fixed category list that cleanly fits a pure injunction suit.** The frontend's Suit Category dropdown offers exactly seven options (Money Recovery, Specific Performance, Possession, Declaratory, Breach of Contract, Appeal, Execution) — none of which is "Injunction." If the advocate is forced to pick the closest label (most likely "Declaratory," since neither party disputes title, only conduct), the system will apply Article 58's 3-year rule from whichever date is entered as cause-of-action, which is not actually the correct legal basis for an injunction suit (injunctions are generally governed by residual limitation principles tied to the continuing/recurring nature of the wrong, not a single accrual date in the same way a declaration is). This is a genuine category-modeling gap, not a data-entry error.

**Expected Forum Result:** Suit type "Civil Suit," claim value = nominal/notional valuation for an injunction suit (use ₹2,00,000 as a placeholder valuation), Delhi. Should fall in Delhi's lowest pecuniary band.

**Expected Legal Issues:** Permanent and/or interim injunction restraining interference with possession (Specific Relief Act, 1963, not the Limitation Act categories the tool models); possibly also a claim for damages for the obstructed deliveries.

**Expected Evidence Gaps:** Should flag that no tenancy/lease agreement establishing Anil's possessory right has been uploaded.

**Expected AI Case Analysis Outcomes:** Watch closely whether "Applicable Statutes" surfaces the Specific Relief Act, 1963 (relevant to injunctions) despite the Limitation Calculator being forced into an ill-fitting category — the RAG retrieval step is independent of the Limitation Calculator's category selection, so it should be able to find Specific Relief Act content from the facts narrative alone, which would be a genuinely good sign the two subsystems don't silently inherit each other's category errors.

**Acceptance Criteria:**
- [ ] Record which Suit Category the advocate was forced to select, and note explicitly in the validation report that this is a forced-fit, not a genuine match
- [ ] Confirm the Limitation Summary in the AI Case Analysis is treated by the advocate as advisory-only for this scenario, not authoritative (this is a judgment call to record, not a pass/fail on the tool)
- [ ] Applicable Statutes includes Specific Relief Act, 1963 content, OR explicitly shows no retrieval rather than a fabricated section
- [ ] Missing information flags the absent tenancy document

---

#### CIV-04 — Money recovery suit already barred, long-stale (condonation nuance)

**Matter Description:** A trader, Deepak Bansal, gave a friend a ₹3,20,000 interest-free loan in early 2020 to help set up a small business. The friend has never repaid despite years of informal reminders. Deepak is only now, in 2026, considering formal legal action.

**Parties:**
- Petitioner/Plaintiff #1: Deepak Bansal, Delhi
- Respondent/Defendant #1: Rohit Sethi, Delhi

**Facts:**
- 2020-01-05 — ₹3,20,000 handed over in cash, with a one-page handwritten acknowledgment signed by Rohit.
- 2020-01-05 to 2025-12: various informal WhatsApp reminders sent periodically (no formal legal notice at any point).
- 2026-07-15 — Deepak consults counsel for the first time.

**Evidence:** Exhibit P-1 (handwritten acknowledgment), Exhibit P-2 (a sample of WhatsApp reminder messages).

**Expected Limitation Result:** Suit category "Money Recovery," Article 19, cause-of-action date = 2020-01-05. Expiry = **2023-01-05**. `is_barred = True`. Barred by approximately **1,309 days (~3 years 7 months)** as of 2026-08-06. `condonation_required = True`.

**Flag — this is a deliberate stress test of a real gap:** the tool's `condonation_notes` field is a fixed template string regardless of how long the delay is — it reads the same whether a suit is barred by 10 days or 10 years. A 3-year-7-month delay makes a Section 5 condonation application a genuinely weak prospect as a matter of practice (courts require "sufficient cause" covering the *entire* period of delay, and informal WhatsApp reminders without any formal notice do little to establish diligence). Check whether the AI Case Analysis's Potential Risks section independently flags the low probability of condonation being granted, given the length of delay — the deterministic Limitation Summary card will not do this on its own; only the LLM-synthesized layer could catch it, and it isn't specifically instructed to weigh delay length either.

**Expected Forum Result:** Suit type "Civil Suit," claim value ₹3,20,000, Delhi. Delhi's lowest pecuniary band, Deterministic, unambiguous.

**Expected Legal Issues:** Recovery of loan, contingent on a successful Section 5 Limitation Act condonation application — the case cannot proceed to the merits at all without first clearing that hurdle.

**Expected Evidence Gaps:** Should flag the complete absence of any formal written demand/legal notice across six years — a significant gap for a condonation argument, since a documented paper trail of diligence strengthens "sufficient cause."

**Expected AI Case Analysis Outcomes:** This scenario should produce a Potential Risks section led by the limitation bar itself, not a secondary mention. Missing information should explicitly note the absence of a formal notice. If the AI's Recommended Next Steps jumps straight to "file the suit" without foregrounding the condonation application as a mandatory first hurdle, that is a finding to log.

**Acceptance Criteria:**
- [ ] `is_barred == True`
- [ ] Expiry date == 2023-01-05
- [ ] `condonation_required == True`
- [ ] Potential Risks explicitly names the limitation bar as the primary/highest risk, not a minor note
- [ ] Record (pass/fail is a judgment call, not a strict code check) whether the AI's language independently reflects that a multi-year, undocumented delay is a materially weaker condonation case than a short delay — the generic `condonation_notes` string alone does not do this

---

#### CIV-05 — Minimal input at the precondition floor (fact-extraction / synthesis stress)

**Matter Description:** A prospective client called Nitesh's office and gave a very vague description of a possible claim: "someone owes me money from a business deal, I don't remember exactly how much or when." No opposing party has been formally identified yet. This is a genuine, common real-world intake scenario — a matter opened on the barest possible information, before a proper client interview.

**Parties:**
- Petitioner/Plaintiff #1: Client name only (any name), Delhi — **no Respondent/Defendant is entered.**

**Facts:**
- Entry with `event_date` left blank and `fact_summary`: "Client states an unnamed business associate owes an unspecified sum, exact date and amount not yet confirmed."

**Evidence:** None uploaded.

**Expected Limitation Result / Forum Result:** Do not run the Limitation Calculator or Forum Advisor for this scenario — there isn't enough information to fill in their required fields meaningfully, and forcing plausible-sounding values would defeat the point of this test (which is to see how the system behaves with genuinely insufficient input, not to manufacture a data point).

**Expected Legal Issues:** None should be asserted with confidence — this scenario specifically tests whether the AI over-commits to a legal theory (e.g., confidently stating "breach of contract" or inventing specifics like a claim amount) from a single vague sentence.

**Expected Evidence Gaps:** Should be extensive — essentially everything.

**Expected AI Case Analysis Outcomes:** This is the most important AI-synthesis stress test in the set. A trustworthy system, given almost nothing to work with, should produce a short, honest Matter Summary that states plainly that critical facts (identity of the other party, amount, date, nature of the deal) are missing, and Missing Information / Recommended Next Steps should center on "conduct a full client interview to establish basic facts" rather than a padded-out analysis that reads as more confident than the input warrants. Watch specifically for **fabricated specificity** — any dollar amount, date, or party detail appearing in the output that was never entered is a serious finding, not a minor one, since it would mean the model is inventing facts rather than working from what was actually provided.

**Acceptance Criteria:**
- [ ] Matter can still be created and the AI Case Analysis endpoint still succeeds with exactly one party and one fact (the documented precondition floor)
- [ ] No specific amount, date, or party name appears anywhere in the output that was not entered by the tester
- [ ] Missing information / next steps foreground "identify the opposing party" and "establish basic facts via client interview" ahead of any substantive legal analysis
- [ ] Possible causes of action is either empty or explicitly hedged ("insufficient facts to identify a cause of action") rather than a confident assertion

### 3.2 Commercial Disputes

#### COM-01 — SaaS licensing dispute at the Commercial Courts Act threshold (forum-ordering defect)

**Matter Description:** Vertex Software Solutions Pvt. Ltd. licensed a custom inventory-management platform to Bluewave Retail Technologies LLP under a Software Development & Maintenance Agreement. Bluewave has not paid an invoice for the final milestone.

**Parties:**
- Petitioner/Plaintiff #1: Vertex Software Solutions Pvt. Ltd., Delhi
- Respondent/Defendant #1: Bluewave Retail Technologies LLP, Delhi

**Facts:**
- 2025-02-01 — Software Development & Maintenance Agreement signed.
- 2025-06-01 — Final milestone invoice raised for ₹3,00,000, payable within 30 days.
- 2025-07-01 — Payment due date passes with no payment.
- 2026-04-10 — Formal demand letter sent; no response received.

**Evidence:** Exhibit P-1 (signed agreement), Exhibit P-2 (invoice), Exhibit P-3 (demand letter).

**Expected Limitation Result:** Suit category "Breach of Contract," Article 55, cause-of-action date = 2025-07-01 (when the contract was broken — the missed payment due date). Expiry = **2028-07-01**. `is_barred = False`. Comfortably within limitation.

**Expected Forum Result:** Suit type "Commercial Dispute," claim value **exactly ₹3,00,000** (the Commercial Courts Act, 2015 §2(1)(i)/§6 minimum "Specified Value"), Delhi. `recommended_forum` should be the **Designated Commercial Court / Commercial Division, Delhi** — confirmed by direct execution against the live code.

> **TICKET-6, fixed 6 August 2026 — this scenario is now a regression check, not a live defect.** When this guide was originally authored, tracing `forum.py` found that `claim_value_inr >= 3_00_000` correctly added a Commercial Court option to `viable_options`, but the general civil-court option was then unconditionally **inserted at index 0** for any suit type other than RERA/Real Estate — ahead of the Commercial Court that was already there — so `recommended_forum = viable_options[0]` returned the general civil court instead, every time, for every qualifying Commercial Dispute. The fix (in `api/app/services/forum.py::determine_forum()`) makes the Commercial Court branch append the civil option after itself, the same pattern the RERA branch already used correctly, rather than displacing it. Locked in by `test_forum_commercial_courts_act_recommends_commercial_court_not_general_civil` in `api/tests/test_forum.py`. **If this scenario is ever run and the general civil court is recommended instead, that is a regression, not a known issue — treat it as a fresh Critical-severity defect.**

**Expected Legal Issues:** Breach of contract / recovery of the unpaid milestone invoice.

**Expected Evidence Gaps:** None significant if all three exhibits are attached.

**Expected AI Case Analysis Outcomes:** Jurisdiction Summary is a verbatim pass-through of whatever the Forum Advisor returned — it should now correctly show the Commercial Court as the recommendation.

**Acceptance Criteria:**
- [ ] `recommended_forum` == Designated Commercial Court / Commercial Division, Delhi. If the general civil court is returned instead, this is a regression of the fixed TICKET-6 defect — log it as Critical, not as an expected/known finding
- [ ] Confirm the general civil court option is still present in `viable_options` as a secondary option, just not recommended
- [ ] Confirm the AI Case Analysis's Jurisdiction Summary matches the Forum Advisor's `recommended_forum` exactly (verbatim pass-through, per [ADR-011](../ADR/ADR-011-ai-case-analysis-before-pleading.md)) — a mismatch here would be a separate defect (the deterministic pass-through failing)

---

#### COM-02 — Distributorship termination, Maharashtra (canary)

**Matter Description:** A regional FMCG distributor's dealership agreement with a manufacturer was terminated with immediate effect, without the notice period the agreement itself required, cutting off unpaid commission owed for the prior quarter.

**Parties:**
- Petitioner/Plaintiff #1: Konkan Distributors Pvt. Ltd., Maharashtra
- Respondent/Defendant #1: Sahyadri FMCG Ltd., Maharashtra

**Facts:**
- 2023-04-01 — Dealership Agreement executed, requiring 90 days' written notice for termination without cause.
- 2025-11-01 — Manufacturer terminates the agreement with immediate effect via a one-line email, no notice given.
- 2025-11-15 — Distributor's demand for unpaid Q3 commission (₹45,00,000) goes unanswered.

**Evidence:** Exhibit P-1 (Dealership Agreement), Exhibit P-2 (termination email), Exhibit P-3 (commission statement/ledger).

**Expected Limitation Result:** "Breach of Contract," Article 55, cause-of-action date = 2025-11-01 (the wrongful termination). Expiry = **2028-11-01**. Not barred.

**Expected Forum Result:** "Commercial Dispute," claim value ₹45,00,000, Maharashtra. `recommended_forum` should be the **Designated Commercial Court / Commercial Division, Maharashtra** (per the TICKET-6 fix — see COM-01). Use this scenario to confirm the fix holds state-independently, not just for Delhi: the general civil pecuniary table (which would otherwise place this claim in Maharashtra's unlimited/Civil Judge Senior Division band) must not override the Commercial Court recommendation.

**Expected Legal Issues:** Wrongful termination without contractually required notice; recovery of unpaid commission.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Should identify two distinct threads — the notice-period breach and the separate commission non-payment — as this fact pattern genuinely has two related but severable claims.

**Acceptance Criteria:**
- [ ] `is_barred == False`, expiry == 2028-11-01
- [ ] `recommended_forum` == Designated Commercial Court / Commercial Division, Maharashtra (confirms the TICKET-6 fix holds across states — a regression here would show the general Maharashtra civil-court band instead)
- [ ] AI analysis's possible causes of action includes both the notice-breach and commission-recovery threads, not just one collapsed claim

---

#### COM-03 — Cross-state marketplace payout dispute (forum ambiguity — positive control)

**Matter Description:** An online marketplace vendor based in Delhi has had payouts withheld by the marketplace operator, a company registered and headquartered in Karnataka, even though the vendor's transactions and cause of action arose from Delhi-based operations.

**Parties:**
- Petitioner/Plaintiff #1: Delhi Crafts Emporium, Delhi
- Respondent/Defendant #1: SwiftCart Marketplace Technologies Pvt. Ltd., Karnataka

**Facts:**
- 2025-09-01 — Vendor onboarded to the marketplace platform.
- 2026-01-15 — Marketplace begins withholding payouts citing an unspecified "policy review."
- 2026-03-01 — ₹18,00,000 in accumulated payouts remains withheld.
- 2026-04-05 — Formal demand sent; marketplace disputes the amount is owed.

**Evidence:** Exhibit P-1 (onboarding agreement), Exhibit P-2 (payout/transaction ledger), Exhibit P-3 (demand letter and marketplace's dispute response).

**Expected Limitation Result:** "Breach of Contract," Article 55, cause-of-action date = 2026-01-15 (when withholding began / the breach occurred). Expiry = **2029-01-15**. Not barred.

**Expected Forum Result:** "Commercial Dispute," claim value ₹18,00,000, jurisdiction state Delhi, `defendant_residence_state` = Karnataka. This is precisely the condition that triggers `forum.py`'s ambiguity branch: cause of action in Delhi, defendant resident in Karnataka → `is_unambiguous = False`, with a secondary forum option computed at the defendant's residence (Karnataka), and an explicit assumption note about Section 20(a) vs. Section 20(c) CPC choice. **This is a positive control for the ambiguity logic** — unlike PROP-01/PROP-04, Karnataka *is* present in `forum.py`'s state table, so the ambiguity-handling itself should work correctly. **Verified against the live code, post-TICKET-6 fix:** the response contains **three** viable options — the Delhi civil court, a Delhi Commercial Court option (claim clears the ₹3,00,000 threshold), and the Karnataka option — and `recommended_forum` correctly returns the **Delhi Commercial Court**, confirming the fix holds even in combination with the cross-state ambiguity branch, not just in the simpler single-state case COM-01 tests.

**Expected Legal Issues:** Breach of the marketplace onboarding agreement; wrongful withholding of payouts.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Jurisdiction Summary should reflect the ambiguity — `is_unambiguous: false` passed through — and ideally the AI's own text acknowledges the forum choice as a strategic decision for the advocate, not a settled fact.

**Acceptance Criteria:**
- [ ] `is_unambiguous == False`
- [ ] Three viable forum options present: Delhi civil court (cause of action), Delhi Commercial Court (claim ≥ ₹3,00,000), and Karnataka (defendant residence) — confirm the count matches; two would indicate the Commercial Court branch did not fire as expected
- [ ] The Delhi and Karnataka options carry correct, distinct governing provisions (Section 20(c) CPC for the Delhi option, Section 20(a) CPC for the Karnataka option)
- [ ] `recommended_forum` == Delhi Commercial Court — confirms the TICKET-6 fix holds even combined with cross-state ambiguity; a general-civil-court recommendation here would be a regression
- [ ] AI Case Analysis's Jurisdiction Summary correctly reflects `is_unambiguous: false`, not silently defaulting to certainty

---

#### COM-04 — Joint venture dispute with overlapping fraud allegation (multi-cause-of-action synthesis)

**Matter Description:** Two individuals formed a joint venture company to run a logistics business. One partner, who controlled the company's bank accounts, is alleged to have both breached the JV agreement's profit-sharing terms **and** to have diverted company funds to a personal account — two related but legally distinct wrongs (breach of contract, and potentially fraud/breach of fiduciary duty) arising from the same relationship.

**Parties:**
- Petitioner/Plaintiff #1: Arvind Nair, Delhi
- Respondent/Defendant #1: Karan Malhotra, Delhi
- Respondent/Defendant #2: Vantage Logistics JV Pvt. Ltd. (the JV entity itself, nominal party), Delhi

**Facts:**
- 2023-06-01 — JV Agreement executed, 50/50 profit-sharing between Arvind and Karan.
- 2024-08-01 to 2025-12-01 — Karan, as the account signatory, transfers a total of ₹1,20,00,000 out of the JV's operating account in a series of transactions to an account later traced to his personal name.
- 2026-01-10 — Arvind discovers the diversions during an annual audit.
- 2026-02-01 — Arvind confronts Karan; Karan claims the transfers were "reimbursements" for undocumented personal expenses advanced to the JV.

**Evidence:** Exhibit P-1 (JV Agreement), Exhibit P-2 (bank statements showing the transfers), Exhibit P-3 (audit report), Exhibit P-4 (WhatsApp exchange where Karan's "reimbursement" explanation is recorded).

**Expected Limitation Result:** This is genuinely ambiguous even for a human advocate — is the cause of action the first diversion (2024-08-01) or the date of discovery (2026-01-10)? For fraud, Section 17 of the Limitation Act extends time from the date of *discovery*, not the wrongful act — a nuance the tool's fixed categories do not model at all (there is no "fraud" category, and Article 55's trigger event is the breach itself, not discovery). Test with "Breach of Contract," Article 55, and cause-of-action date = 2024-08-01 (first diversion): expiry = **2027-08-01**, not barred either way, so the ambiguity doesn't change the bottom-line result here — but it should still be recorded as a modeling gap.

**Expected Forum Result:** "Commercial Dispute," claim value ₹1,20,00,000, Delhi. Falls in Delhi's ₹20,00,000–₹2,00,00,000 band → District Court/Additional District Judge, Delhi. (Note: this claim value is *below* the ₹2,00,00,000 High Court threshold — a deliberately different pecuniary band than COM-01's exact-threshold test, to broaden coverage of Delhi's three-tier table.)

**Expected Legal Issues:** This is the core test — does the AI correctly identify **two** distinct causes of action (breach of the JV profit-sharing agreement, and a separate claim for diversion of funds/breach of fiduciary duty, potentially with a criminal breach-of-trust dimension), or does it flatten the fact pattern into a single generic "breach of contract" claim?

**Expected Evidence Gaps:** Should flag that no independent forensic accounting has been conducted beyond the internal audit, which may be needed to fully trace all diverted funds.

**Expected AI Case Analysis Outcomes:** This is the primary AI-synthesis stress scenario in the full set. A strong result names both threads distinctly with separate supporting facts. A weak result collapses everything into one generic "Breach of Contract" entry and misses the fiduciary-duty/diversion dimension entirely, or conversely invents an overconfident fraud characterization the facts don't yet support (the WhatsApp "reimbursement" explanation means intent is genuinely disputed, not established).

**Acceptance Criteria:**
- [ ] Possible causes of action includes at least two distinct entries (breach of JV agreement; and a separate fund-diversion/fiduciary-duty entry), not one collapsed claim
- [ ] Neither entry asserts fraud as an established fact — the AI should reflect that Karan's explanation is disputed, not resolved, language like "alleged diversion" or "disputed characterization," not "Karan committed fraud"
- [ ] Missing information or evidence gaps flags the lack of independent forensic tracing
- [ ] Potential risks notes the Section 17 discovery-date limitation nuance is unmodeled by the deterministic Limitation Calculator (this is a record-and-note item, not a strict pass/fail on the tool)

### 3.3 Property Matters

#### PROP-01 — Possession suit, ancestral agricultural land, Uttar Pradesh (state-coverage gap)

**Matter Description:** A family dispute over ancestral agricultural land in rural Uttar Pradesh — one branch of the family has occupied and cultivated the land, refusing to recognize the plaintiff's inherited title share and denying access.

**Parties:**
- Petitioner/Plaintiff #1: Yogendra Singh, Uttar Pradesh
- Respondent/Defendant #1: Brijesh Singh, Uttar Pradesh

**Facts:**
- 2014-04-01 — Defendant's branch of the family takes exclusive physical possession of the disputed plot following the death of the common ancestor, excluding Plaintiff.
- 2024-06-15 — Plaintiff formally demands access/partition; refused.
- 2026-02-01 — Plaintiff obtains certified revenue records confirming his inherited title share.

**Evidence:** Exhibit P-1 (revenue/khatauni records), Exhibit P-2 (family genealogy/succession documentation).

**Expected Limitation Result:** "Possession," Article 65 (listed first in the tool's candidate list and therefore auto-selected unless overridden), 12 years, cause-of-action date = 2014-04-01 (when possession became adverse). Expiry = **2026-04-01**. As of 2026-08-06, **`is_barred = True`** — barred by exactly **127 days** (verified against the live `calculate_limitation()` function). This is itself worth double-checking carefully against the exact date entered, since it sits close enough to today's date that small variations in the actual cause-of-action date the advocate settles on could flip the result from barred to not-barred. **Deliberately chosen to sit just past the line**, so this scenario also tests whether the advocate and the tool agree on which side of the line the facts fall.

**Expected Forum Result:** Suit type "Property Dispute," claim value = land's stated value for court-fee purposes (use ₹35,00,000), `jurisdiction_state = "Uttar Pradesh"`, `property_location_state = "Uttar Pradesh"`. **This is the headline finding for this scenario:** `forum.py`'s `STATE_PECUNIARY_LIMITS` dictionary defines entries only for Delhi, Maharashtra, Karnataka, and a generic DEFAULT — **Uttar Pradesh has no entry**, despite being one of the three official Phase-1 states named in `CLAUDE.md` Decision 2 (Delhi, Maharashtra, UP). A UP matter silently falls through to the generic DEFAULT band, returning forum names like "Civil Judge Senior Division" / "District Court" — generic labels, not UP-specific court nomenclature (e.g., UP's actual civil court structure and the U.P. Civil Laws (Reforms, etc.) Act references) — while the response still carries `confidence: "Deterministic"`, which could mislead the advocate into treating a generic fallback answer as jurisdiction-verified for UP specifically. **This gap should be treated as a real product-quality finding, not a data-entry issue.**

**Expected Legal Issues:** Suit for possession based on title/adverse possession claim; likely to require an accompanying partition suit given the inherited-share framing.

**Expected Evidence Gaps:** Should flag that no prior legal notice was sent before the 2024 demand, and that no partition suit or mediation attempt has yet been documented.

**Expected AI Case Analysis Outcomes:** Given the barred limitation result, Potential Risks should lead with the limitation bar. Jurisdiction Summary, being a verbatim pass-through, will also carry the generic DEFAULT-band forum name — the AI layer has no way to independently catch or flag that this is a lower-confidence answer for UP specifically, since it trusts the Forum Advisor's own `"Deterministic"` label at face value.

**Acceptance Criteria:**
- [ ] Confirm `is_barred` — verify precisely against the exact cause-of-action date entered; record the actual result whichever way it falls, since this scenario is sensitive to small date variations by design
- [ ] Confirm the returned forum name/court category — **record it verbatim**. If it is a generic label ("Civil Judge Senior Division," "District Court") rather than UP-specific court nomenclature, this confirms the state-coverage gap
- [ ] Note explicitly in the Product Validation Report whether the `"Deterministic"` confidence label was, in the advocate's professional judgment, misleading here given UP has no dedicated rule set
- [ ] Missing information flags the absence of a pre-suit legal notice

---

#### PROP-02 — Possession suit based on prior possession, not title (article-selection + chronology test)

**Matter Description:** A commercial tenant was forcibly dispossessed from a shop in Delhi without any court process — the landlord simply changed the locks one weekend. The tenant is not claiming ownership, only seeking restoration of possession based on his prior lawful possession, which is a materially different legal basis (Article 64) from a title-based possession claim (Article 65).

**Parties:**
- Petitioner/Plaintiff #1: Prakash Traders (proprietor: Om Prakash Verma), Delhi
- Respondent/Defendant #1: Delhi Estates Pvt. Ltd. (landlord), Delhi

**Facts:**
- 2019-04-12 — Landlord changes the locks over a weekend without notice or court order, while the tenant is mid-lease.
- 2019-04-14 — Tenant lodges a police complaint (no FIR registered, treated as a civil matter).
- 2019-05-01 — Tenant sends a legal notice demanding restoration of possession; ignored.

*(Testing instruction: enter these three facts in reverse order — 2019-05-01 first, then 2019-04-14, then 2019-04-12 — to verify the AI Case Analysis's Chronological Facts section correctly re-sorts them by `event_date` regardless of entry order, per the deterministic sort in `case_analysis.py::_chronological_facts`.)*

**Evidence:** Exhibit P-1 (police complaint acknowledgment), Exhibit P-2 (legal notice).

**Expected Limitation Result:** "Possession" category — but the advocate must explicitly select **Article 64** via `selected_article` (the trigger being "date of dispossession," which is exactly this fact pattern), since the tool's default without an override is Article 65 (title-based). Cause-of-action date = 2019-04-12. Expiry = **2031-04-12** either way (both articles carry the same 12-year period, so this scenario does not test whether the *number* changes — it tests whether the advocate notices the article needs to be explicitly chosen at all, and whether the AI Case Analysis's Limitation Summary correctly reflects whichever article was actually selected, not silently substituting the default).

**Expected Forum Result:** "Property Dispute," claim value = nominal shop valuation (use ₹8,00,000), Delhi. Delhi's 0–20,00,000 band.

**Expected Legal Issues:** Suit for restoration of possession based on prior possession (not title) — a summary suit under Order XXI or a suit under Section 6 of the Specific Relief Act, 1963 (recovery of possession without proof of title, if filed within six months — note the six-month window here has long since passed given the facts, which is itself worth the AI surfacing as a missed faster remedy).

**Expected Evidence Gaps:** Should flag that no lease agreement establishing the tenancy has been uploaded.

**Expected AI Case Analysis Outcomes:** Regardless of entry order, Chronological Facts must display 2019-04-12, then 2019-04-14, then 2019-05-01, in that order. This is a directly checkable, code-level assertion (the sort is deterministic and independent of insertion order), not a matter of AI judgment.

**Acceptance Criteria:**
- [ ] Chronological Facts section displays the three facts in true date order (04-12, 04-14, 05-01) despite being entered in reverse — a failure here is a code-level defect, not an AI quality issue
- [ ] Confirm whether the advocate needed to explicitly select Article 64, and whether the AI Case Analysis's Limitation Summary reflects the actually-selected article
- [ ] AI analysis notes (or the advocate records as a gap if it doesn't) that the Section 6 Specific Relief Act six-month summary remedy has already lapsed, making this a full title/possession suit instead of the faster route
- [ ] Missing information flags the absent lease agreement

---

#### PROP-03 — Specific performance of sale deed, Maharashtra (citation/statute grounding)

**Matter Description:** A buyer paid the full agreed consideration for a residential flat in Pune under an Agreement to Sell, but the seller has since refused to execute the final sale deed, apparently having received a higher offer from a third party.

**Parties:**
- Petitioner/Plaintiff #1: Ananya Deshmukh, Maharashtra
- Respondent/Defendant #1: Sanjeev Kulkarni, Maharashtra

**Facts:**
- 2024-11-01 — Agreement to Sell executed for ₹95,00,000, with a fixed date for execution of the sale deed of 2025-09-30, full consideration paid via bank transfer on execution of the agreement.
- 2025-09-15 — Seller informally indicates he has received a better offer.
- 2025-09-30 — Sale deed execution date passes with no registration; seller refuses to appear before the Sub-Registrar.
- 2025-10-10 — Buyer's legal notice calling upon the seller to complete the sale is ignored.

**Evidence:** Exhibit P-1 (Agreement to Sell), Exhibit P-2 (proof of full payment), Exhibit P-3 (legal notice).

**Expected Limitation Result:** "Specific Performance," Article 54, cause-of-action date = 2025-09-30 (the date fixed for performance). Expiry = **2028-09-30**. Not barred.

**Expected Forum Result:** "Property Dispute," claim value = ₹95,00,000 (the sale consideration), Maharashtra. Falls in Maharashtra's unlimited/CJSD band.

**Expected Legal Issues:** Suit for specific performance of the Agreement to Sell (Specific Relief Act, 1963), with an alternative prayer for refund of consideration with damages if specific performance is not granted.

**Expected Evidence Gaps:** Should flag that no stamp duty/registration-readiness documentation has been prepared, and that title verification (encumbrance certificate) for the flat has not been placed on record.

**Expected AI Case Analysis Outcomes:** This is the designated citation-and-statute-grounding test in the set. Two things to check specifically: **(1) Applicable Statutes** — does retrieval surface Specific Relief Act, 1963 content (specific performance is squarely within its scope, since 2018 amendments made specific performance the default remedy rather than a discretionary one), and does it also surface the Indian Stamp Act / Registration Act, 1908 material relevant to the sale-deed registration angle, per the corpus described in the original Scope of Work Appendix B? A failure to retrieve either is worth recording as a corpus-completeness finding, not necessarily a code defect. **(2) Possible Precedents** — specific performance is an area with substantial reported Indian case law (e.g., landmark Supreme Court authority on time being of the essence in property contracts, and on the post-2018 amendment's effect on specific performance as a discretionary vs. near-mandatory remedy). If the AI proposes any case names here, verify each one independently on Indian Kanoon yourself before trusting the tool's `status: "verified"` label — this scenario is specifically chosen because real, checkable precedent exists, making it a fair test of whether the Citation Verifier's `verified`/`unverified` labeling matches independent reality, not just whether it renders a label at all.

**Acceptance Criteria:**
- [ ] Applicable Statutes includes Specific Relief Act, 1963 content (record as a defect/gap if entirely absent)
- [ ] Record whether Indian Stamp Act / Registration Act, 1908 content is retrieved at all — this directly tests corpus completeness for the property-transaction statutes named in the original Scope of Work
- [ ] For every entry in Possible Precedents, independently verify on Indian Kanoon whether the case name is real and whether the tool's `verified`/`unverified` status matches — record any mismatch as a defect regardless of direction (a real case marked unverified, or a non-existent case marked verified, are both serious findings)
- [ ] Missing information flags the absent encumbrance certificate

---

#### PROP-04 — Easement/boundary dispute, Bihar (compound gap: category + state)

**Matter Description:** Two adjoining landowners in rural Bihar dispute a shared access path — one has begun constructing a boundary wall that would cut off the other's only vehicular access to the public road, a right the family claims to have exercised for over two decades.

**Parties:**
- Petitioner/Plaintiff #1: Ramnath Yadav, Bihar
- Respondent/Defendant #1: Bhola Prasad, Bihar

**Facts:**
- 2003 (exact date unknown — enter as 2003-01-01 with a note in `relevance_notes` that the exact date is not established) — Family begins regularly using the access path, undisputed for two decades.
- 2026-05-01 — Defendant begins construction of a boundary wall across the path.
- 2026-05-20 — Plaintiff's informal protest to the village panchayat goes unresolved.
- 2026-06-15 — Wall construction is roughly 60% complete.

**Evidence:** Exhibit P-1 (photographs of the wall construction in progress).

**Expected Limitation Result:** Like CIV-03, this is an injunction-flavored dispute (restraining completion of the wall, and/or a declaration of easementary right by prescription) with no clean fit in the tool's seven fixed categories. If forced into "Declaratory" with cause-of-action date = 2026-05-01 (when the interference began), Article 58 gives expiry **2029-05-01** — plenty of time, so the category mismatch doesn't create a false urgency/false safety problem here, but it does mean the "declaration" framing misses that this is really about an easement acquired by prescriptive use over 20+ years (Indian Easements Act, 1882, §15), a distinct legal theory the Limitation Act category list has no way to represent.

**Expected Forum Result:** "Property Dispute," claim value = nominal (use ₹5,00,000), `jurisdiction_state = "Bihar"`. **This compounds PROP-01's finding**: Bihar is not merely missing UP's specific treatment — it is not present in `STATE_PECUNIARY_LIMITS` *and* it is not one of the three CLAUDE.md Phase-1 states at all (Delhi, Maharashtra, UP only; other states are meant to "fall back to Central law plus a verify state rules flag" per `CLAUDE.md` Decision 2). Confirm the actual returned behavior: does the system produce a generic DEFAULT-band answer with no visible "verify state rules" flag or warning to the advocate that Bihar-specific court structure was not consulted? If so, this is the most concrete instance in the whole test set of the product's own stated Decision 2 policy (state fallback should carry an explicit "verify" flag) not actually being implemented anywhere in the Forum Advisor's response shape — there is no such field in `ForumAdvisorResponse` at all.

**Expected Legal Issues:** Injunction restraining obstruction of an easementary right of way; declaration of prescriptive easement under the Indian Easements Act, 1882.

**Expected Evidence Gaps:** Should flag the complete absence of any documentary evidence (revenue records, prior correspondence, witness statements) supporting 20+ years of continuous use — the photographs alone only establish the current dispute, not the historical prescriptive claim the case actually depends on.

**Expected AI Case Analysis Outcomes:** Watch whether Applicable Statutes surfaces the Indian Easements Act, 1882 at all — this act's presence in the ingested corpus is not confirmed anywhere in the project's documentation (it is not listed in the original Scope of Work Appendix B statute list), so a failure to retrieve it may reflect a genuine corpus gap, not a retrieval-logic failure — worth distinguishing between the two in the report.

**Acceptance Criteria:**
- [ ] Record the exact forum/court name returned for Bihar — confirm whether it is the generic DEFAULT band
- [ ] Confirm there is no "verify state rules" indicator anywhere in the Forum Advisor response or the AI Case Analysis for a non-Phase-1 state — record this as a policy-implementation gap against `CLAUDE.md` Decision 2 if absent
- [ ] Record whether Indian Easements Act, 1882 content is retrieved (record as a corpus-coverage finding, not a code defect, given it isn't in the documented statute list)
- [ ] Missing information flags the absence of historical-use documentation supporting the prescriptive easement claim

### 3.4 RERA Matters

#### RERA-01 — Delayed possession, refund with interest, Delhi (forum ordering — positive control)

**Matter Description:** A homebuyer paid the full consideration for a flat in a Delhi residential project; possession, committed for June 2024, is now over two years delayed with no firm new date given.

**Parties:**
- Petitioner/Plaintiff #1: Priya Malhotra (Allottee), Delhi
- Respondent/Defendant #1: Skyline Realtors Pvt. Ltd. (Promoter), Delhi

**Facts:**
- 2022-03-01 — Flat Buyer's Agreement executed, ₹68,00,000 total consideration, committed possession date 2024-06-30.
- 2022-03-01 to 2023-12-01 — Full consideration paid in installments per the agreed payment plan.
- 2024-06-30 — Committed possession date passes with construction visibly incomplete.
- 2026-05-01 — Promoter's project update states no firm revised date is available.

**Evidence:** Exhibit P-1 (Flat Buyer's Agreement), Exhibit P-2 (payment receipts), Exhibit P-3 (promoter's project update communication).

**Expected Limitation Result:** No clean RERA-specific category exists in the tool (as with RERA-02 below); if forced into "Breach of Contract," Article 55, cause-of-action date = 2024-06-30 (the missed committed date). Expiry = **2027-06-30**. Not barred. Note for the report: RERA complaints under §18 are not, strictly, ordinary civil breach-of-contract suits — they proceed before a specialized tribunal under a statutory scheme, and RERA authorities have historically taken a more claimant-favorable view of delay than a generic breach-of-contract limitation analysis might suggest. Record this as a category-fit caveat, same family of finding as CIV-03/PROP-04 but specific to RERA.

**Expected Forum Result:** Suit type "RERA," claim value ₹68,00,000 + interest (use ₹75,00,000 as an estimate including interest), `jurisdiction_state = "Delhi"`, `property_location_state = "Delhi"`. **This is the intended positive control, contrasting directly with COM-01/COM-02/IA-03:** for `suit_type in ("RERA", "Real Estate")`, `forum.py` appends the general civil option *after* the RERA tribunal option rather than inserting it at index 0 — so `recommended_forum = viable_options[0]` correctly returns the **Real Estate Regulatory Authority (RERA), Delhi**. Confirm this is what actually happens; if it is, this is the one scenario in the whole set that should demonstrate the ordering logic working exactly as intended.

**Expected Legal Issues:** Complaint under RERA Act, 2016 §18 for delayed possession; refund of the full amount paid with prescribed interest, or alternatively, possession with compensation for delay.

**Expected Evidence Gaps:** None significant if all three exhibits are attached.

**Expected AI Case Analysis Outcomes:** Applicable Statutes should surface RERA Act, 2016 content if the corpus has it ingested — this is itself worth confirming, since RERA/state-rule corpus coverage for Delhi specifically was named in the original Scope of Work as a Phase-1 priority state.

**Acceptance Criteria:**
- [ ] `recommended_forum` == Real Estate Regulatory Authority (RERA), Delhi — confirm this explicitly, since it is the contrasting positive control to COM-01's defect
- [ ] Record the category-fit caveat about Article 55 not being a fully accurate proxy for a RERA §18 claim
- [ ] Confirm RERA Act, 2016 content appears in Applicable Statutes, or record its absence as a corpus-coverage gap
- [ ] Jurisdiction Summary in the AI Case Analysis correctly shows the RERA tribunal, matching the Forum Advisor verbatim

---

#### RERA-02 — Structural defect claim under the defect liability period, Uttar Pradesh (no correct limitation category + state gap)

**Matter Description:** An allottee took possession of a flat in a Noida (UP) project 18 months ago; visible structural issues (wall seepage, cracked flooring) have since emerged, which the allottee believes the promoter is obligated to rectify at no cost under RERA's statutory defect liability period.

**Parties:**
- Petitioner/Plaintiff #1: Anjali Rastogi (Allottee), Uttar Pradesh
- Respondent/Defendant #1: Ganga Infrabuild Pvt. Ltd. (Promoter), Uttar Pradesh

**Facts:**
- 2025-02-01 — Possession taken, occupancy certificate on file.
- 2025-08-01 — First visible seepage noticed in a bedroom wall.
- 2026-01-15 — Cracked flooring noticed in the living room.
- 2026-03-01 — Written complaint to the promoter; promoter disputes the defects are structural rather than cosmetic wear.

**Evidence:** Exhibit P-1 (occupancy certificate), Exhibit P-2 (dated photographs of the seepage), Exhibit P-3 (dated photographs of the cracked flooring), Exhibit P-4 (written complaint and promoter's response).

**Expected Limitation Result:** **There is no correct answer available in the tool's fixed categories for this fact pattern at all.** RERA Act, 2016 §14(3) creates a statutory five-year defect liability period running from the date of possession — this is not a Limitation Act "cause of action accrues, then N years to sue" structure at all; it's a fixed statutory window during which the promoter's rectification obligation exists, and the claim logic is completely different in kind from every category `limitation.py` models. Forcing this into "Breach of Contract" (Article 55, cause-of-action = first defect noticed, 2025-08-01, expiry 2028-08-01) produces a numerically plausible-looking result that is not actually the correct legal framework at all. **Record explicitly that the tool's limitation output for this scenario should not be relied upon** — this is not primarily a bug to fix quickly, but a category the Limitation Engine simply does not represent, worth surfacing clearly before any future work builds on it.

**Expected Forum Result:** "RERA," claim value = estimated repair cost (use ₹4,50,000), `jurisdiction_state = "Uttar Pradesh"`, `property_location_state = "Uttar Pradesh"`. Combines with the UP state-coverage gap from PROP-01: the RERA-specific branch of `forum.py` does not itself depend on `STATE_PECUNIARY_LIMITS` (the RERA tribunal option is added unconditionally for the state named), so the RERA recommendation itself should be state-name-correct ("Real Estate Regulatory Authority (RERA), Uttar Pradesh") even though UP is missing from the *general civil* pecuniary table — a useful contrast showing the gap is specifically in the general civil-court logic, not universal.

**Expected Legal Issues:** RERA §14(3) defect liability claim for rectification at the promoter's cost (not a breach-of-contract damages claim in the conventional sense).

**Expected Evidence Gaps:** None significant — the dated photograph documentation here is a good example of well-evidenced facts, useful as a contrast to the sparser scenarios elsewhere in the set.

**Expected AI Case Analysis Outcomes:** Watch whether the AI's own text (independent of the deterministic Limitation Summary card) correctly identifies this as a statutory defect-liability matter rather than treating the passed-through Article 55 breach-of-contract limitation figure as authoritative. This is a meaningful test of whether the LLM-synthesized layer can catch a categorization problem the deterministic layer has no way to flag on its own.

**Acceptance Criteria:**
- [ ] `recommended_forum` correctly names "Real Estate Regulatory Authority (RERA), Uttar Pradesh" specifically (not a generic fallback) — confirm the RERA branch is state-name-correct even where the general civil branch is not
- [ ] Record explicitly, regardless of what number the Limitation Calculator produces, that this scenario has no correct representation in the current category list — this is a "record the gap," not "pass/fail the math," criterion
- [ ] Check whether the AI Case Analysis text itself (Matter Summary or Potential Risks) independently notes that this is a statutory defect-liability matter rather than a conventional limitation-governed claim — record whether it does or doesn't; either result is informative

---

#### RERA-03 — Multi-allottee collective complaint, Maharashtra (fact-extraction stress: similar names)

**Matter Description:** Several allottees in the same MahaRERA-registered project, all facing the same delayed-possession issue, are considering filing jointly. Several of the allottees have similar surnames, a deliberately realistic and common complicating factor in Indian multi-party matters.

**Parties:**
- Petitioner/Plaintiff #1: Suresh Sharma, Maharashtra
- Petitioner/Plaintiff #2: Suman Sharma (no relation to Petitioner #1, despite the shared surname), Maharashtra
- Petitioner/Plaintiff #3: Ramesh Gupta, Maharashtra
- Petitioner/Plaintiff #4: Rakesh Gupta (brother of Petitioner #3, co-allottee of a different unit), Maharashtra
- Respondent/Defendant #1: Horizon Heights Developers LLP, Maharashtra

**Facts:**
- 2022-01-01 — All four allottees separately execute Flat Buyer's Agreements for different units in the same project, each with a committed possession date of 2024-03-31.
- 2024-03-31 — Committed date passes, project roughly 70% complete.
- 2025-06-01 — Allottees begin informally coordinating.
- 2026-04-01 — Joint written demand sent to the developer on behalf of all four.

**Evidence:** Exhibit P-1 (Suresh Sharma's Flat Buyer's Agreement), Exhibit P-2 (Suman Sharma's Flat Buyer's Agreement), Exhibit P-3 (Ramesh Gupta's Flat Buyer's Agreement), Exhibit P-4 (Rakesh Gupta's Flat Buyer's Agreement), Exhibit P-5 (joint demand letter).

**Expected Limitation Result:** Same category-fit caveat as RERA-01, "Breach of Contract" Article 55 as proxy, cause-of-action date = 2024-03-31. Expiry = **2027-03-31**. Not barred.

**Expected Forum Result:** "RERA," aggregate claim value (use ₹22,00,000), Maharashtra. Should correctly recommend the RERA tribunal per the same positive-control logic as RERA-01.

**Expected Legal Issues:** Collective/joint RERA §18 complaint on behalf of all four allottees.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** This is the fact-extraction stress test. Verify carefully that the Matter Summary and Chronological Facts correctly attribute each Flat Buyer's Agreement and each fact to the *correct* individual allottee — specifically watch for the model conflating "Suresh Sharma" with "Suman Sharma," or treating the two Guptas as a single party, or dropping one of the four allottees from the narrative entirely. Because `case_analysis.py`'s PII masking step assigns stable `PARTY_A`/`PARTY_B`-style placeholders per detected name before the prompt reaches the LLM, this scenario also indirectly tests whether the masking/unmasking round-trip correctly keeps four distinct parties distinct rather than collapsing similar names into the same placeholder — a real, code-level risk given the masker's name-detection logic, worth checking explicitly.

**Acceptance Criteria:**
- [ ] All four Petitioners are correctly named and distinguished in the Matter Summary — none dropped, none merged, none swapped with another
- [ ] Chronological Facts correctly attributes each Flat Buyer's Agreement fact to its correct allottee (if the fact-entry UI captures this level of detail — if it doesn't, record that as a UI/data-model gap for multi-party matters, since the current `litigation_facts_evidence` schema has no field linking a fact to a specific party)
- [ ] No party name in the output is a garbled or masked-then-incorrectly-unmasked variant (e.g., "PARTY_C" appearing literally in the rendered text would be a serious masking-round-trip defect)
- [ ] Jurisdiction Summary correctly recommends the RERA tribunal, consistent with RERA-01's positive control

### 3.5 Contract Disputes

#### CONT-01 — NDA breach, ambiguous trigger date (limitation input-validation gap)

**Matter Description:** A former contractor bound by a mutual NDA is discovered to have shared confidential product-roadmap information with a direct competitor. The actual disclosure happened well before it was discovered.

**Parties:**
- Petitioner/Plaintiff #1: Nimbus Analytics Pvt. Ltd., Delhi
- Respondent/Defendant #1: Deepak Oberoi (former contractor), Delhi

**Facts:**
- 2024-06-01 — Mutual NDA executed as part of the contractor engagement.
- 2024-11-20 — Deepak shares confidential roadmap documents with a competitor via personal email (established later via forensic email review — this is the actual date of breach).
- 2026-01-25 — Nimbus first learns of the leak via an unrelated industry conversation.
- 2026-02-01 — Forensic review of Deepak's work email confirms the 2024-11-20 disclosure date.

**Evidence:** Exhibit P-1 (NDA), Exhibit P-2 (forensic email review report establishing the actual disclosure date).

**Expected Limitation Result:** "Breach of Contract," Article 55, whose trigger event is explicitly **"when the contract is broken,"** i.e., the actual disclosure date (2024-11-20) — not the later discovery date (2026-01-25). Correct cause-of-action date = 2024-11-20. Expiry = **2027-11-20**. Not barred either way, but this scenario is specifically designed to test a subtler risk than the arithmetic itself: **the tool computes deterministically correct math off of whatever date is entered, with no independent check on whether the entered date is legally the correct trigger event.** If the advocate (understandably, since that's when the client "found out" about it) enters the *discovery* date (2026-01-25) instead of the *breach* date (2024-11-20), the tool will silently and confidently produce a different — and legally wrong — expiry date (2029-01-25), with nothing in the UI or the AI Case Analysis flagging that the entered date might be the wrong one. **This is a genuine trust-design gap worth naming precisely:** the system's "deterministic, not LLM-generated" guarantee for the Limitation Summary only guarantees the *arithmetic* is correct given the input — it does not, and currently cannot, validate that the advocate selected the legally correct trigger date in the first place.

**Expected Forum Result:** "Civil Suit," claim value = estimated competitive harm (use ₹25,00,000), Delhi.

**Expected Legal Issues:** Breach of the NDA's confidentiality obligations; potential claim for damages / injunctive relief restraining further use of the confidential information.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Run this scenario **twice** — once with the correct breach-date entry (2024-11-20) and once with the discovery-date entry (2026-01-25) — and compare the two Limitation Summaries. Both will look equally confident and equally "deterministic," despite one of them resting on a legally incorrect premise. This side-by-side comparison is the actual test.

**Acceptance Criteria:**
- [ ] With the correct breach-date entry, expiry == 2027-11-20
- [ ] With the (incorrect) discovery-date entry, expiry == 2029-01-25 — confirm the tool produces this with the exact same "Deterministic"/confident presentation as the correct run, with no warning of any kind
- [ ] Record explicitly in the Product Validation Report: nothing anywhere in the current UI or AI Case Analysis prompts the advocate to double-check which date they've entered represents the correct legal trigger event — this is a design gap to log, not a bug to mark "fixed/not fixed"

---

#### CONT-02 — Non-compete enforcement (substantive-law nuance test)

**Matter Description:** An employer wants to sue a former senior employee for joining a direct competitor within the 12-month non-compete period stipulated in her employment contract.

**Parties:**
- Petitioner/Plaintiff #1: Prism Consulting Group Pvt. Ltd., Delhi
- Respondent/Defendant #1: Kavita Rao, Delhi

**Facts:**
- 2023-04-01 — Employment Agreement executed, including a clause restraining Kavita from joining a competing firm for 12 months post-termination.
- 2025-12-15 — Kavita's employment ends (resignation).
- 2026-01-10 — Kavita joins a direct competitor.
- 2026-01-20 — Prism sends a cease-and-desist letter citing the non-compete clause.

**Evidence:** Exhibit P-1 (Employment Agreement with the non-compete clause), Exhibit P-2 (evidence of Kavita's new employment), Exhibit P-3 (cease-and-desist letter).

**Expected Limitation Result:** "Breach of Contract," Article 55, cause-of-action date = 2026-01-10 (the date of joining the competitor — the breach itself). Expiry = **2029-01-10**. Not barred.

**Expected Forum Result:** "Civil Suit," claim value ₹15,00,000 (estimated damages), Delhi.

**Expected Legal Issues:** This is the substantive-law test in the set. Indian courts have consistently held, under **Section 27 of the Indian Contract Act, 1872**, that a post-termination (as opposed to during-employment) non-compete restraint is generally void as an unreasonable restraint of trade, subject to narrow exceptions — this is well-settled, reported law, not a fringe position. A trustworthy analysis should flag the enforceability of this specific clause as a live, material risk, not simply assert "breach of contract" as though the clause is presumptively valid.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Check specifically whether **Potential Risks** (or, less ideally but still acceptable, Possible Causes of Action's own description text) surfaces the Section 27 enforceability question. A result that treats the non-compete clause as straightforwardly enforceable, with no mention of the restraint-of-trade doctrine, should be logged as a substantive-accuracy gap — this is exactly the kind of issue a real advocate would catch instantly and would erode trust quickly if the tool missed it silently.

**Acceptance Criteria:**
- [ ] `is_barred == False`, expiry == 2029-01-10
- [ ] Applicable Statutes or Potential Risks references Indian Contract Act, 1872 (ideally Section 27 specifically, or restraint-of-trade language generally)
- [ ] Record explicitly whether the analysis flags the non-compete clause's enforceability as a material risk, or treats it as presumptively valid — the former is the trustworthy result, the latter is a defect to log
- [ ] If Possible Precedents includes any case name, independently verify it — Section 27 restraint-of-trade jurisprudence includes well-known, real, checkable Supreme Court authority, making this a fair grounding test similar to PROP-03

---

#### CONT-03 — SLA penalty clause dispute (substantive-law nuance + Maharashtra pecuniary boundary)

**Matter Description:** A service provider failed to meet uptime SLA commitments under a Service Agreement, which contains a clause specifying a fixed "penalty" of ₹50,000 per day of downtime beyond the SLA threshold, capped at ₹6,00,000.

**Parties:**
- Petitioner/Plaintiff #1: Coral Retail Systems Pvt. Ltd., Maharashtra
- Respondent/Defendant #1: NetSecure IT Services LLP, Maharashtra

**Facts:**
- 2024-09-01 — Service Agreement executed, 99.5% uptime SLA, ₹50,000/day penalty for breaches beyond a 4-hour monthly grace period, capped at ₹6,00,000.
- 2025-04-01 to 2025-04-15 — A prolonged outage results in 12 days of SLA breach beyond the grace period.
- 2025-05-01 — Full ₹6,00,000 cap invoiced to the provider.
- 2025-05-01 to present — Provider refuses to pay, calling the clause an unenforceable penalty rather than genuine pre-estimated liquidated damages.

**Evidence:** Exhibit P-1 (Service Agreement with the SLA/penalty clause), Exhibit P-2 (uptime monitoring logs for the outage period), Exhibit P-3 (invoice for the capped amount), Exhibit P-4 (provider's refusal correspondence).

**Expected Limitation Result:** "Breach of Contract," Article 55, cause-of-action date = 2025-05-01 (when the provider's refusal to pay crystallized the dispute) or arguably 2025-04-15 (when the last day of the breach period occurred) — record which the advocate selects and why, since this is a genuinely debatable choice, similar in kind to (though less stark than) CONT-01's ambiguity. Using 2025-05-01: expiry = **2028-05-01**. Not barred.

**Expected Forum Result:** "Civil Suit," claim value **₹6,00,000** — deliberately chosen to sit just above Maharashtra's ₹5,00,000 Civil Judge Junior Division threshold, landing in the Civil Judge Senior Division/unlimited band. A boundary-adjacent test complementing COM-01's exact-threshold Commercial Courts Act test, this time on the general Maharashtra pecuniary table rather than the Commercial Courts Act.

**Expected Legal Issues:** The substantive question is whether the ₹50,000/day clause, capped at ₹6,00,000, is enforceable as genuine **liquidated damages** (a reasonable pre-estimate of loss) under **Section 74 of the Indian Contract Act, 1872**, or is void as a **penalty** — Indian law (unlike some common-law jurisdictions) does not draw a sharp penalty/liquidated-damages line the same way, and Section 74 generally permits recovery of "reasonable compensation" not exceeding the stipulated sum regardless of the label used, but the provider's specific defense (calling it an unenforceable penalty) is a real, commonly-raised argument the analysis should engage with, not dismiss.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Check whether the analysis engages with the Section 74 liquidated-damages-vs-penalty question directly (a sophisticated result) or simply asserts the clause is straightforwardly enforceable / straightforwardly a penalty without reasoning (a shallow result either way).

**Acceptance Criteria:**
- [ ] Confirm which cause-of-action date the advocate selected and record it; either 2028-05-01 (from 2025-05-01) or a comparably reasoned alternative is acceptable — the point is documenting the choice, not a single "correct" date
- [ ] Forum falls in Maharashtra's unlimited band (claim ₹6,00,000 > ₹5,00,000 threshold)
- [ ] Applicable Statutes or Possible Causes of Action references Indian Contract Act, 1872, ideally Section 74 specifically
- [ ] Record whether the analysis substantively engages with the liquidated-damages-vs-penalty question or merely asserts a conclusion — the former is the trustworthy result

---

#### CONT-04 — Consultancy fee dispute, Karnataka (canary)

**Matter Description:** A management consultant's retainer invoice for the final project phase went unpaid after the client claimed dissatisfaction with the deliverables — a common, low-drama fee dispute included deliberately as a second clean baseline scenario, on a different state/pecuniary band than CIV-01.

**Parties:**
- Petitioner/Plaintiff #1: Meridian Consulting Advisors, Karnataka
- Respondent/Defendant #1: Bangalore Fresh Foods Pvt. Ltd., Karnataka

**Facts:**
- 2025-02-01 — Consultancy/Retainer Agreement executed for a 6-month engagement, ₹4,00,000 for the final phase, payable on delivery.
- 2025-07-15 — Final deliverables submitted.
- 2025-08-01 — Invoice due date passes with no payment; client claims dissatisfaction with deliverable quality, first raised only after the invoice was sent.
- 2026-01-10 — Formal demand letter sent; unanswered.

**Evidence:** Exhibit P-1 (Consultancy Agreement), Exhibit P-2 (final deliverables submission email/receipt), Exhibit P-3 (invoice), Exhibit P-4 (demand letter).

**Expected Limitation Result:** "Breach of Contract," Article 55, cause-of-action date = 2025-08-01 (invoice due date / payment breach). Expiry = **2028-08-01**. Not barred.

**Expected Forum Result:** "Civil Suit," claim value ₹4,00,000, Karnataka. Falls in Karnataka's 0–5,00,000 band → Civil Judge Junior Division, Karnataka. Deterministic, unambiguous.

**Expected Legal Issues:** Recovery of the unpaid consultancy fee; the client's belated quality objection is a factual dispute for trial, not a jurisdictional or limitation issue.

**Expected Evidence Gaps:** None significant.

**Expected AI Case Analysis Outcomes:** Should be a clean, coherent, well-supported analysis with no significant flags — this scenario, alongside CIV-01, exists specifically as a control to confirm the happy path still works cleanly on a materially different state/category combination.

**Acceptance Criteria:**
- [ ] `is_barred == False`, expiry == 2028-08-01
- [ ] Forum == Civil Judge Junior Division, Karnataka, Deterministic, unambiguous
- [ ] No spurious risks, gaps, or ungrounded statute references appear — a clean scenario producing a cluttered or over-hedged analysis would itself be worth recording as a finding (over-caution has its own trust cost)

### 3.6 Appeals

#### APP-01 — First appeal to the High Court (off-by-one-day limitation defect)

**Matter Description:** A litigant who lost a money-recovery suit in the District Court wishes to file a first appeal to the High Court of Delhi.

**Parties:**
- Petitioner/Appellant #1: Rajiv Malhotra, Delhi
- Respondent #1: Sunita Bhatia, Delhi

**Facts:**
- 2026-06-20 — District Court decree passed against the Appellant.
- 2026-06-25 — Certified copy of the decree obtained.

**Evidence:** Exhibit P-1 (certified copy of the decree).

**Expected Limitation Result:** "Appeal," Article 116 (High Court appeal, listed first and auto-selected), cause-of-action date = 2026-06-20 (date of the decree). Expiry = **2026-09-18** (exactly 90 days from the decree date). `is_barred = False`. Days remaining = **43** (as of 2026-08-06).

> **TICKET-5, fixed 6 August 2026 — this scenario is now a regression check.** This was originally the single most important finding in this guide: Article 116 is coded in `limitation.py` as `"statutory_period_years": 0.2465` (comment: `# 90 days`), and the day-based branch of `calculate_limitation()` computed `int(0.2465 * 365)` = `int(89.9725)` = **89**, one day short of the correct statutory period — producing an expiry of 2026-09-17 and 42 days remaining, both objectively wrong. The fix changes the truncating `int()` to `round()`, which correctly recovers the intended 90-day period from the stored fraction. Locked in by `test_limitation_appeal_article_116_ninety_days_exact` in `api/tests/test_limitation.py`. **If this scenario is ever run and produces 2026-09-17 / 42 days instead of 2026-09-18 / 43 days, that is a regression — treat it as a fresh Critical-severity defect, not a known issue.**

**Expected Forum Result:** Not applicable to a first appeal in the same way as a fresh suit — if run for completeness, use "Civil Suit," claim value matching the original suit's decretal amount (use ₹8,00,000), Delhi.

**Expected Legal Issues:** First appeal under Section 96 CPC against the decree.

**Expected Evidence Gaps:** Should flag that no memorandum of appeal grounds has yet been drafted (expected — that's downstream of this analysis).

**Expected AI Case Analysis Outcomes:** The Limitation Summary card, being a verbatim pass-through, should now carry the correct 2026-09-18 expiry date into the advocate-facing analysis.

**Acceptance Criteria:**
- [ ] Confirm the tool's computed expiry date == 2026-09-18. If it is 2026-09-17 instead, this is a regression of the fixed TICKET-5 defect — log it as Critical
- [ ] Confirm days remaining == 43 (not 42)
- [ ] Confirm the AI Case Analysis's Limitation Summary matches whatever the Limitation Calculator produced exactly (verbatim pass-through check) — a mismatch here would be a second, separate defect

---

#### APP-02 — Appeal to District Court, urgent (off-by-one-day defect, second article)

**Matter Description:** An appeal from a Small Causes Court order to the District Court, filed on a tight statutory clock.

**Parties:**
- Petitioner/Appellant #1: Vinod Chugh, Delhi
- Respondent #1: Meena Kapoor, Delhi

**Facts:**
- 2026-07-20 — Small Causes Court order passed against the Appellant.

**Evidence:** Exhibit P-1 (certified copy of the order).

**Expected Limitation Result:** "Appeal" category, with `selected_article = "Article 115"` explicitly chosen (District/Subordinate Court appeal — the advocate must override the default, since Article 116 is auto-selected otherwise). Expiry = **2026-08-19** (exactly 30 days from the order date). `is_barred = False`. Days remaining = **13** (as of 2026-08-06).

> **TICKET-5, fixed 6 August 2026 — this scenario is now a regression check, run on the second affected article to confirm the fix is systematic.** Article 115 is coded as `"statutory_period_years": 0.0821` (`# 30 days`); before the fix, `int(0.0821 * 365)` = `int(29.9665)` = **29**, again one day short, producing an expiry of 2026-08-18 and 12 days remaining. Because a 30-day appeal window is inherently urgent, this was the highest-practical-stakes instance of the defect in the whole scenario set — the same `round()` fix that corrected APP-01 corrects this one too, and the same regression test file locks in both articles. **If this scenario produces 2026-08-18 / 12 days instead of 2026-08-19 / 13 days, that is a regression — Critical severity.**

**Expected Forum Result:** Not applicable in the ordinary sense; if run, "Civil Suit," nominal claim value matching the original order, Delhi.

**Expected Legal Issues:** Appeal under the applicable District Court/Subordinate Court appellate provision.

**Expected Evidence Gaps:** Memorandum of appeal not yet drafted (expected).

**Expected AI Case Analysis Outcomes:** Same pass-through check as APP-01, with higher real-world stakes given the shorter, more urgent window.

**Acceptance Criteria:**
- [ ] Confirm the advocate had to explicitly select Article 115 (the default without override is Article 116) — record whether this requirement was clear from the UI or a source of confusion
- [ ] Confirm computed expiry == 2026-08-19 (not 2026-08-18 — a regression of TICKET-5)
- [ ] Confirm days remaining == 13 (not 12)
- [ ] Confirms, alongside APP-01, that the TICKET-5 fix holds across both day-based Limitation Act articles the tool models, not just one

---

#### APP-03 — Time-barred commercial appeal, Maharashtra (barred + off-by-one + forum)

**Matter Description:** A party seeking to appeal a Commercial Court decree in Maharashtra has delayed nearly nine months past the decree date before consulting counsel.

**Parties:**
- Petitioner/Appellant #1: Trident Engineering Works Pvt. Ltd., Maharashtra
- Respondent #1: Coastal Marine Suppliers LLP, Maharashtra

**Facts:**
- 2025-11-01 — Commercial Court decree passed against the Appellant.
- 2026-07-15 — Appellant first consults counsel about a possible appeal.

**Evidence:** Exhibit P-1 (certified copy of the decree).

**Expected Limitation Result:** Article 116 (default), cause-of-action date = 2025-11-01. Expiry = **2026-01-30**. As of 2026-08-06, **`is_barred = True`**, barred by **188 days**. `condonation_required = True`.

> **TICKET-5, fixed 6 August 2026.** Before the fix, this scenario's expiry computed as 2026-01-29 (one day short) and barred-by 189 days instead of the correct 188 — the matter was already barred either way, which is why this scenario's main point (limitation bar + weak condonation prospects) doesn't hinge on the exact figure the way APP-01/APP-02 do, but the underlying arithmetic error was still present and is still worth confirming fixed here.

**Expected Forum Result:** "Commercial Dispute," claim value = original decretal amount (use ₹35,00,000), Maharashtra — `recommended_forum` should be the Maharashtra Commercial Court, per the TICKET-6 fix, if the Forum Advisor is run for the underlying matter.

**Expected Legal Issues:** Appeal from a Commercial Court decree, contingent on a Section 5 Limitation Act condonation application, similar in structure to CIV-04 but in an appellate rather than original-suit context (courts generally scrutinize delay in appeals at least as strictly as in suits, arguably more so given decrees carry a presumption of correctness pending appeal).

**Expected Evidence Gaps:** Should flag the absence of any documented reason for the nearly nine-month delay in seeking legal advice.

**Expected AI Case Analysis Outcomes:** Similar to CIV-04, this tests whether Potential Risks foregrounds the limitation bar and the weak condonation prospects given the length and undocumented nature of the delay, rather than proceeding as if the appeal is straightforwardly available.

**Acceptance Criteria:**
- [ ] `is_barred == True`
- [ ] Confirm computed expiry == 2026-01-30 (not 2026-01-29 — a regression of TICKET-5)
- [ ] `condonation_required == True`
- [ ] Potential Risks leads with the limitation bar and weak condonation prospects, similar to the standard set by CIV-04
- [ ] If the Forum Advisor is run for the underlying Commercial Dispute, confirm `recommended_forum` is the Commercial Court, not the general civil court (TICKET-6 regression check, same as COM-01)

### 3.7 Interim Applications

#### IA-01 — Interim injunction pending a possession suit, Delhi (AI-blindness to hearing/IA data)

**Matter Description:** In an ongoing suit for possession of a Delhi commercial property (the underlying matter), the plaintiff urgently needs an ad-interim injunction restraining the defendant from selling or further encumbering the property while the suit is pending, since credible information suggests the defendant is actively negotiating a sale to a third party.

**Parties:**
- Petitioner/Plaintiff #1: Devansh Properties Pvt. Ltd., Delhi
- Respondent/Defendant #1: Manoj Aggarwal, Delhi

**Facts:**
- 2025-03-01 — Underlying possession suit filed (assume already pending).
- 2026-07-20 — Credible information received that Defendant is negotiating a sale of the disputed property to a third party.
- 2026-07-25 — Application for ad-interim injunction (Order XXXIX Rules 1 & 2 CPC) filed.

**Hearing Docket entry (log this — this is the point of the scenario):** `hearing_date`: 2026-08-12, `ia_number`: "IA 234/2026", `purpose_of_hearing`: "Ad-interim injunction application — urgent listing," `status`: "Scheduled."

**Evidence:** Exhibit P-1 (information/evidence of the pending third-party sale negotiation, e.g., a broker listing or communication).

**Expected Limitation Result:** Use the underlying suit's basis — "Possession," Article 65, whatever cause-of-action date applies to the underlying suit (not directly relevant to the interim application itself, which does not have its own separate limitation period in the same sense).

**Expected Forum Result:** "Property Dispute," matching the underlying suit's forum, Delhi.

**Expected Legal Issues:** Ad-interim/interim injunction under Order XXXIX Rules 1 & 2 CPC restraining alienation of the suit property pending disposal; the underlying possession claim continues in parallel.

**Expected Evidence Gaps:** Should flag that the sale-negotiation evidence is not yet independently corroborated (e.g., no registered sale agreement or advance-payment receipt located, only informal information).

**Expected AI Case Analysis Outcomes — this is the headline finding for the entire Interim Applications category, verified directly from the code:** `case_analysis.py`'s `_facts_narrative()` function, which builds the text sent to the LLM, includes only the matter's title/court metadata, the parties, and the chronological facts — it **never reads or includes `litigation_hearings` data at all**. The hearing docket (including the IA number, its purpose, and its scheduled date) is fetched by `generate_case_analysis()` only to answer one deterministic yes/no question — "does at least one hearing exist?" — and is otherwise **completely invisible to the LLM and to every section of the AI Case Analysis.** In a matter where the single most urgent, time-sensitive fact is "there is an interim injunction application listed for hearing in N days," the tool's flagship output has no mechanism to surface that at all. Expect the Matter Summary, Potential Risks, and Recommended Next Steps to say nothing whatsoever about the pending IA or its hearing date — not because the LLM failed to reason about it, but because the data was never given to it in the first place.

**Acceptance Criteria:**
- [ ] Confirm (expected result: **fails**, and this failure should be logged as the expected/confirmed finding, not as a surprise) that nothing in the Matter Summary, Potential Risks, or Recommended Next Steps references the pending interim injunction application, its IA number, or its hearing date
- [ ] Confirm the hearing/IA entry is visible in the matter's own Hearing Docket tab in the UI (it should be — this is a UI-display check, separate from whether the AI Case Analysis uses it)
- [ ] Missing information correctly does NOT flag "no hearings logged" (since one is logged) — confirm this deterministic check at least behaves correctly even though the richer IA content is invisible to the LLM
- [ ] Log this as a category-wide architectural gap (not scenario-specific): the AI Case Analysis pipeline has no path from `litigation_hearings` into the LLM prompt, and this should be treated as a design consideration before pleading-generation work is built on top of the analysis step

---

#### IA-02 — Status quo application pending appeal, Bihar (hearing-blindness + state gap, compound)

**Matter Description:** A litigant who lost a possession suit in Bihar has filed a first appeal and, apprehending imminent dispossession by the successful party during the pendency of the appeal, urgently needs a status quo / stay of execution order.

**Parties:**
- Petitioner/Appellant #1: Ramavtar Mahto, Bihar
- Respondent #1: Basant Kumar Singh, Bihar

**Facts:**
- 2026-05-10 — District Court decree for possession passed against the Appellant.
- 2026-06-01 — First appeal filed.
- 2026-07-28 — Respondent initiates execution proceedings to take physical possession.

**Hearing Docket entry:** `hearing_date`: 2026-08-09, `ia_number`: "IA 88/2026", `purpose_of_hearing`: "Stay of execution / status quo application," `status`: "Scheduled."

**Evidence:** Exhibit P-1 (District Court decree), Exhibit P-2 (memorandum of appeal), Exhibit P-3 (execution proceeding notice).

**Expected Limitation Result:** Underlying appeal basis — "Appeal," Article 116, cause-of-action date = 2026-05-10 (decree date). Note the same off-by-one defect from APP-01/APP-02/APP-03 applies here too, though it is not the primary point of this scenario.

**Expected Forum Result:** "Property Dispute," Bihar — re-confirms the PROP-04 state-coverage gap in a live-application context rather than an original suit.

**Expected Legal Issues:** Application for stay of execution / status quo pending appeal (Order XLI Rule 5 CPC).

**Expected Evidence Gaps:** Should flag the extreme time-sensitivity of the situation relative to the imminent execution proceeding.

**Expected AI Case Analysis Outcomes:** Same category-wide finding as IA-01 — the scheduled stay-of-execution hearing on 2026-08-09, just three days from the acceptance-test run date, is invisible to the LLM entirely. This scenario is deliberately chosen with the hearing date extremely close to the present, so the practical cost of the blindness is maximally visible: an advocate glancing only at the AI Case Analysis, without separately checking the Hearing Docket tab, would have no idea from the analysis alone that anything time-critical is imminent.

**Acceptance Criteria:**
- [ ] Confirm (expected: fails, as the confirmed finding) that the imminent stay-of-execution hearing is not referenced anywhere in the AI Case Analysis text
- [ ] Confirm the Bihar state-coverage gap reproduces (generic DEFAULT-band forum result, no "verify state rules" indicator), consistent with PROP-04
- [ ] Confirm the off-by-one Article 116 defect reproduces if the Limitation Calculator is run for the underlying appeal
- [ ] Record this as reinforcing, not duplicating, the IA-01 finding — the point of running a second IA scenario is to confirm the gap is systemic across different underlying suit types (possession vs. appeal), not an artifact of one specific fact pattern

---

#### IA-03 — Attachment before judgment, Karnataka commercial matter (hearing-blindness + forum-ordering defect, combined)

**Matter Description:** In a pending commercial recovery suit, the plaintiff has learned the defendant company is rapidly selling off assets and moving funds offshore, apparently to defeat any eventual decree, and urgently seeks an order of attachment before judgment.

**Parties:**
- Petitioner/Plaintiff #1: Cascade Manufacturing Pvt. Ltd., Karnataka
- Respondent/Defendant #1: Orbit Components LLP, Karnataka

**Facts:**
- 2026-02-01 — Commercial recovery suit filed for ₹52,00,000 in unpaid supply invoices (assume already pending).
- 2026-07-15 — Credible reports emerge that Defendant is liquidating fixed assets and transferring funds to accounts outside India.
- 2026-07-30 — Application for attachment before judgment (Order XXXVIII Rule 5 CPC) filed.

**Hearing Docket entry:** `hearing_date`: 2026-08-14, `ia_number`: "IA 512/2026", `purpose_of_hearing`: "Attachment before judgment — urgent listing," `status`: "Scheduled."

**Evidence:** Exhibit P-1 (supply invoices forming the basis of the recovery claim), Exhibit P-2 (evidence of the asset liquidation / fund transfers, e.g., corporate filings or banking correspondence).

**Expected Limitation Result:** Underlying suit basis — "Breach of Contract" or "Money Recovery" depending on how the advocate frames the supply-invoice claim; not the focus of this scenario.

**Expected Forum Result:** "Commercial Dispute," claim value ₹52,00,000, Karnataka. `recommended_forum` should be the Karnataka Commercial Court — this scenario confirms the TICKET-6 fix in a third state, combined with an urgent interim application, in the same run as the still-open IA-blindness gap (TICKET-8).

**Expected Legal Issues:** Application for attachment before judgment to secure the eventual decree against dissipation of assets; underlying claim for recovery of unpaid invoices.

**Expected Evidence Gaps:** Should flag that the asset-dissipation evidence, while credible, is not yet independently verified through formal discovery or a forensic asset trace.

**Expected AI Case Analysis Outcomes:** Same category-wide hearing-blindness finding as IA-01/IA-02 — expect nothing about the urgent attachment application to appear in the narrative sections. The Jurisdiction Summary, separately, should now correctly show the Karnataka Commercial Court as recommended (TICKET-6 fix).

**Acceptance Criteria:**
- [ ] Confirm (expected: fails, and this is the confirmed open finding — TICKET-8) that the urgent attachment application is not referenced anywhere in the AI Case Analysis text
- [ ] `recommended_forum` == Karnataka Commercial Court — this is the third and final confirmation, across three states (Delhi in COM-01, Maharashtra in COM-02, Karnataka here), that the TICKET-6 fix is state-independent; a general-civil-court recommendation here would be a regression
- [ ] Missing information does not incorrectly flag "no hearings logged" (one is present) — same deterministic-check sanity confirmation as IA-01

## 4. Where this guide expects the system to expose weaknesses

This section consolidates §3's per-scenario flags into one place, organized by the six categories named in the task brief, so a reader can go straight to "what's likely wrong with fact extraction" without reading all 26 scenarios end to end. Every claim below was verified by hand-tracing the actual implementation during this guide's authoring, not inferred from behavior alone — file paths and line-level logic are cited so a developer can go straight to the fix.

### 4.1 Fact extraction

**Primary scenarios:** RERA-03 (similar/shared surnames across multiple parties), CIV-05 (extremely sparse, vague single-fact input), CONT-01 (a fact whose date is ambiguous between two legally distinct meanings — breach vs. discovery).

The known risk here is less about the retrieval pipeline and more about the PII masking layer (`pii_mask.py`) that runs before every prompt: its person-name detection is a heuristic (Title-Case run detection filtered by spaCy), and RERA-03 is specifically designed to test whether four similarly-named parties survive the mask → LLM → unmask round-trip as four distinct people rather than collapsing or cross-contaminating.

### 4.2 Chronology

**Primary scenarios:** PROP-02 (facts deliberately entered out of temporal order to test the sort), IA-01/IA-02/IA-03 (hearing-docket dates entirely excluded from the chronology the AI ever sees).

The chronological sort itself (`case_analysis.py::_chronological_facts`, via `_sort_key`) is a simple, low-risk deterministic operation — undated facts sort last, dated facts sort by `event_date` — and should not fail under normal conditions. The real chronology risk is the **scope gap**: the "chronology" the AI reasons over is facts-only and silently excludes hearing dates, which is a substantive omission for any matter with a live procedural timeline, not a sorting bug.

### 4.3 Limitation

**Primary scenarios:** APP-01, APP-02, APP-03 (a precisely verified, code-level off-by-one-day defect); CIV-01, PROP-02 (default article auto-selection may not match the legally precise article without an explicit override); CIV-04, APP-03 (the generic `condonation_notes` template does not scale its framing to delay length); CONT-01, CONT-03 (the tool has no way to validate that the advocate entered the legally correct trigger date, only that the arithmetic from whatever date is entered is internally consistent); CIV-03, PROP-04, RERA-01, RERA-02, RERA-03 (fact patterns — injunctions, easements, RERA §18 delay claims, RERA §14(3) defect-liability claims — with no correct representation at all among the tool's seven fixed Suit Category options).

**The single highest-confidence, most actionable finding in this guide — fixed 6 August 2026, before the first validation round (TICKET-5).** `limitation.py`'s `LIMITATION_ARTICLES["Appeal"]` entries encode Article 116 as `0.2465` years and Article 115 as `0.0821` years, both annotated `# 90 days` / `# 30 days` respectively. `calculate_limitation()`'s day-based branch computed `int(years * 365)`, which evaluated to `89` and `29` — one day short of the correct statutory period in both cases, because truncation via `int()` always rounds down and the stored fractions were not chosen to round to the exact intended day count. This affected every appeal-limitation calculation the tool produced. The fix changes the truncating `int()` to `round()`; APP-01 and APP-02 now serve as regression checks for the fix rather than live-bug demonstrations, and both are locked in with dedicated tests in `api/tests/test_limitation.py`.

### 4.4 Forum determination

**Fixed before the first validation round (TICKET-6):** COM-01, COM-02, COM-03, and IA-03 originally exposed a recommendation-ordering defect — for any Commercial Dispute meeting the ≥₹3,00,000 Commercial Courts Act threshold, `forum.py`'s `determine_forum()` computed the Commercial Court option first but then unconditionally inserted the general civil-court option at index 0 of `viable_options` for any suit type other than RERA/Real Estate, so `recommended_forum`, which is simply `viable_options[0]`, always returned the general civil court, never the Commercial Court, even when Commercial Court designation was the legally apt answer. The fix makes the Commercial Dispute branch append the civil option after the Commercial Court option, mirroring the pattern the RERA branch already used correctly, rather than displacing it; confirmed across three states (Delhi, Maharashtra, Karnataka) and locked in with a dedicated regression test in `api/tests/test_forum.py`. These four scenarios now function as regression checks for the fix rather than live-bug demonstrations.

**Still open:** PROP-01, RERA-02 (Uttar Pradesh — one of exactly three states named as in-scope in `CLAUDE.md` Decision 2 — has no entry in `STATE_PECUNIARY_LIMITS`, so it silently falls through to the generic `DEFAULT` band with no distinguishing indicator; tracked as TICKET-7); PROP-04, IA-02 (Bihar, a non-Phase-1 state, produces the same silent generic fallback, and `CLAUDE.md` Decision 2's own stated policy — that out-of-scope states should "fall back to Central law plus a verify state rules flag" — has no corresponding field anywhere in `ForumAdvisorResponse`, so the "flag" part of that policy does not appear to be implemented at all; also TICKET-7). COM-03 additionally serves, as before, as a positive control for the cross-state ambiguity-handling logic specifically (Karnataka is present in the state table, and the Section 20(a)/20(c) CPC branch behaves correctly independent of the ordering fix). RERA-01, RERA-03 remain useful positive controls: the RERA branch's option-ordering was always correct, and is in fact the pattern the TICKET-6 fix generalized to the Commercial Dispute branch.

### 4.5 Citation grounding

**Primary scenarios:** PROP-03 (specific performance — an area with substantial, well-known, independently checkable Indian precedent), CONT-02 (Section 27 restraint-of-trade — similarly well-trodden, real case law exists).

Neither scenario is expected to expose a code-level defect the way the Limitation/Forum findings above do — the Citation Verifier's design (verify every proposed case name against Indian Kanoon before it can render as anything but "unverified," per [ADR-005](../ADR/ADR-005-zero-hallucination-citation-gate.md)) is sound in principle. These two scenarios exist to test it empirically: does `status: "verified"` actually correspond to a real, correct match when a genuinely well-known case is at stake, and — just as importantly — does the model refrain from proposing a citation at all in scenarios (most of the other 24) where no confident, checkable case name is actually warranted? A pattern of the model proposing plausible-sounding but unverifiable names across many scenarios, even correctly labeled "unverified," would itself be worth recording as a quality signal (a model that names cases it can't stand behind is a weaker foundation than one that says nothing), separate from whether the labeling mechanism itself is technically working.

### 4.6 AI synthesis

**Primary scenarios:** COM-04 (does the model correctly separate two related but legally distinct causes of action from one dense fact pattern, without either flattening them into one or overreaching into an unsupported fraud finding); CONT-02, CONT-03 (does the model apply well-settled substantive doctrine — Section 27 and Section 74 Indian Contract Act — rather than asserting a conclusion without legal reasoning); CIV-05 (does the model resist fabricating specificity — dates, amounts, party details — that were never actually provided, when given almost nothing to work with); IA-01, IA-02, IA-03 (does the model's overall output feel trustworthy and complete to an advocate glancing only at the AI Case Analysis, given that it is provably blind to hearing/IA data — this is as much a UX-trust question as a pure synthesis-quality question).

## 5. Overall acceptance gate for this validation round

Record a single rollup verdict (see the [Product Validation Report Template](Product_Validation_Report_Template.md) §D) answering: **is the AI Case Analysis vertical slice trustworthy enough, as currently built, to serve as the foundation pleading generation is built on top of** ([ADR-011](../ADR/ADR-011-ai-case-analysis-before-pleading.md))?

A reasonable bar, consistent with the project's existing Phase 2 gate ("100 generated citations audited, target zero fabricated citations reaching the user" — `00_Product/Roadmap.md`) and this guide's own findings:

- **Zero tolerance:** any scenario where a fabricated fact, statute, or citation is presented as confirmed/verified without actually being grounded. This is a hard blocker on proceeding to pleading generation regardless of how well everything else scores.
- **Fixed before this round (verify via regression, don't re-diagnose):** the Article 116/115 off-by-one-day defect (§4.3, TICKET-5) and the forum-ordering defect for Commercial Disputes (§4.4, TICKET-6) were both found and fixed on 6 August 2026, before any human validation round ran, and are locked in with dedicated regression tests (`test_limitation_appeal_article_116_ninety_days_exact`, `test_limitation_appeal_article_115_thirty_days_exact`, `test_forum_commercial_courts_act_recommends_commercial_court_not_general_civil`). APP-01/APP-02/APP-03 and COM-01/COM-02/COM-03/IA-03 now serve as scenario-level confirmations that the fix holds in realistic fact patterns, not just the unit-test cases — if any of them reproduces the original wrong number or wrong recommendation, that is a **regression**, and should be treated as Critical severity, not filed as "confirms the known issue."
- **Document-and-proceed-with-caution:** the state-coverage gaps (UP, Bihar, and any other non-Delhi/Maharashtra/Karnataka state — TICKET-7), the category-fit gaps (injunctions, easements, RERA-specific claims), and the hearing/IA-data blindness (TICKET-8) are real limitations worth fixing eventually, but do not necessarily block starting pleading-generation work on the categories that *are* well-covered (the canary scenarios' categories), provided the advocate is clearly informed of the boundary.
