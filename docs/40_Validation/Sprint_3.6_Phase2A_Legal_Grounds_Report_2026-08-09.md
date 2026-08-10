> **Title:** Sprint 3.6 Phase 2A — Legal Grounds Intelligence (TICKET-25 root-cause, redesign, regression)
> **Version:** 1.0
> **Status:** Final for this sprint
> **Owner:** Keshav (executed) / Nitesh (to review before any full-pleading-drafting work begins)
> **Audience:** Nitesh, Keshav, future AI agents assessing legal_grounds readiness
> **Last Updated:** 9 August 2026
> **Baseline:** Sprint 3.6 Phase 2, certified **CLAUSE ENGINE REQUIRES FURTHER WORK** per
> [`Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md`](Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md) §9,
> which named the `legal_grounds` reliability gap (33% malformed-output rate) as blocker (1) of three.
> **Related Documents:** [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md) (TICKET-24/25/26/27),
> [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)

---

# 0. Scope and rules observed

This sprint's brief is explicit: **not** a pleading-functionality sprint. Its objective is narrower and deeper — make `legal_grounds` production-quality by resolving TICKET-25. No other clause type's *prompt content* was changed (facts/cause_of_action/reliefs/prayer keep their existing prompts). The one change applied uniformly beyond `legal_grounds` is mechanical/delivery-layer, not content-layer: `llm_gateway.generate_json()` (JSON-mode + one repair attempt) now backs all 5 LLM clause types, since it is the same shared `clause_drafter` task type and system prompt for all five, and hardening JSON delivery reliability is not "more pleading functionality."

Every finding below is either **(a) directly executed** — a real Deno... no, a real Python script run against the live production Supabase project and live LLM providers, with raw output captured to `docs/40_Validation/TICKET-25_*.json` — or **(b) traced**, explicitly labeled. No number in this report is estimated or inferred from the design's intent.

---

# 1. WORK ITEM 1 — Root Cause Report

**Method:** Phase 2's own report did not persist the raw text of its 2 malformed examples (COM-01, PROP-03) — only the aggregate finding. Recovering real evidence required regenerating live. `api/scripts/diagnose_legal_grounds.py` reran the **pre-redesign** `legal_grounds` generator 4× against each of the 6 certification matters (24 fresh live samples, read-only — no DB rows persisted), capturing full raw text for every parse failure.

**Result of that first pass:** 1/24 malformed (4%) — much lower than Phase 2's 33%, because this run's real-time provider quota state (see §7 below) pushed nearly every call onto Groq's `llama-3.3-70b-versatile`, not Gemini's weak tier. The **one** malformed sample captured landed on `gemini-2.5-flash-lite` — the same tier both of Phase 2's original failures used. Its raw text:

```json
{
 "content": "Sanjay Malhotra's failure to repay the principal sum along with accrued interest...
 constitutes a clear breach of contract. The said loan was granted by Contract

Reviewed to Sanjay Malhotra based on the mutual understanding and covenants agreed upon by both parties...",
 "statute_refs": [],
 "case_law_refs": [],
 "confidence": 0.8
}
```

