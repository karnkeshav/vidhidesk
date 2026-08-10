> **Title:** Sprint 3.6 Phase 1 — AI Pleading Generation Foundation Report
> **Version:** 1.0
> **Status:** Final for this sprint
> **Owner:** Keshav (executed) / Nitesh (to review before Sprint 3.6 Phase 2 begins)
> **Audience:** Nitesh, Keshav, future AI agents assessing pleading-generation readiness
> **Last Updated:** 9 August 2026
> **Baseline:** `ecc715fcd009043783e29c49c05d879c759638b0`; certified WITH CONDITIONS per [`Sprint_3.5.6_Certification_Report_2026-08-09.md`](Sprint_3.5.6_Certification_Report_2026-08-09.md)
> **Related Documents:** [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md) (TICKET-16 through TICKET-23), [`../30_Implementation/ADR/ADR-011-ai-case-analysis-before-pleading.md`](../30_Implementation/ADR/ADR-011-ai-case-analysis-before-pleading.md), [`../30_Implementation/ADR/ADR-002-deterministic-document-structure.md`](../30_Implementation/ADR/ADR-002-deterministic-document-structure.md)

---

# 1. Scope and rules observed

Per this sprint's brief: **no production-ready pleadings were generated** (only structured plans — enforced in code, not just prompted, see §4). **No deterministic engine** (`limitation.py`, `forum.py`) was modified. **No architecture redesign** — every change below extends an existing, already-certified pattern (the `litigation_case_analyses` versioning shape, the `ingest_statutes.py` pipeline, the `hybrid_retrieve()` signal-merge, the Citation Verifier's cache-first state machine) rather than replacing it. Every certification finding this sprint addresses (TICKET-16, TICKET-17/18, TICKET-20/21, TICKET-22) is named and traced to the specific code change that addresses it — none were bypassed or silently dropped.

All 225 backend tests pass (214 pre-existing + 11 new: 8 for `pleading_outline.py`, 3 for the citation-reliability changes), including 2 pre-existing tests updated to reflect intentional new behavior (model-degradation logging, not a regression).

---

# 2. Deliverable 1 — Updated Corpus Statistics

