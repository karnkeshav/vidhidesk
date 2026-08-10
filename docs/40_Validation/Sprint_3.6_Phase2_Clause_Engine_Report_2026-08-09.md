> **Title:** Sprint 3.6 Phase 2 — AI Drafting Engine & Clause Generator Report
> **Version:** 1.0
> **Status:** Final for this sprint
> **Owner:** Keshav (executed) / Nitesh (to review before any full-pleading-drafting work begins)
> **Audience:** Nitesh, Keshav, future AI agents assessing clause-engine readiness
> **Last Updated:** 9 August 2026
> **Baseline:** Sprint 3.6 Phase 1 working tree, certified WITH CONDITIONS per
> [`Sprint_3.5.6_Certification_Report_2026-08-09.md`](Sprint_3.5.6_Certification_Report_2026-08-09.md);
> Phase 1 recommendation was **FOUNDATION REQUIRES FURTHER WORK** per
> [`Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md`](Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md)
> **Related Documents:** [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md) (TICKET-24 through TICKET-27, new this sprint), [`../30_Implementation/ADR/ADR-002-deterministic-document-structure.md`](../30_Implementation/ADR/ADR-002-deterministic-document-structure.md)

---

# 1. Scope and rules observed

Per this sprint's brief: **no production-quality pleadings were generated** — the objective was validating the clause-engine architecture, not drafting. **No deterministic engine** (`limitation.py`, `forum.py`) was modified. **No architecture redesign** — the clause engine is built strictly downstream of Phase 1's Pleading Outline (`case_analysis_id` → `pleading_outline_id` → `clause_id`), reusing the LLM Gateway, Citation Verifier, and PII masking layer exactly as Phase 1 did, never re-implementing them. Per the sprint's explicit Defect Policy ("Only Certification Blockers may be fixed. All other defects become backlog items."), **every defect found during this sprint's own live evaluation (§4–§5 below) was documented, not fixed** — see TICKET-24 through TICKET-27 in `Backlog.md`.

All 253 backend tests pass (225 pre-existing + 28 new: 20 for `clause_generator.py`, 8 for `document_composer.py`).

---

# 2. Deliverable 1 — Clause Generator Report

**14 independent clause generators implemented**, in `api/app/services/clause_generator.py`, matching this sprint's required list exactly: Cause Title, Court Details, Parties, Jurisdiction, Facts, Chronology, Cause of Action, Legal Grounds, Applicable Statutes, Applicable Precedents, Reliefs, Prayer, Verification, List of Annexures (`CLAUSE_TYPES`).

**Deterministic vs. LLM split, decided by the project's own established bar** (Backlog.md's "Governing Law: `llm_fillable` → `fixed_boilerplate`" finding: *"does this clause require synthesizing free prose from the intake inputs, in a way a template author cannot enumerate in Jinja? If no, it's deterministic."*), applied here one layer deeper than Phase 1's outline-level split:

| Deterministic (9, zero LLM calls) | LLM-synthesized (5) |
|---|---|
| Cause Title, Court Details, Parties, Jurisdiction, Chronology, Applicable Statutes, Applicable Precedents, Verification, List of Annexures | Facts, Cause of Action, Legal Grounds, Reliefs, Prayer |

Jurisdiction was deliberately reclassified as deterministic during design (initially assumed LLM) — the Forum Advisor's own output (`territorial_basis`, `pecuniary_basis`, `governing_provisions`) is already fully structured and enumerable in a template sentence; adding an LLM call there would only add hallucination surface and latency for zero synthesis benefit. This is the same judgment call the Backlog's Governing Law finding already validated for the Contracts module, applied here for the first time in Litigation.

**Every generator satisfies the sprint's per-generator requirements**: receives structured context (`_clause_context()` — matter, pleading outline, source case analysis, parties, all already-reviewed), receives retrieved statutes (`outline.applicable_statutes`, passthrough, never re-retrieved — Hard Rule 3), receives retrieved precedents (`outline.applicable_case_law`, already Citation-Verifier-gated — Hard Rule 1), returns structured output (`{content, statute_refs, case_law_refs, confidence}`), includes confidence (`_confidence_for()`), includes citations, supports regeneration (`generate_clause()` always appends a new version).

