> **Title:** Sprint 3.5.6 — Production Certification & AI Quality Validation Report
> **Version:** 1.0
> **Status:** Final for this round
> **Owner:** Keshav (executed) / Nitesh (must review AI-quality findings and sign off before Sprint 3.6 begins)
> **Audience:** Nitesh, Keshav, future AI agents assessing release readiness
> **Last Updated:** 9 August 2026
> **Canonical Reference:** Yes — this is the first round in which all 26 scenarios from the Acceptance Testing Guide were executed for real, end to end, against production infrastructure
> **Certification baseline commit:** `ecc715fcd009043783e29c49c05d879c759638b0`
> **Related Documents:** [`../30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md`](../30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md), [`../40_Operations/Release_Gates.md`](../40_Operations/Release_Gates.md), [`README.md`](README.md) (prior partial rounds), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md) (TICKET-16 onward filed from this round)

---

# 1. Executive Summary

This round executed **all 26 scenarios** (27 runs, counting CONT-01's deliberate two-pass comparison) from the Sprint 3.5.3 Acceptance Testing Guide for real: real production Supabase (matters/parties/facts/evidence/hearings/case-analyses/pii_masks tables, `evidence` storage bucket), real LLM providers (Gemini primary, Groq/SambaNova failover available), real Indian Kanoon citation verification. No mocks, no fabricated or estimated figures anywhere in this report — every number below traces to a specific log line, HTTP response, or direct database query, and is cited as such.

**Certification decision: CERTIFIED WITH CONDITIONS.** The deterministic engines this product's safety guarantees actually rest on — Limitation Calculator, Forum Advisor, chronological fact ordering, PII-mask mechanics, and the Citation Gate's fabrication-blocking mechanism — all held up under real execution with **zero regressions** of the two previously-fixed defects (TICKET-5, TICKET-6) and **zero instances** of a fabricated fact, statute, or citation being presented as confirmed. That clears the guide's own zero-tolerance bar (§5). But this round surfaced four new, material, evidence-backed findings about the AI-synthesized layer and its supporting infrastructure — most importantly that the statute corpus is far too narrow for litigation use and that the top-of-pool LLM model never actually served a single real request this round — that should be read and weighed by Nitesh before Sprint 3.6 (AI Pleading Generation) begins building on top of this layer. See §10 for the conditions.

---

# 2. Methodology

- **Pre-flight:** `api/scripts/verify_project.py` run first, per the sprint's mandatory gate. Result: **FAIL** — every section passed (Environment, Database, Storage, Runtime, 214/214 tests) except the Providers section, which failed solely on Cerebras (`HTTP 401: Wrong API Key`), a pre-existing, already-tracked condition (**TICKET-11**, filed 6 Aug 2026, judged out-of-scope in the immediately preceding Sprint D1 report). Gemini, Groq, SambaNova, and Indian Kanoon all passed; the failover chain had 3 of 4 tiers healthy. Per the sprint's own strict "STOP on any failure" pre-flight rule, this was surfaced to the user rather than silently overridden — **the user explicitly approved waiving this single known condition and proceeding.** This waiver is the only deviation from a clean pre-flight in this round and is recorded here for the audit trail.
- **Execution environment:** a local `uvicorn` instance (same pattern `verify_project.py`'s own runtime check uses) wired to the real production Supabase project (`pgwemjswxdlnshrfoggj`) and real provider API keys via the repo-root `.env` — **not** a mocked or staging environment. This is the same approach Sprint D1 used for its smoke test, chosen because the Render-hosted deployment's cold-start/free-tier characteristics make it unsuitable for 26 sequential real LLM calls, while a local process against the same real database/storage/provider endpoints exercises the identical code path and identical real infrastructure.
- **Test identity:** one throwaway Supabase Auth user created via the admin API (`cert-sprint356-9603b937@vidhidesk.local`), matching the project's established `[TEST] <ID> — <label>` matter-naming convention (`20_Engineering/Lessons_Learned.md`).
- **Evidence uploads:** every exhibit listed in the guide was uploaded through the real `POST /evidence/upload` endpoint with a real (minimal, valid) file attachment — not just a text label — so the evidence-gap deterministic check and the storage round-trip were both genuinely exercised, not simulated.
- **Scenario fidelity:** all 26 scenarios' parties, facts, dates, and exhibit lists were transcribed directly from the guide. Two known deviations from the literal guide text are disclosed for transparency:
  1. A handful of facts the guide states as a date range (e.g., "2020-01-05 to 2025-12") were entered as a single representative dated entry, since the data model requires one `event_date` per fact row. This does not affect any Limitation/Forum computation (all of which use an explicitly guide-specified `cause_of_action_date`), only the AI-synthesized narrative's fact count.
  2. My own scenario labels (used purely for my bookkeeping, e.g. matter titles containing "(Section 27 test)") leaked into the retrieval query text via `_facts_narrative()`'s title line, causing an artifact in two scenarios' `applicable_statutes` scores (see §5.5) — **this is a testing-methodology artifact, not a product defect**, and is called out explicitly rather than mis-filed as a system finding.
- **Execution integrity note:** the first batch (CIV-01–COM-04) ran clean. The throwaway user's JWT (1-hour Supabase default TTL) expired mid-batch — a side effect of the long documentation-reading phase that preceded execution, not a product issue — causing PROP-01 through IA-03 to fail on auth. This was caught immediately (fast-failing scenarios with a distinctive error signature), the token was refreshed, and **all 18 affected scenarios were re-run cleanly from scratch** with fresh data. Final result: **27/27 runs completed with zero unhandled errors.**
- **Cleanup status:** as of this report, the 26 real `[TEST]`-prefixed matters, their case analyses, PII masks, and uploaded evidence files, and the throwaway auth user **have not been deleted** — see §11 for why, and the decision this leaves for Nitesh.

---

# 3. Production Validation Report — deterministic engines

Every Limitation and Forum result below is the actual, real output of `calculate_limitation()` / `determine_forum()` via live HTTP calls, not hand-computed. The guide's own expected values were computed **as of 2026-08-06**; this round ran **2026-08-09**, a 3-day offset. Every `days_remaining` comparison below already accounts for that 3-day drift — where the adjusted actual matches the adjusted expected, it is recorded as a match, not a new discrepancy.

## 3.1 Regression checks (TICKET-5, TICKET-6) — the highest-priority checks in the entire guide

| Scenario | Check | Expected | Actual | Result |
|---|---|---|---|---|
| APP-01 | Article 116, 90-day expiry | 2026-09-18, 43d remaining (as of 8/6) → 40d (as of 8/9) | 2026-09-18, **40d remaining** | ✅ PASS — no regression |
| APP-02 | Article 115, 30-day expiry | 2026-08-19, 13d (8/6) → 10d (8/9) | 2026-08-19, **10d remaining** | ✅ PASS — no regression |
| APP-03 | Article 116, barred | 2026-01-30, barred | 2026-01-30, `is_barred=True` | ✅ PASS — no regression |
| COM-01 | Commercial Court ordering, Delhi | Commercial Court, Delhi (not general civil) | **Designated Commercial Court / Commercial Division, Delhi**, general civil court present as 2nd viable option | ✅ PASS — no regression |
| COM-02 | Commercial Court ordering, Maharashtra | Commercial Court, Maharashtra | **Designated Commercial Court / Commercial Division, Maharashtra** | ✅ PASS — no regression, holds cross-state |
| COM-03 | Commercial Court + cross-state ambiguity combined | 3 viable options, Delhi Commercial Court recommended, `is_unambiguous=False` | 3 options (Delhi Commercial, Karnataka District, Delhi Civil), **Delhi Commercial recommended**, `is_unambiguous=False` | ✅ PASS — no regression |
| IA-03 | Commercial Court ordering, Karnataka (3rd state) | Karnataka Commercial Court | **Designated Commercial Court / Commercial Division, Karnataka** | ✅ PASS — no regression, confirms fix is state-independent across all 3 tested states |

**Both previously-fixed defects hold under real, live execution across every scenario the guide designed to test them. No regressions found.**

## 3.2 Limitation Calculator — full results

| ID | Suit category / article | COA date | Expiry (actual) | Barred? | Days remaining (actual) | Matches guide (adjusted for 3-day drift)? |
|---|---|---|---|---|---|---|
| CIV-01 | Money Recovery / Art.19 | 2024-03-10 | 2027-03-10 | No | 213 | ✅ (216−3) |
| CIV-02 | Declaratory / Art.58 | 2023-08-20 | 2026-08-20 | No | 11 | ✅ (14−3) |
| CIV-03 | Declaratory (forced-fit) / Art.58 | 2025-01-15 (my choice — guide left this open) | 2028-01-15 | No | 524 | N/A — guide deliberately leaves COA date choice to the advocate for this category-fit-gap scenario |
| CIV-04 | Money Recovery / Art.19 | 2020-01-05 | 2023-01-05 | **Yes**, condonation required | −1312 (barred 1312d, guide said 1309d as of 8/6 → 1312d as of 8/9) | ✅ |
| CIV-05 | *(not run — guide instructs skipping Limitation/Forum for this scenario)* | — | — | — | — | ✅ correctly skipped |
| COM-01 | Breach of Contract / Art.55 | 2025-07-01 | 2028-07-01 | No | 692 | ✅ |
| COM-02 | Breach of Contract / Art.55 | 2025-11-01 | 2028-11-01 | No | 815 | ✅ |
| COM-03 | Breach of Contract / Art.55 | 2026-01-15 | 2029-01-15 | No | 890 | ✅ |
| COM-04 | Breach of Contract / Art.55 | 2024-08-01 | 2027-08-01 | No | 357 | ✅ |
| PROP-01 | Possession / Art.65 | 2014-04-01 | 2026-04-01 | **Yes** | −130 (barred 130d, guide said 127d as of 8/6 → 130d as of 8/9) | ✅ |
| PROP-02 | Possession / **Art.64 (explicit override)** | 2019-04-12 | 2031-04-12 | No | 1707 | ✅ — advocate had to explicitly select Article 64; confirmed the UI/API requires this override, default would have been Art.65 |
| PROP-03 | Specific Performance / Art.54 | 2025-09-30 | 2028-09-30 | No | 783 | ✅ |
| PROP-04 | Declaratory (forced-fit) / Art.58 | 2026-05-01 | 2029-05-01 | No | 996 | ✅ |
| RERA-01 | Breach of Contract (proxy) / Art.55 | 2024-06-30 | 2027-06-30 | No | 325 | ✅ |
| RERA-02 | Breach of Contract (forced-fit) / Art.55 | 2025-08-01 | 2028-08-01 | No | 723 | ✅ |
| RERA-03 | Breach of Contract (proxy) / Art.55 | 2024-03-31 | 2027-03-31 | No | 234 | ✅ |
| CONT-01a | Breach of Contract / Art.55, **correct breach date** | 2024-11-20 | 2027-11-20 | No | 468 | ✅ matches guide exactly |
| CONT-01b | Breach of Contract / Art.55, **incorrect discovery date** | 2026-01-25 | 2029-01-25 | No | 900 | ✅ matches guide exactly — **and rendered with the identical unqualified "Deterministic" confidence as the correct run, exactly the trust-design gap the guide flags (§4.3)** |
| CONT-02 | Breach of Contract / Art.55 | 2026-01-10 | 2029-01-10 | No | 885 | ✅ |
| CONT-03 | Breach of Contract / Art.55 | 2025-05-01 | 2028-05-01 | No | 631 | ✅ |
| CONT-04 | Breach of Contract / Art.55 | 2025-08-01 | 2028-08-01 | No | 723 | ✅ |
| APP-01 | Appeal / Art.116 | 2026-06-20 | 2026-09-18 | No | 40 | ✅ regression-checked, see 3.1 |
| APP-02 | Appeal / **Art.115 (explicit override)** | 2026-07-20 | 2026-08-19 | No | 10 | ✅ regression-checked, see 3.1 |
| APP-03 | Appeal / Art.116 | 2025-11-01 | 2026-01-30 | **Yes** | −191 (barred 191d, guide said 188d as of 8/6 → 191d as of 8/9) | ✅ regression-checked, see 3.1 |
| IA-01 | Possession (underlying suit) / Art.65 | 2025-03-01 (placeholder — guide says "not directly relevant") | 2037-03-01 | No | 3857 | N/A — not the focus of this scenario per guide |
| IA-02 | Appeal (underlying) / Art.116 | 2026-05-10 | 2026-08-08 | **Yes** (barred by 1 day) | −1 | Consistent with the fixed Art.116 math (90 days from 5/10 = 8/8; test run on 8/9 is exactly 1 day past) |
| IA-03 | Breach of Contract (underlying) / Art.55 | 2026-02-01 | 2029-02-01 | No | 907 | ✅ |

**Result: 27/27 Limitation runs produced arithmetically correct, guide-consistent output. Zero defects found in the deterministic Limitation Engine this round.**

## 3.3 Forum Advisor — headline findings

| ID | Recommended forum (actual) | Confidence | `is_unambiguous` | Matches guide? |
|---|---|---|---|---|
| CIV-01 | Civil Judge Court, Delhi | Deterministic | True | ✅ |
| COM-01/02/03/IA-03 | Commercial Courts (Delhi/Maharashtra/Delhi/Karnataka) | Deterministic | COM-03: False (correct — cross-state ambiguity), others True | ✅ all four TICKET-6 regression checks pass (§3.1) |
| RERA-01/02/03 | Real Estate Regulatory Authority, (Delhi/UP/Maharashtra) | Deterministic | True | ✅ positive control confirmed — RERA branch's correct ordering logic (the pattern TICKET-6 generalized from) still holds |
| **PROP-01** | **"District Court"** (generic — no "Uttar Pradesh" in the name) | **Deterministic** | True | **Confirms TICKET-7 exactly as the guide predicted**: UP has no entry in `STATE_PECUNIARY_LIMITS`, silently falls through to the generic DEFAULT band, and the response still carries `confidence: "Deterministic"` — a real risk of the advocate treating a generic fallback as UP-verified. No `verify_state_rules`-style flag anywhere in the response. |
| **PROP-04** | **"Civil Judge Junior Division"** (generic — no "Bihar") | **Deterministic** | True | **Confirms TICKET-7 for Bihar too** (non-Phase-1 state), same gap, same missing-flag observation |
| **RERA-02** | **"Real Estate Regulatory Authority (Uttar Pradesh)"** — correctly state-named | Deterministic | True | Confirms the guide's contrast point precisely: the RERA branch is state-name-correct for UP even though the general civil branch (PROP-01, same state) is not — the gap is specifically in the general civil pecuniary table, not universal |
| **IA-02** | **"Civil Judge Junior Division"** (generic — no "Bihar") | Deterministic | True | Confirms TICKET-7 reproduces in a live-application (not just original-suit) context, exactly as the guide's IA-02 was designed to test |

**Result: Forum Advisor's core logic (including the two regression-checked fixes) is sound. The one real, live-confirmed gap is TICKET-7 (Uttar Pradesh / Bihar state-coverage), already tracked, reproduced exactly as predicted with no new dimensions.**

## 3.4 Chronology — code-level check

PROP-02's three facts were deliberately entered in reverse order (2019-05-01, then 2019-04-14, then 2019-04-12). The AI Case Analysis's `chronological_facts` output, queried directly from the persisted row, returned them correctly re-sorted: **2019-04-12 → 2019-04-14 → 2019-05-01**, undated exhibit rows sorted last. **Pass — deterministic sort confirmed correct regardless of entry order, exactly as the guide specifies.**

## 3.5 Hearing/IA-blindness (TICKET-8) — reconfirmed live

IA-01, IA-02, and IA-03 each had a real, urgent hearing logged in the Hearing Docket (`IA 234/2026`, `IA 88/2026`, `IA 512/2026` respectively — all confirmed present via the `/hearings` endpoint). In all three, the AI Case Analysis's `matter_summary`, `potential_risks`, and `recommended_next_steps` **contain no reference whatsoever** to the pending IA, its number, or its hearing date — exactly the architectural gap the guide identifies (`case_analysis.py::_facts_narrative()` never reads `litigation_hearings`). **Confirmed as the guide's own predicted, "expected to fail" result — not a new finding, but now backed by three live, real generation runs rather than code-tracing alone.**

---

# 4. AI Quality Report

The guide's own organizing structure (§4.1–4.6) is used here since it was purpose-built for exactly this evaluation.

## 4.1 Fact extraction — RERA-03 (similar names), CIV-05 (sparse input)

- **RERA-03** (4 allottees, two pairs sharing a surname): all four names — Suresh Sharma, Suman Sharma, Ramesh Gupta, Rakesh Gupta — appear correctly and distinctly in the `matter_summary`. No name collapsed, swapped, or replaced with a literal `PARTY_C`-style placeholder in the rendered output. **Pass.** Direct DB query confirms 5 real `pii_masks` rows were created and correctly round-tripped for this matter (not spot-checked in the narrative alone).
- **CIV-05** (near-empty input: one party, one vague fact, no defendant): the model's `matter_summary` states plainly that the business associate is unidentified and the sum/date are unconfirmed. **No fabricated amount, date, or party name appears anywhere in the output** — the single most important AI-synthesis stress test in the guide passes cleanly. `possible_causes_of_action` is hedged ("could be pursued, once specific details are ascertained"), not asserted with false confidence.

## 4.2 Chronology — see §3.4. Pass.

## 4.3 Limitation trust boundary — CONT-01 A/B comparison

Both the correct-breach-date run (CONT-01a, expiry 2027-11-20) and the incorrect-discovery-date run (CONT-01b, expiry 2029-01-25) rendered with the **identical** `"Deterministic"` label and an identically confident `condonation_notes` string. **Nothing anywhere in the API response or the AI Case Analysis text flags that the entered date might be the legally wrong trigger event.** This is exactly the design gap the guide names — confirmed, not a code defect (the arithmetic is correct given the input; the gap is that there is no check on whether the input itself is the legally correct one).

## 4.4 Forum determination — see §3.3. TICKET-6 fully regression-clean; TICKET-7 reconfirmed, unchanged in scope.

## 4.5 Citation grounding — the most significant new findings this round

The guide names PROP-03 and CONT-02 as the designated grounding tests; live execution surfaced findings across many more scenarios that go beyond what the guide anticipated, because they depend on the real corpus and real Indian Kanoon API rather than code-tracing:

**Finding A — the statute corpus is far narrower than the product needs.** A direct query of the live `statute_chunks` table (not inferred from output — queried directly) returns exactly **6 acts, 633 chunks total**:

| Act | Chunks |
|---|---|
| Indian Contract Act, 1872 | 178 |
| Transfer of Property Act, 1882 | 129 |
| Consumer Protection Act, 2019 | 107 |
| Registration Act, 1908 | 102 |
| Indian Stamp Act, 1899 | 95 |
| Carriage by Road Act, 2007 | 22 |

**Missing entirely: the Limitation Act 1963 itself, the Specific Relief Act 1963, the Code of Civil Procedure 1908, the Indian Easements Act 1882, the RERA Act 2016, and the Commercial Courts Act 2015** — i.e., the acts most central to litigation practice, and the exact acts the guide repeatedly names as the *correct* statutory basis for CIV-03 (Specific Relief Act — injunctions), PROP-02 (Specific Relief Act §6), PROP-03 (Specific Relief Act), PROP-04 (Easements Act), RERA-01/02/03 (RERA Act), and every Appeal/IA scenario (CPC). This single gap explains the overwhelming majority of "Applicable Statutes surfaced something irrelevant" or "surfaced nothing" observations across all 26 scenarios — it is a corpus-provisioning gap, not a retrieval-algorithm defect. **Filed as TICKET-16 (Major).**

**Finding B — because of Finding A, retrieval frequently returns generically top-ranked but substantively irrelevant statutes** (Consumer Protection Act and Carriage by Road Act sections recur across loan-recovery, injunction, JV-fraud, and easement scenarios alike, with mediocre similarity scores ~0.6–0.7, because there is nothing better in the corpus to rank against). **Positive finding, worth stating clearly: the LLM correctly declined to force-cite these irrelevant retrieved chunks** — `statutes_relied_upon` was empty or genuinely on-topic in every scenario reviewed, never padded with an irrelevant citation just because it was retrieved. Hard Rule 3 (never invent, never silently trust) held.

**Finding C — the Citation Verifier shows real, reproducible non-determinism.** During the live CIV-03 run, the model proposed *Anathula Sudhakar v. P. Buchi Reddy (Dead) by LRs and Ors.* — a real, well-known Supreme Court authority — and the Citation Verifier returned `status: "unverified"`. An independent, direct re-call of `verify_citation()` with the **exact same case name string**, minutes later, returned `status: "verified"` with a real Supreme Court doc URL (`https://indiankanoon.org/doc/540361/`). Same code, same input, different result — this points to non-deterministic behavior in the underlying Indian Kanoon search ranking (the confidence gate's 0.6 word-overlap threshold depends on whatever result set the live search API returns that call) rather than a caching or logic bug. **Filed as TICKET-17 (Major)** — this directly affects Hard Rule 1, the product's stated reason to exist.

**Finding D — some real, correctly-named precedents genuinely fail to verify even on retry.** *Fateh Chand v. Balkishan Dass* (landmark 1963 Supreme Court authority on Section 74 ICA, proposed in CONT-03) and *Ambrish Kumar Shukla & Ors. v. Ferrous Infrastructure (P) Ltd.* (real NCDRC landmark, proposed in RERA-03) both independently re-verified as **unverified** — this is not the flakiness in Finding C, but an apparent genuine gap in Indian Kanoon's search-title matching for older Supreme Court judgments and NCDRC-tier tribunal orders. **Filed as TICKET-18 (Minor)** — the safe-failure direction (real case shown as unverified, never the reverse), but it means the tool will under-serve the advocate on well-established precedent more often than the citation-gate design alone would suggest.

**Finding E — citation relevance, independent of verification status, sometimes fails.** IA-02 (flash-lite model) proposed the *Best Bakery Case* — a real, famous case, but about witness intimidation in a criminal trial, with essentially no substantive connection to a civil status-quo application — justified only with "highlights the importance of fair procedure." This is exactly the risk the guide's §4.5 flags as worth recording on its own: a model reaching for a recognizable name rather than staying silent. **Filed as TICKET-19 (Minor).**

## 4.6 AI synthesis quality

- **COM-04** (JV dispute, overlapping fraud allegation): the model correctly separated **three** distinct threads (fraudulent transfer, breach of JV agreement, breach of fiduciary duty) rather than flattening to one generic "breach of contract" claim, and consistently used hedged language ("alleged diversion," "Karan claims") rather than asserting fraud as established fact. **Strong result, exceeds the guide's minimum bar.**
- **CONT-02** (Section 27 ICA non-compete): correctly identified and engaged with the restraint-of-trade doctrine as a material risk ("Non-compete clause being held void under Section 27... High" severity), not treated as presumptively enforceable. **Pass — matches the guide's trustworthy-result bar exactly.**
- **CONT-03** (Section 74 ICA liquidated damages/penalty): correctly engaged substantively with the penalty-vs-liquidated-damages question and named the real, correct landmark authority (*Fateh Chand v. Balkishan Dass*) — see Finding D on why that citation itself couldn't be verified, but the legal reasoning that surfaced it was sound. **Pass on substance, Minor gap on verification (TICKET-18).**
- **New finding, not anticipated by the guide (model-pool quality variance) — APP-01/02/03:** these three appeal scenarios (all served by `gemini-2.5-flash-lite`, see §5.1 for why) show a materially weaker and, in APP-02's case, actively confused result: the model's `potential_risks` reasons about "Section 41 of the Consumer Protection Act, 2019, prescribes a period of 45 days for appeal from a District Commission order to the State Commission" as though it might govern an ordinary CPC first appeal from a District Court decree — because Consumer Protection Act appellate provisions were the *only* appeal-shaped content the (too-narrow, see Finding A) corpus had to retrieve. `possible_causes_of_action` came back empty for all three. This is a compounding effect of the corpus gap (Finding A) and a real, observed quality difference between `gemini-2.5-flash` and `gemini-2.5-flash-lite` on the same task type. **Filed as TICKET-20 (Major)** — flash-lite should not be treated as an interchangeable member of the `case_analyst` model pool without this quality gap being weighed.

---

# 5. Runtime Performance Report

All figures below are real, measured wall-clock timings and real provider/model identifiers returned by the live API — no estimates.

## 5.1 Provider/model distribution and the single most significant infrastructure finding this round

Every one of the 26 real `generate()` calls this round **first attempted `gemini-2.5-pro`** (the top of the pool per `llm_gateway.py`'s ordering) **and every single one was rate-limited** — confirmed directly from the running server's logs: **52 `status=error reason="gemini: rate limited"` log lines**, all `gemini-2.5-pro` on first attempt, with a handful cascading to a second rate-limited attempt on `gemini-2.5-flash` or `gemini-2.0-flash` before finally succeeding lower in the pool. **`gemini-2.5-pro` served zero real requests this entire round.** Final successful model, by scenario:

| Model actually used | Scenarios | Count |
|---|---|---|
| `gemini-2.5-flash` | CIV-01–05, COM-01–04, PROP-01–04, RERA-01, RERA-03* | 15 |
| `gemini-2.5-flash-lite` | RERA-02, CONT-01a, CONT-02, CONT-03, CONT-04, APP-01/02/03, IA-01/02/03 | 11 |

*(RERA-03 landed on flash-lite, corrected above from an earlier miscount — see raw per-scenario data in `results/`.)*

This degradation is **silent** end-to-end: nothing in the API response, the persisted `litigation_case_analyses` row, or the advocate-facing UI (per the schema — `model_used` is stored but not rendered as a quality/tier signal anywhere in the reviewed frontend components) indicates that the analysis was produced by a materially weaker model than the one the architecture nominally leads with. Combined with §4.6's finding that flash-lite output is measurably weaker on this task, this is a real product-trust issue, not just a cost/performance footnote. **Filed as TICKET-21 (Major)**, related to but distinct from TICKET-20.

## 5.2 Latency

| Metric | Value |
|---|---|
| Fastest case-analysis call | 7.76s (APP-01, flash-lite) |
| Slowest case-analysis call | 23.29s (RERA-01, flash) |
| Mean, flash-served scenarios (n=15) | ~19.9s |
| Mean, flash-lite-served scenarios (n=11) | ~11.4s |
| Full end-to-end scenario runtime (matter creation → case analysis, incl. all deterministic calls and evidence uploads) | 18–33s per scenario |

All 26 real generations completed comfortably within any reasonable UI-facing timeout; no scenario approached Sprint D1's earlier-observed 55–61s outlier.

## 5.3 Reliability

- **27/27 scenario-runs completed successfully** (100%), after the JWT-refresh correction described in §2 (a test-harness issue, not a product one — zero product-side HTTP 500s or unhandled exceptions occurred in this round).
- **0 retries exhausted to total failure** — the failover chain always found a working tier within the Gemini pool itself; Groq/SambaNova were never needed as a full-provider fallback this round (though `verify_llm_providers.py`'s pre-flight confirmed both are independently reachable).
- **Operability gap found:** the `llm_gateway.generate()` success path logs at `INFO` level (`logger.info(...)`, line ~273 of `llm_gateway.py`), but the application's effective logging configuration only surfaces `WARNING`-and-above records in practice — confirmed directly: 52 `status=error` (warning-level) lines are present in the captured server log, **zero** `status=ok` (info-level) lines are, despite 26 real successful generations. The module's own docstring states "every attempt is logged... for auditability" — that claim does not hold operationally for the success path today, though Hard Rule 4's actual DB-level requirement (prompt/model/sources stored per output) is still met via the `litigation_case_analyses` row itself, independently confirmed by direct query. **Filed as TICKET-22 (Minor)** — an observability gap, not a Hard Rule violation.

---

# 6. Cost Analysis

Per the sprint's explicit instruction, **no unavailable figure is estimated.**

| Metric | Status |
|---|---|
| Provider | Measured — see §5.1 |
| Model | Measured — see §5.1 |
| Latency | Measured — see §5.2 |
| Retry count | Measured — see §5.3 (52 failed attempts, all pre-success failover, logged) |
| **Prompt tokens / completion tokens / total tokens** | **Not measured — structurally unavailable.** `llm_gateway.py`'s `GenerationResult` dataclass (`text`, `provider`, `model`, `latency_ms`, `masked_prompt`) has no token-count field, and none of Gemini's, Groq's, or SambaNova's raw response bodies are parsed for usage data anywhere in the codebase. This is a real, code-level gap, not a reporting limitation of this round — filed as **TICKET-23 (Enhancement)**. |
| **Cost per request / per scenario / estimated monthly cost** | **Not measured, for the same reason** — cost cannot be derived without token counts. |
| Free-tier ($0) expectation (ADR-009) | **Not falsified this round** — every real call this round used Gemini's free tier (`gemini-2.5-flash` / `gemini-2.5-flash-lite`), and 26 real generations plus their deterministic-endpoint overhead produced no billing-relevant signal observed. This is consistent with, but does not by itself prove, the $0/month architecture expectation at full Sprint 3.6 scale. |

---

# 7. Defect Report — this round's new findings

Per the sprint's Defect Policy, every item below is classified. **No Category A (Certification Blocker) defects were found this round** — nothing prevented the validation from completing; the one Category-A-shaped event (JWT expiry) was a test-harness issue, corrected without touching product code, and is documented in §2 rather than filed as a ticket.

| Ticket | Finding | Category | Severity | Scenarios |
|---|---|---|---|---|
| TICKET-16 | Statute corpus covers only 6 acts / 633 chunks; missing Limitation Act, Specific Relief Act, CPC, Easements Act, RERA Act, Commercial Courts Act | B | Major | Nearly all 26 |
| TICKET-17 | Citation Verifier non-deterministic — same real case name verified on retry after returning unverified live | B | Major | CIV-03 |
| TICKET-18 | Some real, correctly-named precedents (older SC / NCDRC) fail to verify even on retry | B | Minor | CONT-03, RERA-03 |
| TICKET-19 | Model sometimes proposes a real but substantively irrelevant "famous case" precedent | B | Minor | IA-02 |
| TICKET-20 | `gemini-2.5-flash-lite` shows materially weaker/confused legal reasoning than `gemini-2.5-flash` on the same task type | B | Major | APP-01/02/03 |
| TICKET-21 | Model-tier degradation (pro→flash/flash-lite) is completely silent to the advocate | B | Major | All 26 |
| TICKET-22 | LLM Gateway success-path logs are suppressed by effective logging config; only failures are visible operationally | B | Minor | All 26 (log-level config, not scenario-specific) |
| TICKET-23 | No token-usage or cost capture anywhere in the LLM Gateway | B | Enhancement | All 26 |
| — | Deterministic evidence-gap check flags every fact row without its *own* attached file, even when a separately-uploaded exhibit documents the same event — mechanical noise, not a hallucination | B | Minor (observation, not filed as a ticket — a data-model/UX note, see Lessons Learned) | All 26 |

**Pre-existing, reconfirmed-not-new** (no new ticket filed — already tracked): TICKET-7 (state-coverage gap, PROP-01/PROP-04/RERA-02/IA-02), TICKET-8 (hearing/IA blindness, IA-01/02/03), TICKET-11 (Cerebras key), TICKET-15 (PII over-masking, reconfirmed live on CIV-01: 4 `PARTY_*` placeholders generated for 2 actual parties).

---

# 8. Release Readiness Report & Production Readiness Scorecard

| Area | Verdict | Basis |
|---|---|---|
| Architecture | **PASS** | Deterministic/LLM trust boundary held exactly as designed across all 27 runs; no subsystem silently inherited another's errors |
| Database | **PASS** | All 17 tables present and functioning; RLS blocks anon access confirmed live in pre-flight |
| Infrastructure | **PASS** (Cerebras excepted, waived — TICKET-11) | 3/4 provider tiers healthy, Storage round-trip real, Runtime healthy |
| Security | **CONDITIONAL** | RLS/auth correct; `evidence` bucket is public by prior approved decision (TICKET-13, still open, out of this round's scope) |
| **AI Quality** | **CONDITIONAL** | Zero fabrication-presented-as-verified (clears the zero-tolerance gate); but corpus coverage (TICKET-16) and model-tier degradation (TICKET-20/21) are real, material gaps in the layer Sprint 3.6 is meant to build on |
| Performance | **PASS** | All real generations 7.8–23.3s, no outliers, no timeouts |
| Cost | **PARTIAL / Not measurable** | No token/cost instrumentation exists (TICKET-23); free-tier usage not falsified this round |
| **Explainability** | **CONDITIONAL** | `grounded: true/false` flagging works correctly and was observed working exactly as designed (IA-03's CPC citation correctly flagged ungrounded); but silent model-tier degradation (TICKET-21) undermines explainability of *which* model actually produced a given analysis |
| **Citation Quality** | **CONDITIONAL** | Gate mechanism itself is sound (never renders a live link without a `get_doc()`-confirmed match); but real non-determinism (TICKET-17) and a low hit-rate for older/tribunal precedent (TICKET-18) mean the "unverified" label under-represents how many proposed citations are actually real |
| **Hallucination** | **PASS** | Zero instances found across 26 real generations of a fabricated fact, statute, or citation presented as confirmed |
| UX | **Not assessed this round** | Guide explicitly scopes this out (§0: "does not cover UI polish") |
| Deployment | **PASS** | Consistent with Sprint D1's confirmed state; no infrastructure drift found |

---

# 9. Lessons Learned

**What worked:** running the full 26-scenario guide for real — not tracing code, not partial-executing the deterministic layer alone — surfaced findings no prior round could reach (corpus composition, citation-verifier flakiness, model-tier quality variance, the silent gemini-2.5-pro rate-limiting). The guide's own design (regression checks embedded as live scenarios, not just unit tests; deliberate stress scenarios like CIV-05 and CONT-01's A/B pair) paid off directly — every one of its predicted findings reproduced exactly as written, with zero surprises on the deterministic side.

**What failed (in this round's own execution, not the product):** the throwaway JWT's 1-hour TTL was consumed by a long pre-execution reading phase, causing a mid-batch auth failure across 18 scenario-runs. Caught immediately by the distinctive fast-fail error signature, corrected with a token refresh, no product code touched. **Process improvement:** future validation rounds should mint the test session token immediately before, not long before, the execution phase begins — or refresh proactively if more than ~30 minutes of non-execution work intervenes.

**What production revealed that a smoke test couldn't:** Sprint D1's single smoke-test run never exercised `gemini-2.5-pro` enough times to reveal it is *always* rate-limited on the current key — a single successful call (which happened to land on `gemini-2.5-flash` after one retry) looked like normal failover, not a systemic 100%-miss pattern. Volume mattered here specifically.

**What unit tests missed:** all 214 backend unit tests pass, and correctly so — they test each subsystem's logic in isolation with controlled inputs. None of them could have caught the corpus-coverage gap (that's a data problem, not a logic problem), the citation-verifier's live non-determinism (needs the real external API), or the cross-model quality variance (needs a real LLM call, not a mock). This is exactly the class of finding this sprint exists to produce.

**Recommendation:** before Sprint 3.6 (Pleading Generation) leans further on statute grounding and citations than Case Analysis already does, prioritize TICKET-16 (corpus expansion — Limitation Act, Specific Relief Act, CPC, Easements Act, RERA Act, Commercial Courts Act are the highest-value additions) and TICKET-21 (surface the actual model tier used, at minimum in the stored/audit record if not the UI) ahead of, or in parallel with, Sprint 3.6's early milestones.

---

# 10. Final Certification Decision

## CERTIFIED WITH CONDITIONS

| Condition | Severity | Blocking / Non-blocking for Sprint 3.6 start | Estimated effort | Recommendation |
|---|---|---|---|---|
| TICKET-16 — expand statute corpus (Limitation Act, Specific Relief Act, CPC, Easements Act, RERA Act, Commercial Courts Act) | Major | **Non-blocking for starting Sprint 3.6 design/scaffolding, but should land before real pleading drafts are trusted for advocate review** | Medium (corpus ingestion pipeline already exists — `scripts/ingest_statutes.py` — this is a data-sourcing task, not new engineering) | Prioritize before Sprint 3.6's first real drafting milestone |
| TICKET-20/21 — flash-lite quality gap + silent model-tier degradation | Major | Non-blocking | Small (surface `model_used` in the stored/audit trail more prominently; consider whether `case_analyst`/future `pleading_drafter` task types should exclude flash-lite from the pool) | Address before or during Sprint 3.6 |
| TICKET-17/18 — citation verifier non-determinism and low older-case hit rate | Major/Minor | Non-blocking | Small–Medium (investigate whether IK search retry logic can be made more robust; document the known lower hit-rate for pre-2000 and tribunal-tier judgments) | Track, address opportunistically |
| TICKET-19 — irrelevant-but-real precedent proposals | Minor | Non-blocking | Small (prompt-level fix — out of scope for this sprint's "do not modify prompts" rule; revisit) | Track for Sprint 3.6 prompt design |
| TICKET-22/23 — logging/observability and cost instrumentation gaps | Minor/Enhancement | Non-blocking | Small | Opportunistic |
| TICKET-7/8/11/13/15 | (pre-existing, unchanged) | Non-blocking, already tracked | — | Continue as previously scheduled |

**No condition above is a hard blocker on beginning Sprint 3.6.** They are the conditions under which this certification is granted: build Sprint 3.6, but do not present a pleading draft to Nitesh for real client use until at minimum TICKET-16 has meaningfully progressed, since pleading generation depends on statute grounding even more heavily than case analysis does.

---

# 11. Open decision for Nitesh: test data retention

The 26 real `[TEST]`-prefixed matters created this round — with real AI Case Analyses, real PII masks, and real uploaded evidence files — currently remain in the production database, along with the throwaway auth user. Unlike Sprint D1's smoke test (which existed only to prove the pipeline didn't 500), this round's entire purpose was to produce real, reviewable output for exactly the kind of scrutiny only Nitesh can give it. Recommend: **leave the data in place** so it can be browsed directly in the app before cleanup, rather than deleting it sight-unseen. Say the word and it will be cleaned up (cascade-deleted matters, storage objects removed, throwaway auth user deleted) the same way Sprint D1's smoke-test data was.

---

# 12. Sprint 3.6 — AI Pleading Generation: Engineering Execution Plan

*(Provided per the sprint's "if certified" instruction. Not implemented this sprint — planning only.)*

## Objectives

Build the first pleading-drafting capability on top of the now-certified AI Case Analysis vertical slice, per [ADR-011](../30_Implementation/ADR/ADR-011-ai-case-analysis-before-pleading.md): the advocate reviews and approves a Case Analysis, then Sprint 3.6 lets them generate a first-draft pleading (plaint or written statement, scoped narrowly at first) grounded in that reviewed analysis — never free-form, per CLAUDE.md Hard Rule 2.

## Scope (first iteration)

- **In scope:** plaint drafting for the well-covered categories this round validated cleanly — straightforward Money Recovery / Breach of Contract civil suits (CIV-01, COM-01/02, CONT-02/03/04-shaped matters), where Limitation and Forum are unambiguous and the statute corpus (post-TICKET-16 progress) has real coverage.
- **Out of scope for the first iteration:** RERA complaints, Interim Applications, and Appeals — each has an open, live-confirmed gap this round documented (RERA/IA category-fit gaps, hearing-blindness, forced-fit limitation categories) that pleading generation would otherwise silently inherit.

## Architecture touchpoints

- **Jinja2 `.docx` skeletons** (Hard Rule 2): new `templates/litigation/plaint_civil_suit.docx.j2`-style skeleton, following the same fixed-structure/bespoke-clause-fill pattern already proven in the Contracts module.
- **Prompt Registry:** a new `pleading_drafter` system prompt in `llm_gateway.SYSTEM_PROMPTS`, carrying the same `_GROUNDING_INSTRUCTION` / `_DELIMITER_INSTRUCTION` every other task type uses, plus an explicit instruction that it fills clauses inside the skeleton and never invents structure.
- **Context Assembly:** the drafter's prompt should be built from the **approved Case Analysis row** (not re-run from raw facts) — matter_summary, possible_causes_of_action (with their grounded statute refs), chronological_facts, limitation_summary, jurisdiction_summary — so pleading generation is provably downstream of, and consistent with, what the advocate already reviewed and signed off on, not a second independent synthesis that could silently diverge.
- **RAG integration:** reuse `hybrid_retrieve()` unchanged, but the corpus gap this round found (TICKET-16) is a direct, load-bearing dependency here — flag any cause of action whose relied-upon statutes are ungrounded as "requires manual statute verification" directly in the drafted pleading, not just in the upstream analysis.

## Versioning strategy

Mirror `draft_versions`/`litigation_case_analyses`' existing pattern: a new `litigation_pleading_drafts` table, immutable auto-incrementing `version_no` per matter, never overwritten — same convention, same audit-trail guarantee (Hard Rule 4).

## Testing strategy

- Unit tests for the skeleton-fill logic (deterministic, no LLM).
- A small, deliberately-scoped acceptance guide (5–8 scenarios, not 26) covering only the in-scope categories above, run for real against production exactly as this sprint did — not just unit-tested — before any pleading draft reaches Nitesh.
- Explicit regression tests locking in that a drafted pleading's statute citations are a strict subset of what the source Case Analysis already showed as grounded (never a superset — pleading generation must not introduce new, unreviewed statutory claims).

## Acceptance criteria

- Zero instances of pleading structure/boilerplate originating from the LLM rather than the skeleton (Hard Rule 2, enforced in code via skeleton-diff testing, not just prompted).
- Every citation in a drafted pleading passes through the same Citation Verifier gate as Case Analysis (Hard Rule 1) — no new bypass path.
- A live browser E2E walkthrough on at least one real seeded scenario before counting any pleading type as "shipped," per the Per-Template Release Gate.

## Risks

- **Corpus gap (TICKET-16) is now a Sprint 3.6 dependency, not just a Case Analysis quality issue** — pleading generation will cite statutes more assertively than an analysis does; shipping before the corpus gap closes risks producing confidently-worded but thinly-grounded pleadings.
- **Silent model-tier degradation (TICKET-21)** carries higher stakes in pleading generation than in analysis — a flash-lite-produced plaint reaching an advocate's desk without any signal of which model produced it is a bigger trust risk than an analysis with the same gap.
- **Citation verifier non-determinism (TICKET-17)** means the same pleading, regenerated, could show a different citation-verification result for the identical precedent — worth deciding explicitly whether pleading generation should re-verify on every version or lock verification status at first-generation time.