Sourced directly from India Code (`indiacode.nic.in`, the Ministry of Law and Justice's official bare-act repository) — 6 new real PDFs downloaded and ingested, not fabricated or summarized text. Verified via direct query of the live `statute_chunks` table, not estimated.

| Act | Chunks (before) | Chunks (after) |
|---|---:|---:|
| Code of Civil Procedure, 1908 | — | **915** |
| Indian Contract Act, 1872 | 178 | 178 |
| Limitation Act, 1963 | — | **134** |
| Transfer of Property Act, 1882 | 129 | 132 |
| Consumer Protection Act, 2019 | 107 | 107 |
| Registration Act, 1908 | 102 | 102 |
| Indian Stamp Act, 1899 | 95 | 95 |
| Real Estate (Regulation and Development) Act, 2016 | — | **91** |
| Indian Easements Act, 1882 | — | **63** |
| Specific Relief Act, 1963 | — | **46** |
| Commercial Courts Act, 2015 | — | **26** |
| Carriage by Road Act, 2007 | 22 | 22 |
| **Total** | **6 acts / 633 chunks** | **12 acts / 1,911 chunks** |

**A real chunking defect was found and fixed during ingestion, not just the corpus expanded.** `ingest_statutes.py`'s section-boundary regex required a section/rule number at the exact start of a line; an inserted/amended provision — rendered by India Code as `1[2. Pleading to state material facts...` (a footnote-reference digit and bracket glued directly before the real number) — never matched, silently merging the whole provision into whichever boundary preceded it. Found via CPC's Order VI Rule 2 (the foundational "material facts" pleading rule) and Order VIII Rule 1 (written statement) both going missing/wrong during ingestion — CPC's amendment-marker density exercised this bug far more than any prior act had. Fixed with a minimal regex extension (`(?:\d{1,3}[A-Z]?\[)?` optional non-capturing prefix); re-running ingestion on all 12 acts (idempotent upsert) recovered a few previously-missed sections on 3 of the original 6 acts too (Transfer of Property Act 129→132, plus smaller gains on two of the new acts), with zero regressions confirmed by re-running the full test suite.

**CPC's First Schedule (Orders/Rules) required a second, additive chunking pass** (`chunk_cpc_schedule()`), since Rule numbering restarts at 1 within every Order and would otherwise collide with — or be silently dropped behind — the identically-numbered Sections. Keyed as `"Order VII Rule 1"` rather than bare `"1"`. Verified directly: Order VII Rule 1 (plaint particulars), Order VIII Rule 1 (written statement), Order XXXVIII Rule 5 (attachment before judgment), and Order XXXIX Rule 1 (temporary injunction) — the four provisions pleading generation depends on most — are all present with real statutory text, not placeholders.

---

# 3. Deliverable 2 — Knowledge Retrieval Report

**Methodology:** re-ran `hybrid_retrieve()` against the exact same fact narratives from all 26 real Sprint 3.5.6 certification matters (still live in production, rebuilt via the same `_facts_narrative()` function the product itself uses — not paraphrased), now against the expanded 12-act corpus, and compared to each scenario's captured "before" top-5 from the certification round. Ground truth for "the correct act" was transcribed directly from the Acceptance Testing Guide's own stated expected statutory basis per scenario — not invented for this evaluation.

| Metric | Before (6 acts) | After (12 acts, top_k=5) | After (12 acts, top_k=8) |
|---|---:|---:|---:|
| Recall@k (correct act present) | **35%** (9/26) | **62%** (16/26) | **73%** (19/26) |

**A real, measured side effect was found, not just a headline improvement.** At top_k=5, several queries that *used* to correctly surface a specific act now show that act crowded out by generic CPC procedural chunks — CPC alone is 915 of 1,911 chunks (~48% of the whole corpus by volume). Confirmed directly: CIV-01 (a simple loan-recovery query) went from correctly surfacing Indian Contract Act content to a top-5 of `[CPC, CPC, Transfer of Property Act, Consumer Protection Act, CPC]`; PROP-03 (specific performance) similarly got crowded by generic CPC chunks ahead of the now-present, more specific Specific Relief Act. Retesting at top_k=8 recovered most of this (62%→73%) by giving smaller, more specific acts more room to compete alongside CPC's volume, without touching the underlying ranking algorithm.

**Action taken on this evidence:** `case_analysis.py::MAX_STATUTE_CONTEXT_CHUNKS` raised from 5 to 8 (also used by `pleading_outline.py`, which reuses the case analysis's already-retrieved statutes rather than re-retrieving — see §4). This is the one Phase 2 change actually shipped; it is a one-constant, low-risk change directly justified by the before/after measurement above, not a speculative tuning.

**Known confound in scenario-level retrieval, disclosed rather than hidden:** two scenarios' matter titles (`CONT-02`/`CONT-03`, carrying my own certification-round bookkeeping labels like "(Section 27 test)") produce an artificial `score: 1.0` tie across five unrelated acts, because `keyword_search()`'s exact-section-number regex matches the literal digits in my own title annotation. This is a testing-methodology artifact from the certification round's own matter titles, not a new product defect — already diagnosed and disclosed in the certification report, reconfirmed identically here.

---

# 4. Deliverable 3 — Pleading Architecture Report

**Pipeline implemented, exactly as specified:**

```
Case Analysis (existing, reviewed, versioned)
   -> Legal Issues            (LLM-synthesized)
   -> Applicable Statutes     (passthrough — never re-retrieved independently)
   -> Applicable Case Law     (LLM-proposed, Citation-Verifier-gated)
   -> Cause of Action         (LLM-refined, re-grounded against the same statutes)
   -> Reliefs Sought          (LLM-synthesized)
   -> Jurisdiction            (passthrough)
   -> Limitation               (passthrough)
   -> Evidence Mapping        (LLM-synthesized, from the case analysis's chronological_facts)
   -> Pleading Outline        (LLM-synthesized, FIXED section list)
   -> Versioning              (immutable, auto-incrementing per matter)
```

**New components:**
- `api/migrations/0015_pleading_outlines.sql` — `litigation_pleading_outlines` table. `case_analysis_id` is a required, non-null foreign key — the architectural guarantee that pleading planning stays downstream of an already-reviewed case analysis, never a silent independent re-derivation from raw facts. RLS matches the established owner-only select+insert pattern; unlike migrations 0011/0013/0014 (TICKET-12), every `CREATE POLICY` here is preceded by `DROP POLICY IF EXISTS`, so this migration is safely re-runnable.
- `api/app/services/pleading_outline.py` — the service module. PII masking is applied via the same `SupabaseMaskStore`/`mask_text` mechanism `case_analysis.py` uses, reusing the *same* per-matter mask map so placeholders stay consistent across both artifacts for a given matter (verified in `test_pleading_outline.py`'s happy-path test, which asserts `entities` is always passed to `generate()`).
- `api/app/routers/litigation.py` — `POST`/`GET /api/matters/{matter_id}/pleading-outline`, matching the Case Analysis endpoint's error-handling convention exactly (`PleadingOutlineError` → 400, `ProviderError` → 502).
- `api/app/models/schemas.py` — `PleadingOutlineOut` and supporting nested schemas.

**"Structured plan, not a document" is enforced in code, not just prompted** (per this sprint's explicit brief and the same principle ADR-002/Hard Rule 2 apply to contract drafting): `pleading_outline.py::FIXED_PLEADING_SECTIONS` is a fixed 8-entry list — Cause Title/Parties, Jurisdiction, Limitation, Facts Constituting the Cause of Action, Cause of Action, Valuation and Court Fees, Reliefs Sought, Verification — derived directly from CPC Order VII Rule 1's real statutory particulars (a)–(i), now that the corpus actually contains that text (§2). `_validate_outline_is_structured()` rejects any section name the model invents, backfills any section the model omits with an explicit "(not yet planned by the model)" rather than a silent gap, and truncates any `content_plan` exceeding 600 characters with an explicit warning — a code-level backstop against drift from planning notes toward drafted prose, tested directly in `test_pleading_outline.py`.

**Statute grounding and citation verification are reused, not reimplemented.** `cause_of_action` statute references are cross-checked against the *same* `applicable_statutes` the source case analysis already retrieved and ground-truthed — never re-retrieved, never trusted on the model's say-so (Hard Rule 3). `applicable_case_law` runs through the identical `verify_citation()` gate every other module uses (Hard Rule 1), now benefiting directly from Phase 5's reliability improvements (§5) for free.

---

# 5. Deliverable 4 — Model Routing Report

Addresses TICKET-20/21 directly: **model-tier degradation is no longer silent, anywhere in the system.**

- `llm_gateway.GenerationResult` now carries `requested_model` (the top of the pool for the task type), `degraded` (bool), and `fallback_chain` (every attempt, including failures, in order) — previously only discoverable by reading raw log lines and comparing against the pool's own source code.
- A `MODEL DEGRADED` warning-level log line is emitted explicitly whenever `actual_model != requested_model` — not buried in a sequence of per-attempt failure lines the reader has to count.
- **The underlying log-suppression bug (TICKET-22) that made even those per-attempt lines invisible in practice is fixed**: `app/main.py` now explicitly configures the `vidhidesk.*` logger hierarchy at `INFO` level with a real handler. Confirmed directly: the certification round captured 52 WARNING-level lines and 0 INFO-level success lines across 26 real generations; after this fix, both `status=ok` and the new `MODEL DEGRADED` lines are captured (see `test_audit_log_output_reflects_full_cascade`, updated to assert on the new line count).
- **`litigation_case_analyses` was retrofitted, not just the new pleading table** — `migrations/0016_case_analysis_model_routing.sql` adds a `model_routing` jsonb column, and `case_analysis.py` now populates it, so this fix applies to the already-certified Case Analysis feature too, not only new pleading work.

**What this sprint's own real usage revealed, worth reporting honestly rather than omitted:** in Phase 6's evaluation (§7), **every one of the 6 real pleading-outline generations degraded past `gemini-2.5-flash` and `gemini-2.5-flash-lite` all the way to `groq/llama-3.3-70b-versatile`** — worse than the certification round, where most calls landed on `gemini-2.5-flash`. This is consistent with cumulative free-tier rate-limit pressure from this session's own heavy real-call volume (26 certification calls + Phase 2/6 evaluation calls + 6 Phase 6 generations, all same day), not a code regression — but it is a genuine, newly-visible signal (visible *because* of this phase's own transparency work) that real single-advocate daily usage could plausibly exhaust free-tier headroom faster than the architecture's documented $0/month assumption (ADR-009) accounts for. Flagged as a recommendation in §9, not fixed this sprint (infrastructure/quota work is out of this sprint's scope).

---

# 6. Deliverable 5 — Citation Reliability Report

Addresses TICKET-17/18 directly.

**Root cause fixed, not papered over.** `verify_citation()` previously cached *any* result — verified or unverified — and returned the cached row on every future call, forever. The certification round found a real, well-known Supreme Court case (*Anathula Sudhakar v. P. Buchi Reddy*) come back `unverified` live, then `verified` on an immediate independent retry with the identical case name — proof the underlying Indian Kanoon search ranking is non-deterministic call-to-call. A transient miss was therefore being locked in as a permanent wrong answer. Fixed: **only a cached `status == "verified"` row is now trusted as final; a cached `unverified` row gets exactly one fresh live re-attempt** before falling back to it.

**Live confirmation against real production infrastructure, not just a unit test:**

| Case | Call 1 | Call 2 |
|---|---|---|
| *Fateh Chand v. Balkishan Dass* (real 1963 SC case, TICKET-18's known low-hit-rate example) | unverified, `recheck_count=1` | unverified, `recheck_count=2` (genuinely not indexed under this exact title — the recheck logic is running live each time, not silently trusting a stale cache) |

This confirms the fix is *live-executing*, not just passing an isolated mock — and honestly reports that this specific older case still doesn't verify even on retry (TICKET-18's "real gap, not flakiness" classification holds; the fix targets flakiness, not the separate older-case indexing gap).

**Confidence reporting added** (the other half of Phase 5's brief): `_best_match()`'s own word-overlap score — computed internally since Sprint 1 and simply discarded before this sprint — is now persisted as `match_confidence` (0.0–1.0) on every verified citation, plus a `recheck_count` for observability. Migration `0017_citations_match_confidence.sql`, additive, `None` for legacy pre-sprint rows.

**No verification was fabricated or the matching threshold loosened** — `_MATCH_CONFIDENCE_THRESHOLD` (0.6) is unchanged; this sprint only changed *how long a negative result is trusted*, never *how easy it is to get a positive one*.

---

# 7. Deliverable 6 — Pleading Outline Examples

Real, live-generated outputs from 6 representative scenarios (real production matters, real LLM calls) plus one clean before/after comparison isolating the corpus-expansion effect.

**The headline result — APP-01, before vs. after a fresh case analysis on the expanded corpus:**

| | Before (certification-round case analysis, pre-expansion corpus) | After (fresh case analysis + outline, this sprint's corpus) |
|---|---|---|
| Applicable statutes | 5/5 Consumer Protection Act sections (no CPC at all) | **`Code of Civil Procedure, 1908, Order XLI Rule 37`** ranked first, plus Order XLIV/XLV — the correct family of appellate provisions |
| Legal issue identified | "Applicability of Consumer Protection Act to High Court decree" (the exact TICKET-20 confusion) | **"Appeal against District Court decree"** — correct framing, no CPA confusion |
| Cause of action grounding | none (empty `possible_causes_of_action`) | **"Appeal against District Court decree"**, grounded in `Code of Civil Procedure, 1908, Order XLI Rule 37`, `grounded: true` |

This is a real, reproducible, direct resolution of a specific certification-round defect (TICKET-20), attributable to Phase 1 (corpus) + Phase 2 (top_k), demonstrated end-to-end through the new pipeline this sprint built.

**Across all 6 evaluated scenarios** (CIV-01, COM-01, PROP-03, RERA-01, APP-01, IA-01 — all `201 Created`, zero errors): every outline correctly produced all 8 fixed sections with substantive `content_plan` text, correctly passed through jurisdiction/limitation from the source case analysis verbatim, and correctly cross-checked cause-of-action statute references (e.g., IA-01's injunction cause of action correctly grounded in `Transfer of Property Act, 1882, Section 52` — the *lis pendens* provision, genuinely on point for restraining alienation during a pending suit).

**Two honest gaps from this same evaluation, not glossed over:**
- `applicable_case_law` came back **empty in all 6 outlines** — either appropriately conservative (the prompt explicitly permits an empty list) or a sign the fallback models this session landed on (mostly Groq's `llama-3.3-70b-versatile`, per §5) recall fewer real Indian precedents by name than Gemini did in the certification round. Not enough evidence this round to distinguish the two; flagged for the next evaluation round once model routing is more reliable.
- PROP-03's cause-of-action statute reference literally read `act: "not specified in retrieval context"` — a degenerate but *safely* handled output (correctly flagged `grounded: false`, never silently trusted), from the same weaker fallback model. Hard Rule 3 held even for malformed input; the underlying quality gap is a model-tier issue (§5), not a pleading_outline.py defect.

Full raw output for all 6 scenarios and the before/after comparison is preserved in the session's evaluation artifacts (`phase6_results.json`, `app01_fresh_case_analysis.json`, `app01_fresh_pleading_outline.json`) for direct review if needed.

---

# 8. Deliverable 7 — Updated Cost Analysis

Per the same "never estimate unavailable values" discipline as the certification round:

| Metric | Status |
|---|---|
| Corpus ingestion cost | **$0** — local `BAAI/bge-small-en-v1.5` embeddings (ADR-009), no API calls; confirmed by the ingestion run's own timing (embedding 1,911 chunks completed in seconds on CPU) |
| Pleading outline generation cost | **Not measured — still structurally unavailable**, unchanged from the certification round's finding (TICKET-23: `GenerationResult` still carries no token-count field). Not addressed this sprint — out of Phase 1's scope, tracked as an Enhancement. |
| Real LLM calls this sprint | 6 Phase 6 outline generations + 1 fresh case-analysis regeneration + 2 live citation-verifier re-checks — all real, all free-tier (Gemini flash/flash-lite, Groq), consistent with $0 actual spend, not independently itemized per-call |
| Free-tier headroom | **Newly-visible concern, not previously quantified**: this sprint's cumulative real-call volume (certification round + Phase 2/6 evaluation) pushed every real generation past `gemini-2.5-pro` *and*, in Phase 6, past `gemini-2.5-flash`/`flash-lite` too, landing on Groq far more often than the certification round saw. Worth capacity-planning before Sprint 3.6 Phase 2 assumes case-analysis-round quota margins hold for pleading-generation-round volumes too. |

---

# 9. Recommendation

## FOUNDATION REQUIRES FURTHER WORK

This is not a verdict that the foundation is weak — the evidence in §2–§7 shows real, measured, reproducible progress on every certification finding this sprint targeted, including one complete, demonstrated resolution of a specific defect (TICKET-20, APP-01). It reflects that "ready for pleading **drafting**" is a materially higher bar than "foundation Phase 1 was scoped to fully clear," and three concrete, bounded gaps remain between here and that bar:

1. **Corpus/retrieval recall is 73%, not resolved.** A real improvement (35%→73%) is not the same as a solved problem — over a quarter of real fact patterns still don't surface the legally correct act in the top 8. Pleading generation will assert statutory grounding more confidently than case analysis does; shipping before this closes further risks confidently-worded but thinly-grounded pleadings, the exact failure mode Sprint 3.6's own risk register (certification report §12) flagged in advance.
2. **Model-tier reliability got measurably worse this session, not better**, even with the transparency fix in place (§5) — the fix makes degradation visible, it does not make it less frequent. Before pleading drafting depends on this pipeline, the free-tier capacity question in §8 needs a real answer, not just visibility into the symptom.
3. **Case-law recall in the new pipeline is thin evidence, not validated.** Zero of 6 Phase 6 outlines proposed any case law at all — plausibly appropriate caution, plausibly a fallback-model gap, genuinely unresolved with this round's evidence. A pleading citing zero precedent where real precedent exists is a real quality gap, not caught by "no fabrication" alone.

**None of these block Sprint 3.6 Phase 2 from beginning design/scaffolding work** — the architecture (§4), model routing transparency (§5), and citation reliability (§6) are solid, tested, and ready to build on. They block treating a pipeline output as trustworthy enough to reach an actual drafted pleading in front of Nitesh without first: (a) a further corpus/retrieval pass targeting the specific still-uncovered scenarios named in §3, (b) resolving the capacity question in §8, and (c) a wider Phase 6-style evaluation round once (a) and (b) are addressed, specifically checking case-law recall quality with reliable top-tier model access.

---

# 10. Return

1. **Git commit hash:** none — no commit was made this session, per this session's standing rule of only committing when explicitly asked. `git status` shows this sprint's work as uncommitted, staged for review.
2. **Files changed:** see the enumerated list in §4/§5/§6 above; full `git status` available on request.
3. **Updated corpus statistics:** §2 (12 acts, 1,911 chunks, up from 6/633).
4. **Retrieval metrics:** §3 (recall@5 35%→62%, recall@8 →73%, real corpus-imbalance side effect measured and disclosed).
5. **Model routing summary:** §5 (degradation now explicit end-to-end; free-tier capacity concern newly surfaced).
6. **Citation reliability metrics:** §6 (root cause of TICKET-17 fixed and live-confirmed; TICKET-18's distinct older-case gap correctly still shows as unverified, not silently "fixed away").
7. **Pleading architecture summary:** §4.
8. **Recommendation for Sprint 3.6 Phase 2:** §9 — FOUNDATION REQUIRES FURTHER WORK, with three specific, bounded blockers named, none of which require redesigning what this sprint built.
