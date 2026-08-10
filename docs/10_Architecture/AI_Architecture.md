> **Title:** AI Architecture
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Architects, engineers, future AI agents working on LLM/RAG/citation code
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for LLM gateway, retrieval, citation verification, PII masking, and prompt-isolation architecture
> **Supersedes:** `90_Historical/Original_Technical_Requirements.md` §3.1–§3.3, `90_Historical/Original_Technical_Requirements.md` §3.5
> **Related Documents:** [`Engineering_Architecture_Handbook.md`](Engineering_Architecture_Handbook.md), [`../30_Implementation/Technical_Design/Litigation_Module_Architecture.md`](../30_Implementation/Technical_Design/Litigation_Module_Architecture.md), ADRs [003](../30_Implementation/ADR/ADR-003-multi-provider-llm-failover.md), [004](../30_Implementation/ADR/ADR-004-mandatory-pii-masking.md), [005](../30_Implementation/ADR/ADR-005-zero-hallucination-citation-gate.md), [008](../30_Implementation/ADR/ADR-008-prompt-injection-boundary-isolation.md)

---

# AI Architecture

## LLM Gateway

Single interface `generate(prompt, task_type)` in `api/app/services/llm_gateway.py`. Routes on rate-limit/error through a fixed provider order: **Gemini 2.5 Flash → Groq (Llama-3.3-70B) → SambaNova → Cerebras** (`CLAUDE.md` Decision 3; no local Ollama — infra does not support it). As of Build Tracker E24, each provider tier itself holds an ordered pool of pinned models (4 Gemini, 5 Groq, 1 SambaNova, 3 Cerebras) tried before escalating to the next provider, with per-model transient retry and position logging. Per-module system prompts exist for each task type (contract drafter, pleading drafter, consulting analyst, etc.) — see [ADR-003](../30_Implementation/ADR/ADR-003-multi-provider-llm-failover.md).

## PII Masking — mandatory, before every external call

Because no local model is available, every prompt leaves the advocate's environment for a third-party cloud. `api/app/services/pii_mask.py` masks party names, addresses, phone numbers, and Aadhaar/PAN patterns into stable placeholders (`PARTY_A`, `ADDR_1`, ...) before any external LLM call, and unmasks only on local client rendering. The masking map is stored per-matter in Postgres (`pii_masks` table) and is never sent to the LLM. This is non-negotiable per `CLAUDE.md` Decision 4 — see [ADR-004](../30_Implementation/ADR/ADR-004-mandatory-pii-masking.md).

## RAG Retriever (statute knowledge base)

`api/app/services/retrieval.py` runs hybrid retrieval over `statute_chunks`: dense vector search (pgvector) combined with PostgreSQL `tsvector` keyword search, fused via Reciprocal Rank Fusion. Corpus is bare acts ingested from India Code (PyMuPDF, section-level chunking), plus RERA state rules from official portals where relevant. Context is capped at ~5 retrieved chunks per prompt. The retrieval promise, stated in the system prompt and enforced by construction: cite only what retrieval provides; if nothing matches, say manual verification is required rather than guessing. This subsystem is shared, not module-specific — promoted to shared infrastructure serving both Litigation and Consulting per `Litigation_Module_Architecture.md` §14.

## Citation Verifier — the product's core differentiator

Every case citation a model proposes goes through this state machine (`api/app/services/citations.py`) before it can ever render as a link:

```
LLM proposes case (name / citation / year)
   → Indian Kanoon /search (title + citation + court filter)
      → confident match found?
           YES → fetch doc ID → https://indiankanoon.org/doc/{id}/
                 cache {case, ik_id, url, court, date} in citations/case_citations table
           NO  → retry with normalized query (party names only)
                 → still no match → render ⚠ UNVERIFIED (grey, no link,
                   "confirm manually — may exist only on SCC/Manupatra")
```

**Enforced in code, not in the prompt**: the renderer refuses to output a live hyperlink unless a verified `ik_id` exists in the database. This is the literal implementation of the Product Constitution's Citation Gate hard rule and the single most load-bearing piece of architecture in the product — see [ADR-005](../30_Implementation/ADR/ADR-005-zero-hallucination-citation-gate.md). Verified citations are cache-first to conserve Indian Kanoon API quota; a nightly job re-checks cached URLs to catch dead links (per TRD §3.3 design — verify current build status in Build Tracker before relying on the nightly job as shipped).

## Prompt-Injection Boundary Isolation (SEC-01)

All LLM entry points wrap user-supplied content (fact patterns, amendment instructions) in explicit XML boundary tags (`<user_facts>`, `<user_instruction>`, `<user_amendment>`) with an explicit system-prompt instruction that content inside these tags is data, never commands that can override system instructions or statutory limits. Confirmed built across all LLM entry points per Build Tracker E21. See [ADR-008](../30_Implementation/ADR/ADR-008-prompt-injection-boundary-isolation.md).

## Query Validator

Lightweight LLM classification step at the entry to Litigation and Consulting flows: `{is_legal_matter, domain, urgency, missing_facts[]}`. If facts are insufficient, the system asks targeted follow-ups before opining, mirroring how the advocate himself works, rather than generating a premature answer.

## Auditability

Every AI output is stored with its prompt (post-masking), the model that answered, and its retrieval sources, so any output can be reconstructed and explained after the fact. This is a hard rule in the Product Constitution and is implemented via the `draft_versions.masked_prompt` field and equivalent fields on litigation pleading records.