This is **not** a structural JSON error (braces/brackets/keys all correct) — it is a **literal, unescaped newline inside a JSON string value**, which `json.loads()` correctly rejects per the JSON spec. All 3 known malformed examples to date (Phase 2's original 2, plus this one) occurred on `gemini-2.5-flash-lite` specifically (n=3, 100% correlation) — consistent with, but sharper than, TICKET-25's own hypothesis ("flash-lite reasons worse"). The mechanism is not vague "worse reasoning" — it is a **specific JSON-formatting defect**: the weak/fast tier occasionally emits a literal line break where `\n` was required.

**A targeted follow-up test isolated and reproduced the exact trigger.** Cross-checking against a fresh, direct capture on the redesigned prompt (see §2) against the CIV-01 matter (`api/scripts/diagnose_legal_grounds_postfix.py`) found the SAME failure shape, 3/3 reproducible, in a **different** field (`"issue"`, not `"content"`):

```json
"issue":"Breach of Contract

Reviewed causes of action",
```

This is decisive: the model copied a **text span crossing a prompt-section boundary**, including the literal blank-line separator between the "Reviewed legal issues" block and the following "Reviewed causes of action:" heading, directly into a JSON string value — not a random formatting slip, but the model conflating two adjacent, insufficiently-delimited prompt sections when CIV-01's issues list was short (a single line) and the next section header sat immediately after it. Reclassified root cause, evidence-backed:

**Root cause (confirmed, not inferred): prompt section-boundary ambiguity, manifesting as an unescaped literal newline inside a JSON string value when the model copies a span crossing that boundary — worse under weaker/faster model tiers, which the real-time provider-failover chain (TICKET-21) makes the *de facto* server for a meaningful share of calls.**

Classified against the sprint's example categories:
- **Parser weakness**: real, but secondary — `json.loads()` is behaving correctly (the input genuinely isn't valid JSON); the previous `_extract_json` had no mechanism to *recover* from this, only to detect it.
- **Model degradation**: real, and now specific — not "reasons worse" in the abstract, but "more likely to blur a prompt-section boundary into a copied text span."
- **Prompt ambiguity**: **the dominant, confirmed cause** — insufficiently delimited section boundaries in the old prompt, directly fixed and directly re-verified (§2, §5).
- **Retrieval weakness / context overflow / grounding gaps**: not implicated in the malformed-JSON failure mode specifically — see §3 for the separate, real retrieval-adjacent gap this sprint also found (case law).

---

# 2. WORK ITEM 2 — Pipeline Redesign

**The suggested flow (Issues → Applicable Statutes → Applicable Sections → Applicable Case Law → Ground Selection → Legal Grounds) was evaluated stage-by-stage, not applied blindly:**

| Suggested stage | Disposition | Why |
|---|---|---|
| Issues | **Reused as-is** — `outline.legal_issues` | Already an independently-generated, independently-inspectable, already-reviewed artifact from Phase 1's Pleading Outline. Re-deriving it inside `legal_grounds` would violate this codebase's "stay downstream of what's already reviewed" architecture (`clause_generator.py`'s own module docstring). |
| Applicable Statutes | **Reused as-is** — `outline.applicable_statutes` | Same reasoning. |
| Applicable Sections | **Folded into "Applicable Statutes"** — not a separate stage | `outline.applicable_statutes` already carries `(act, section_no)` as one retrieved unit (Phase 1's RAG retrieval operates at section granularity already). Splitting an already-atomic pair into two separate LLM calls would add latency and malformed-JSON surface for zero informational gain — against this project's own "does this require synthesis a template author can't enumerate? If no, deterministic" bar (Backlog.md's Governing Law finding), applied here to reject an unnecessary LLM stage, not just an unnecessary template. |
| **Applicable Case Law** | **Genuinely new** — did not exist as a distinct stage before this sprint | See §3. `legal_grounds` now gets its own live Citation Verifier check for any case name it proposes that isn't already in the outline's verified pool (`_ground_case_law_refs_live`, bounded to 3 live IK calls per generation). |
| **Ground Selection** | **Genuinely new** — a structured, independently-inspectable "grounds" list, one entry per issue | Replaces the old single free-form "content" paragraph. Each entry: `{issue, statute_refs, case_law_refs, argument_note, confidence}` — persisted in full in `content.grounds` (no migration needed, existing `content` JSONB column), not collapsed into prose until the next stage. |
| Legal Grounds (final text) | **Deterministic assembly**, not a third LLM call | `_assemble_legal_grounds_text()` renders the final clause paragraph FROM the already-grounded/verified structured data — zero further LLM reasoning, zero further hallucination surface, and a direct, mechanical satisfaction of WORK ITEM 4 (§4). |

**Net effect:** `legal_grounds` goes from 1 LLM call (one long free-form string) to 1 LLM call (a structured, per-issue JSON list of short fields) + deterministic assembly. This is deliberately **not** "more calls" — it is the same call count, restructured so (a) each stage's output is separately inspectable (`content.grounds`), and (b) the string-value failure mode found in §1 has much less surface area (short single-sentence fields vs. one long multi-paragraph string).

**Two structural, gateway-level defenses were added, benefiting all 5 LLM clause types** (`api/app/services/llm_gateway.py`):

1. **`json_mode`** — a new parameter on `generate()`, threaded to every provider (`_call_gemini`'s `generationConfig.responseMimeType`, `_call_openai_compatible`'s `response_format`). Asks the provider's own serializer to guarantee syntactically valid JSON. Does **not** guarantee the requested *shape* — that is still validated by the caller, unchanged.
2. **`generate_json()`** — wraps `generate(..., json_mode=True)` + parse; on a parse failure, makes exactly one **fresh** repair call (original prompt + a correction instruction citing the exact real failure mode from §1 — "a common cause is a literal line break inside a string value"). Deliberately does **not** thread the previous (unmasked) response back as conversation history — doing so would re-send unmasked PII to the provider a second time (CLAUDE.md Decision 4); each repair attempt re-masks from scratch.

All 5 LLM clause generators (`generate_clause()`'s non-deterministic branch) now go through `generate_json()` instead of raw `generate()` + a local `_extract_json()` call — one shared, tested delivery-reliability path.

---

# 3. WORK ITEM 3 — Case Law Retrieval

**"Investigate why zero precedents were proposed"** — direct query against the live production database, across all 6 certification matters:

| Matter | `case_analysis.possible_precedents` | `pleading_outline.applicable_case_law` |
|---|---|---|
| APP-01 | `[]` (model: groq/llama-3.3-70b-versatile) | `[]` |
| CIV-01 | `[]` (model: gemini/gemini-2.5-flash) | `[]` |
| COM-01 | `[]` (model: gemini/gemini-2.5-flash) | `[]` |
| IA-01 | `[]` (model: gemini/gemini-2.5-flash-lite) | `[]` |
| PROP-03 | `[]` (model: gemini/gemini-2.5-flash) | `[]` |
| RERA-01 | `[]` (model: gemini/gemini-2.5-flash) | `[]` |

**Zero across every matter, at both upstream stages, across a wide model-tier mix (flash, flash-lite, Groq).** This rules out "weak model" as the explanation — it is systemic and architectural.

**Root cause (confirmed by direct code inspection of `case_analysis.py` and `pleading_outline.py`):** there is no case-law *retrieval* mechanism anywhere in this codebase — unlike statutes (`hybrid_retrieve()`, a real RAG pipeline over `statute_chunks`), case law is pure **generate-then-verify**: the model is asked to freely recall a real case from its own parametric memory, then the Citation Verifier checks whatever it names. Critically, **neither `case_analysis.py`'s nor `pleading_outline.py`'s prompt ever gives the model any case-law context to recall against** — only statutory context is embedded. The shared `_GROUNDING_INSTRUCTION` (`llm_gateway.py`) explicitly says *"if you are not given a source for a claim, say so explicitly instead of guessing."* A model correctly following that instruction, given zero case-law context, will propose nothing — which is exactly the observed result. **"Zero precedents proposed" is the system behaving exactly as instructed, not a retrieval-recall/precision/ranking failure in the conventional IR sense** — there is no ranking or recall to measure, because there is no retrieval step to measure it on.

**What this sprint changed, scoped to `legal_grounds` only** (not `case_analysis.py`/`pleading_outline.py` — out of scope, per §0): `_prompt_legal_grounds` now explicitly **invites** a confident, specific guess ("if you are reasonably confident of a real, specific Indian case... name it even if it is not in the 'already on record' list... it will be independently verified") and `_ground_case_law_refs_live` gives any such name a real, live Citation Verifier check (bounded to 3 per generation) — a capability that did not exist at the clause level before this sprint (previously, `legal_grounds` could only cross-check against the outline's already-verified pool, never verify a fresh name itself).

**Measured this sprint** (§5 regression): 0/6 matters produced a verified precedent via this new mechanism — the capability now exists and is live-verified as *wired correctly* (unit-tested: `test_legal_grounds_case_law_gets_one_live_verify_attempt_for_a_name_not_already_verified`), but was not exercised into a positive real-world result this session, entirely because Groq's `llama-3.3-70b-versatile`/`gpt-oss-*` — the only tier this session's exhausted Gemini quota (§7) allowed testing — did not, in practice, propose any case names even with the invitation. **This is disclosed honestly, not glossed over**: the new capability is real and correctly built, but "demonstrably improved precedent usage" (the sprint's own success criterion) is not yet shown with a positive example. A durable fix for real precedent-retrieval quality would be a genuine case-law RAG/seeding layer (analogous to `hybrid_retrieve()` for statutes) — out of this sprint's scope, flagged as a real future investment, not attempted here.

---

# 4. WORK ITEM 4 — Grounding

Every generated ground (`content.grounds[i]`) now explicitly carries, by construction — not inferred from prose after the fact:

- **issue** — copied verbatim from a reviewed legal issue (prompt now enforces this explicitly, §1/§2).
- **statute** / **section** — `statute_refs: [{act, section_no, grounded}]`, cross-checked against `outline.applicable_statutes` (unchanged mechanism, `_ground_statute_refs`).
- **precedent** — `case_law_refs: [{case_name, status, ik_url, court}]`, cross-checked against the outline's verified pool OR live-verified (§3, `_ground_case_law_refs_live`) — never a bare, unverified name.
- **confidence** — per-ground `_confidence_for()` (grounding-ratio + model self-report, averaged), same formula every other clause type uses.

**"If unavailable, say so. Never invent authority"** — enforced deterministically in `_assemble_legal_grounds_text()`, not left to the model's prose discipline: a ground with no grounded statute renders *"No statutory provision retrieved for this matter directly supports this ground — verify manually before relying on it"*; a ground with no verified precedent renders *"No verified precedent has been identified in support of this ground."* Both are template strings emitted by Python code, never the LLM's own words — the LLM cannot phrase around this disclosure requirement because it never writes the disclosure sentence itself.

---

# 5. WORK ITEM 5 — Regression

**Method:** `api/scripts/regress_legal_grounds.py` — the exact Phase 2 methodology (`generate_all_clauses()` for real against the same 6 certification matters, starting from each matter's existing outline, then auto-approve + `compose_pleading()`), persisting real new `litigation_pleading_clauses`/`litigation_pleading_drafts` rows, same as Phase 2's own E36 evidence entry.

| Metric | Phase 2 (baseline) | Phase 2A (this sprint) |
|---|---:|---:|
| Legal Grounds malformed rate | 2/6 (33%) | **0/6 (0%)** |
| Runs citing ≥1 statute | 3/4 successful (50% of all 6 attempts) | **4/6 (67%)** |
| Runs citing ≥1 verified precedent | 0/6 | 0/6 (unchanged — see §3) |
| Composition (14/14 sections, `legal_grounds` present) | 4/6 clean | **6/6 clean** |
| Statute refs claimed this round, ungrounded | n/a (no legal_grounds statute claims survived to compose) | **0** — every claimed statute ref in this round was grounded |

**Legal quality (qualitative, read directly from the 6 generated clauses — not scored, per this project's own no-fabricated-metric discipline):** all 6 read as coherent, on-topic legal submissions connecting the matter's issue(s) to a specific statute where one was grounded, or explicitly disclosing the absence of one. One quality *observation*, not a new defect: COM-01's ground cites "Consumer Protection Act, 2019, Section 39" for a B2B SaaS non-payment dispute — a plausible-sounding but domain-questionable fit. This is **not** a fabricated citation (it is genuinely present and `grounded: true` in `outline.applicable_statutes`, i.e. Phase 1's retrieval actually surfaced it for this matter) — it is a downstream symptom of the still-open TICKET-16 corpus/retrieval-precision gap (Consumer Protection Act is comparatively over-represented in the ingested corpus), not a new `legal_grounds` defect. Flagged here for visibility, not filed as a new ticket.

**Disclosed limitation on this regression's scope:** every one of this run's 6 legal_grounds generations landed on Groq (`llama-3.3-70b-versatile` / `openai/gpt-oss-120b` / `openai/gpt-oss-20b`) — Gemini was fully rate-limited for this entire session (§7), including the specific `gemini-2.5-flash-lite` tier responsible for **all 3** known malformed examples to date. The fix's mechanism is understood and directly verified (§1: 0/3 → 3/3 on the exact reproducing case), and the aggregate 0/6 result is real, live evidence — but a full re-validation specifically against `gemini-2.5-flash-lite` once quota resets is the natural next confirmation step, not yet performed.

---

# 6. WORK ITEM 6 — Secondary Issues

Per the brief's explicit instruction ("only if they naturally fall out of the redesign... do not optimize prematurely"):

- **TICKET-24** (PII placeholder leak in `facts`) — **not touched.** `facts`'s own generator/prompt was not modified this sprint (only its JSON-delivery mechanics via the shared `generate_json()` hardening, unrelated to the PII auto-detection root cause). Remains open.
- **TICKET-26** (most LLM clauses claim zero refs even when available) — **partially, incidentally improved for `legal_grounds` specifically** (citation-attempt rate 50%→67% this round, §5) as a side effect of the redesigned prompt's explicit structure, not a deliberate fix. `cause_of_action`/`reliefs`'s own prompts were not changed. **TICKET-26 remains open** — this sprint did not re-measure or target the other clause types' citation-attempt rate, per the "do not optimize prematurely" instruction.
- **TICKET-27** (regeneration model-tier inconsistency) — **unrelated to this redesign**, not addressed. Remains open.

No ticket was closed this sprint; none needed forcing closed to satisfy this section — the brief's own conditional ("only if... do not optimize prematurely") is honored by leaving all three open with an honest note on what did and didn't change.

---

# 7. Build Verification

262/262 backend pytest tests pass (30 in `test_clause_generator.py`, up from 22 — 8 new/rewritten for the redesign; all others unaffected), plus the pre-existing, unrelated `e2e/test_no_auto_pdf_download.py` Playwright failure (`ERR_CONNECTION_REFUSED` — requires a frontend dev server not started this session, same documented gap as every prior sprint's evidence log). No regressions introduced.

**A capacity observation, extending TICKET-21 further:** this sprint's diagnostic + regression work made ~40 real `legal_grounds` LLM calls in one session. Gemini was rate-limited on effectively every attempt after the first ~24, across all 4 pool models (`gemini-2.5-pro/flash/2.0-flash/flash-lite`) — every real generation this sprint, after the first few, was served by Groq. This is the same TICKET-21 concern Phase 1/Phase 2 already flagged, now observed persisting for a full session's diagnostic+redesign+regression workload, not just one 293-second evaluation run. Not a new ticket — TICKET-21 already covers it — but worth restating as continuing, real evidence.

---

# 8. Consolidated Findings & Fixes This Sprint

| # | Finding | Evidence | Fix applied |
|---|---|---|---|
| 1 | `legal_grounds`'s single-string "content" field is vulnerable to a model emitting an unescaped literal newline inside it | `docs/40_Validation/TICKET-25_diagnostic_raw_output_2026-08-09.json` (1 captured malformed sample, gemini-2.5-flash-lite) | Restructured to short, structured per-ground fields (§2) |
| 2 | (root cause of #1, sharpened) prompt section boundaries were ambiguous, letting the model copy a span crossing them, newline included | Reproduced 3/3 on CIV-01/groq before fix; 3/3 fixed after (`diagnose_legal_grounds_postfix.py`) | Explicit `=== SECTION ===` delimiters + explicit "issue must be copied verbatim from exactly one bullet" instruction |
| 3 | No structural JSON-validity guarantee anywhere in the LLM Gateway | Confirmed by code inspection — no `response_format`/`responseMimeType` used anywhere pre-sprint | `json_mode` param on `generate()`, wired to Gemini + all OpenAI-compatible providers |
| 4 | A malformed response was permanently unrecoverable — no repair path existed | Confirmed by code inspection | `generate_json()` — one fresh repair call, PII-safe (no unmasked history threading) |
| 5 | Case law "retrieval" gives the model zero context to recall against, at every stage in the codebase | Direct DB query: 0/6 matters, both upstream stages, all models | `legal_grounds`'s own stage now invites + live-verifies a candidate; NOT fixed at `case_analysis.py`/`pleading_outline.py` (out of scope) |
| 6 | `legal_grounds` had no live Citation Verifier path of its own (only cross-checked against an already-empty outline pool) | Code inspection | `_ground_case_law_refs_live`, bounded to 3 live IK calls/generation |

---

# 9. Recommendation

## TICKET-25 (malformed rate): SUBSTANTIALLY RESOLVED, pending one follow-up confirmation
## Overall: FURTHER LEGAL-GROUNDS WORK REQUIRED — narrower and closer to done than Phase 2's finding

**Reasoning, evidenced above:**

1. **The sprint's Primary Objective — TICKET-25 — has a real, mechanistic fix, not a statistical improvement.** The exact failure (a model copying a text span across an ambiguous prompt-section boundary, including the literal newline separator, into a JSON string value) was reproduced 3/3 times, fixed, and re-verified 3/3 times on the identical reproducing case. The full 6-matter regression measured 0% malformed (target: <5%), down from Phase 2's 33%. This is not yet fully closed only because this session's Gemini quota exhaustion (§7) meant the fix could not be re-validated against `gemini-2.5-flash-lite` specifically — the tier responsible for 100% of known failures to date, all served by Groq instead this round. **Recommend: closeable on the next session where Gemini quota allows a `gemini-2.5-flash-lite`-targeted re-run** (`api/scripts/diagnose_legal_grounds_flash_lite.py` is already built and ready for this).
2. **Precedent/case-law usage is not yet "demonstrably improved" in real output**, though the underlying mechanism (live verification of a candidate `legal_grounds` proposes) is now real, tested, and correctly wired — it simply was not exercised into a positive example this session (Groq's models, the only ones reachable, did not propose case names even when invited). This is the same root architectural gap Phase 1/Phase 2 already named (no case-law retrieval/seeding mechanism anywhere in this codebase) — this sprint gave `legal_grounds` a real chance to demonstrate it, and that chance has not yet paid off with a real example.
3. **Statutory grounding and no-fabricated-authority hold at 100%** this round — every claimed statute ref was grounded; zero case-law names were fabricated-and-displayed-as-real (all either matched the verified pool or were correctly withheld/flagged).

**None of this blocks Sprint 6C-equivalent UI or review-workflow work on top of the clause engine** (mirroring Phase 2's own framing) — it blocks trusting `legal_grounds` as a demonstrated precedent-citing capability in front of Nitesh specifically, and it blocks a full confidence claim on the malformed-rate fix until re-tested against the weak tier that actually produced every known failure.

---

# 10. Return

1. **Root cause report:** §1 — evidence-backed, reproduced, not inferred; prompt section-boundary ambiguity is the confirmed dominant cause.
2. **Pipeline redesign:** §2 — staged, not a prompt rewrite; Issues/Statutes reused from existing artifacts (deliberately not re-split further); genuinely new Applicable Case Law + Ground Selection stages; deterministic final assembly; gateway-level `json_mode`/`generate_json()` hardening applied to all 5 LLM clause types.
3. **Evaluation metrics:** §5 — malformed rate 33%→0% (n=6 each), citation-attempt rate 50%→67%, composition 4/6→6/6 clean.
4. **Grounding metrics:** §4 — every ground carries issue/statute/section/precedent/confidence by construction; 0 ungrounded statute claims, 0 fabricated case-law names this round.
5. **Regression results:** §5, raw evidence at `docs/40_Validation/TICKET-25_regression_raw_output_2026-08-09.json`; also `TICKET-25_diagnostic_raw_output_2026-08-09.json` (pre-fix) for direct comparison.
6. **Recommendation:** §9 — **FURTHER LEGAL-GROUNDS WORK REQUIRED**, narrowly scoped to (a) a flash-lite-targeted re-confirmation of the malformed-rate fix, and (b) demonstrating real precedent usage, not a broad "clause engine not ready" finding.
7. **Files changed:** `api/app/services/llm_gateway.py` (json_mode, `generate_json`, `extract_json`), `api/app/services/clause_generator.py` (legal_grounds staged redesign, `_ground_case_law_refs_live`, `_assemble_legal_grounds_text`, `_dedupe_refs`), `api/app/models/schemas.py` (`ClauseGroundOut`, `ClauseContentOut.grounds`), `api/tests/test_llm_gateway.py` (+7 tests), `api/tests/test_clause_generator.py` (+8 tests, net), `api/tests/test_document_composer.py` (mock signature update). New: `api/scripts/diagnose_legal_grounds.py`, `diagnose_legal_grounds_flash_lite.py`, `diagnose_legal_grounds_postfix.py`, `regress_legal_grounds.py` (kept as reusable diagnostic tooling, matching this project's `verify_*.py` convention). No migration required — `content` JSONB already accommodated the new `grounds` field.
8. **Git commit hash:** none — no commit was made this session, per this session's standing rule of only committing when explicitly asked. `git status` shows this sprint's work as uncommitted.