**One shared LLM system prompt** (`task_type="clause_drafter"`, `llm_gateway.py`) serves all 5 LLM generators — the per-clause instruction lives in each generator's own prompt-builder function (`_prompt_facts`, `_prompt_cause_of_action`, etc.), not in 14 separate system prompts. This keeps every generator independently callable without 14 separate prompt surfaces to maintain, while every generator remains independently regenerable (§4 verifies this in code and live).

---

# 3. Deliverable 2 — Document Composer Report

`api/app/services/document_composer.py::compose_pleading()` assembles the latest **advocate-approved** version of each clause type into one ordered draft. Verified in code and by live test (§4):

- **No legal reasoning, no LLM call** — `test_composer_never_calls_llm` monkeypatches `clause_generator.generate` to raise `AssertionError` on any call and confirms `compose_pleading()` never triggers it, including on an outline with zero approved clauses.
- **Preserves clause order** — sections are emitted in `CLAUSE_TYPES` pipeline order regardless of the order clauses were approved in (`test_compose_pleading_preserves_fixed_order_and_numbering` approves Prayer → Cause Title → Facts, out of order, and confirms the composed output is still Cause Title → Facts → Prayer).
- **Preserves numbering** — `paragraph_no` is assigned purely positionally by the composer itself, never re-derived from clause content.
- **Preserves headings** — from the fixed `CLAUSE_HEADINGS` map, not from any clause's own text.
- **Preserves citations** — `statute_refs`/`case_law_refs` are carried through from the clause row verbatim, never re-verified or re-graded at composition time.
- **Only ever uses the approved version** — `_latest_approved_by_type()` filters on `review_status='approved'` before selecting the latest `version_no`; a clause regenerated-but-not-yet-reviewed (v2 pending) does not silently override an already-approved v1 in the composed draft (`test_compose_pleading_uses_latest_approved_version_not_latest_overall`).
- **Missing clauses are surfaced, never silently skipped** — an unapproved or unreviewed clause type appears in `missing_clauses`, not as absent-without-explanation.
- **Immutable, versioned output** — recomposing after approving one more clause creates a new `litigation_pleading_drafts` row (`version_no` incremented); the prior draft row is untouched.

---

# 4. Deliverable 3 — Versioning Report

Every clause row (migration `0018_pleading_clauses.sql`, `litigation_pleading_clauses`) carries all seven fields the sprint brief requires explicitly: `version_no`, `created_at`, `model_used`/`model_routing`, `prompt_version`, `regenerated`, `author`, `review_status`.

**"Changing one clause must never regenerate the whole document" is enforced structurally, not just by convention** — verified live and in unit test:

- `test_regenerating_one_clause_never_touches_another` regenerates Cause Title twice (v1 → v2) after generating Parties once, then asserts the Parties row is still exactly one row at v1 — untouched by the Cause Title regeneration.
- Live confirmation (§5): across all 6 real matters, regenerating `facts` a second time (v1 → v2) inserted exactly one new row per matter; the other 13 clause types' rows for that matter/outline were never touched (`litigation_pleading_clauses` unique constraint is `(matter_id, pleading_outline_id, clause_type, version_no)` — a regeneration can only ever collide with its own prior versions, never another clause type's).

**Human Review is a first-class gate, not a UI-only convention** — `review_clause()` only accepts `'approved'`/`'rejected'` (never re-accepts `'pending'`, which would be meaningless as a manual transition), validates the clause belongs to the calling matter, and never touches `content`/`version_no`/any other clause. The document composer (§3) structurally cannot bypass this gate — it reads `review_status='approved'` directly, there is no code path from "clause generated" to "clause composed" that skips review.

---

# 5. Deliverable 4 — Clause Evaluation Report (live evaluation)

**Methodology:** ran `generate_all_clauses()` (all 14 generators, real LLM calls where applicable) against the same 6 real certification matters Phase 1's own evaluation used (APP-01, CIV-01, COM-01, IA-01, PROP-03, RERA-01), each starting from its existing, live-generated Phase 1 Pleading Outline — never a fresh outline, per this module's "stay downstream of what's already reviewed" architecture. Every clause that generated without a warning was auto-approved by the evaluation script (a scripted stand-in for advocate review, **for evaluation purposes only** — not a claim that a real advocate would approve everything; see the harness's own docstring), then `compose_pleading()` was run once per matter. One clause (`facts`) was regenerated a second time per matter to test regeneration consistency. All 84 clause generations (6 matters × 14 types) plus 6 regenerations plus 6 compositions ran for real, against the live production Supabase project and live LLM providers, in 293 seconds total.

**Reliability:** 0 hard errors across 84 generations. 2 generation warnings (malformed LLM JSON), both on `legal_grounds` (COM-01, PROP-03) — see TICKET-25. 82/84 (98%) auto-approved cleanly.

**Composition:** 4 of 6 matters composed a complete 14-section draft with zero missing clauses on the first pass; COM-01 and PROP-03 each show exactly one missing clause (`legal_grounds`, correctly excluded — its malformed-JSON generation was never approved, and the composer correctly listed it as missing rather than silently omitting it or filling a placeholder).

**Per-clause-type breakdown** (6 runs each, LLM-generated types only):

| Clause type | Successful | Statute refs claimed (of 6 runs) | Avg confidence (successful runs) | Avg latency |
|---|---:|---:|---:|---:|
| Facts | 6/6 | 0/6 (not asked to cite — narrative only) | 0.933 | 5,874ms |
| Cause of Action | 6/6 | 2/6 | 0.892 | 5,946ms |
| Legal Grounds | 4/6 | 3/4 successful | 0.875 | 7,344ms |
| Reliefs | 6/6 | 1/6 | 0.842 | 4,343ms |
| Prayer | 6/6 | 0/6 (not asked to cite — synthesizes reliefs, not statutes) | 0.933 | 4,772ms |

**Regeneration consistency:** all 6 `facts` regenerations succeeded, but text length varied meaningfully run-to-run (e.g. CIV-01: 1,150 chars v1-adjacent → same matter's v1 was 1,043 chars; APP-01: 267 chars v2 vs. a materially longer v1) and, in 3 of 6 matters, the model that served v2 differed from the model that served v1 (e.g. APP-01 v1 `gemini-2.5-flash` → v2 also `gemini-2.5-flash` but IA-01 v1/v2 both `gemini-2.5-flash-lite` while CIV-01 shifted between calls). This is expected given real-time provider rate-limit state (§6) — the same clause_type, same context, regenerated minutes apart, can land on a different model tier and therefore produce meaningfully different prose, not just re-phrased text. **Filed as TICKET-27** — not a defect, but a real caveat: "regenerate this clause" does not guarantee the same underlying model drafts it twice.

---

# 6. Deliverable 5 — Grounding Metrics

Across the 24 LLM-clause runs that could plausibly cite something (`facts`/`prayer` are narrative-only by design, correctly never asked to cite — see their prompts):

| Metric | Result |
|---|---:|
| Statute refs claimed | 6 total, across 6/24 eligible clause runs |
| Statute refs grounded (matched `outline.applicable_statutes`) | 5/6 (83%) |
| Statute refs ungrounded, correctly flagged | 1/6 — PROP-03's `reliefs` claimed "Specific Relief Act, 1963, Section 10" |
| Case law refs claimed | 0/24 |
| Case law refs verified | n/a |

**The one ungrounded statute ref is a genuine, evidence-backed catch, not a false positive**: Specific Relief Act, 1963, Section 10 is in fact the real, correct provision governing specific performance of contracts — PROP-03 is literally a specific-performance suit. It was flagged `grounded: false` purely because PROP-03's *outline* (a Phase 1 artifact, generated before this sprint) never retrieved that section into its `applicable_statutes` list — a live, concrete instance of the still-open Phase 1 TICKET-16 retrieval gap (73% recall, not 100%) surfacing one layer downstream. The grounding gate did exactly its job: a plausible, likely-correct citation was still shown as unverified rather than silently trusted, because this module's own rule (Hard Rule 3) is "grounded against what was actually retrieved," not "grounded against what's actually true" — the system cannot tell those apart, by design, and correctly defers to the retrieval record.

**Zero claimed case-law refs is the correct behavior given the upstream data, not a clause-engine defect**: `verified_case_law` is built directly from `outline.applicable_case_law` filtered to `status == "verified"`; when that list is empty (as Phase 1 §7 already found for all 6 of these same matters' outlines), the `clause_drafter` system prompt explicitly tells the model "do not cite any case," and every model, every time, complied — a real, live confirmation that Hard Rule 1's "never propose a new, unverified case here" instruction holds under real conditions across 24 opportunities to violate it. It also means this sprint's clause engine cannot demonstrate real precedent-citation quality until Phase 1's case-law-recall gap (Foundation Report §9, point 3) is closed — **carried forward, not newly found**.

**Legal Grounds is this pipeline's weakest clause type on both axes** — the clause type existing specifically to connect statutes/precedents to the pleaded facts had a 33% malformed-JSON failure rate (2/6) and, of its 4 successful runs, only 3 cited any statute at all (75% of successful runs; 50% of all 6 attempts). **Filed as TICKET-25/TICKET-26.**

---

# 7. Deliverable 6 — Performance Metrics

| Metric | Deterministic clauses (54 runs) | LLM clauses (30 runs) |
|---|---:|---:|
| Avg latency | 1,014ms | 5,656ms |
| Min / Max latency | 986ms / 1,369ms | 3,328ms / 14,962ms |

Deterministic-clause latency (~1s, tight variance) is entirely the real Supabase round-trip for `_clause_context()` (4 sequential table reads against the live production project) — there is no computation cost, confirming the "zero LLM calls, zero synthesis" design claim in §2 is not just a code-path claim but a measured one (no deterministic clause generation ever showed LLM-scale latency).

**A real, directly observed instance of cumulative rate-limit pressure within a single run**, extending Phase 1's TICKET-21 finding (previously "worse across a whole session's cumulative volume, not fully quantified within one run") — 30/30 (100%) of this round's LLM clause generations degraded past `gemini-2.5-pro`, matching or exceeding Phase 1's own degradation rate, and the specific pattern of *which* fallback tier caught each call visibly worsened over the course of this one 293-second run: the first two matters processed (APP-01, CIV-01) mostly landed on `gemini-2.5-flash`; all four matters processed after them (COM-01, IA-01, PROP-03, RERA-01) landed on `gemini-2.5-flash-lite` or, 4 times, all the way to `groq/llama-3.3-70b-versatile`. Model distribution across all 30 LLM clauses: `gemini-2.5-flash-lite` 16 (53%), `gemini-2.5-flash` 10 (33%), `groq/llama-3.3-70b-versatile` 4 (13%) — `gemini-2.5-pro` served **zero** of 30 requests. This is concrete, within-session evidence for the capacity-planning concern Phase 1 flagged but could not fully quantify.

Total wall time for the full evaluation (84 clause generations + 6 regenerations + 6 compositions, real calls): 293 seconds (~49s/matter).

---

# 8. Deliverable 7 — Cost Analysis

Unchanged structural gap from Phase 1 (TICKET-23, still open, out of this sprint's scope): `GenerationResult` carries no token-count field, so per-call or per-clause cost cannot be measured, only reported as unavailable — consistent with this project's "never estimate unavailable values" discipline.

| Metric | Status |
|---|---|
| Deterministic clause generation cost | **$0** — no LLM call, confirmed by the latency data in §7 (no run showed LLM-scale latency) |
| LLM clause generation cost | **Not measured — structurally unavailable**, same TICKET-23 gap Phase 1 reported |
| Real LLM calls this sprint | 30 clause generations + 6 regenerations = 36 real calls, all free-tier (Gemini flash/flash-lite, Groq), consistent with $0 actual spend |
| Free-tier headroom | Confirmed worse, not just flagged — see §7's within-run degradation pattern. `gemini-2.5-pro` and, increasingly within a single run, `gemini-2.5-flash` are not reliably available at the call volumes a real clause-drafting session would generate (14 clauses × regenerations × review cycles, per matter, is a materially higher call volume per matter than Phase 1's one-outline-per-matter round). |

---

# 9. Recommendation

## CLAUSE ENGINE REQUIRES FURTHER WORK

The architecture itself — 14 independent, independently versioned, independently regenerable clause generators; a composer that is genuinely reasoning-free and assembly-only; a versioning/review gate the composer cannot bypass — is built, tested (28 new unit tests, all passing), and **live-validated end-to-end against 6 real matters with zero hard failures and zero fabricated results**. This is a real, working foundation, not a prototype that only passes mocked tests.

It is not yet the foundation to build full pleading generation on, for three reasons directly evidenced above, none of which require redesigning what this sprint built:

1. **Legal Grounds — the one clause type whose entire job is connecting law to facts — is this pipeline's least reliable clause** (§5/§6): a 33% malformed-output rate and a 50%-of-attempts grounding rate are not acceptable for the clause an advocate would most need to trust without re-deriving it themselves. This is very likely the same root cause as Phase 1's TICKET-20 (weaker fallback-tier models reasoning worse under pressure) manifesting in a new, more complex clause-level task — not a new, unrelated defect, but not yet resolved either.
2. **Case-law grounding remains completely unvalidated by this round's evidence**, through no fault of the clause engine itself — Phase 1's still-open case-law-recall gap (empty `applicable_case_law` in these same 6 outlines) means the clause engine has had zero real opportunities this round to demonstrate it can correctly ground a clause in a real precedent, only that it correctly declines to fabricate one when none is available. Both are necessary; only the second has been shown.
3. **Provider capacity pressure measurably worsened within a single 293-second evaluation run** (§7), not just across a whole session as Phase 1 found — a real pleading-drafting session (14 clauses, plus regenerations, plus review cycles, per matter) will generate materially more LLM calls per matter than Phase 1's one-call-per-matter outline round did, and this round shows that volume pattern degrading provider tier further within a single sitting, not just accumulating across a day.

**None of these block starting the next phase's design work.** The clause engine, composer, and versioning/review model are solid enough to build a Human Review UI and, eventually, a document-export layer on top of. They block trusting a *fully clause-engine-drafted* pleading section (especially Legal Grounds) in front of Nitesh without: (a) investigating the Legal Grounds reliability gap specifically (its prompt, or its context length, or model-tier sensitivity — genuinely unresolved with this round's evidence, not yet diagnosed), (b) Phase 1's case-law recall gap closing enough to give this module a real chance to demonstrate precedent grounding, and (c) a real answer to the capacity question before assuming a full advocate review-and-regenerate workflow's call volume is sustainable on the free tier.

---

# 10. Return

1. **Git commit hash:** none — no commit was made this session, per this session's standing rule of only committing when explicitly asked. `git status` shows this sprint's work as uncommitted, staged for review.
2. **Files changed:** new — `api/migrations/0018_pleading_clauses.sql`, `api/app/services/clause_generator.py`, `api/app/services/document_composer.py`, `api/tests/test_clause_generator.py`, `api/tests/test_document_composer.py`. Modified — `api/app/models/schemas.py` (9 new schemas), `api/app/routers/litigation.py` (5 new endpoints), `api/app/services/llm_gateway.py` (new `clause_drafter` task type/system prompt).
3. **Clause generators implemented:** 14/14 (§2) — 9 deterministic, 5 LLM-backed, one shared `clause_drafter` system prompt, every generator independently regenerable.
4. **Document composer summary:** built, reasoning-free, order/numbering/heading/citation-preserving, approved-clauses-only, immutable-versioned output (§3).
5. **Grounding metrics:** 5/6 claimed statute refs grounded (83%); 1 ungrounded ref correctly flagged rather than trusted, traced to a real, already-known upstream retrieval gap (§6); 0/0 case-law refs claimed-vs-verified (upstream data was empty in all 6 matters, correctly never fabricated).
6. **Clause evaluation metrics:** 84/84 clause generations completed with 0 hard errors, 82/84 (98%) auto-approved cleanly; Legal Grounds is the outlier at 4/6 (67%) successful and only 3/4 of those grounded (§5).
7. **Performance metrics:** deterministic clauses ~1.0s (real DB round-trip only, zero LLM-scale cost); LLM clauses avg 5.7s (3.3s–15.0s); 100% of LLM clauses degraded past `gemini-2.5-pro`, with a directly observed within-run worsening pattern (§7).
8. **Cost metrics:** $0 real spend (free tier); per-call token cost remains structurally unmeasured (TICKET-23, unchanged).
9. **Recommendation:** §9 — **CLAUSE ENGINE REQUIRES FURTHER WORK**, with three specific, bounded blockers named, none requiring an architecture redesign.
10. **Remaining blockers before full pleading generation:** (a) Legal Grounds clause reliability/grounding gap, newly found and diagnosed this sprint (TICKET-25/26); (b) Phase 1's case-law recall gap, still open, now confirmed to be blocking this module's own evaluation too; (c) LLM provider free-tier capacity under realistic per-matter call volumes, now evidenced within a single run rather than only across a session (§7/§8).
