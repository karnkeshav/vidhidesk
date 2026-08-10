> **Title:** Engineering Architecture Handbook
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Architects, engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes — the top-level architecture reference for VidhiDesk. Second in precedence only to the [Product Constitution](../00_Product/Product_Constitution.md).
> **Supersedes:** `90_Historical/Original_Technical_Requirements.md` §1 and §3 (system architecture and subsystems)
> **Related Documents:** [`Business_Architecture.md`](Business_Architecture.md), [`AI_Architecture.md`](AI_Architecture.md), [`Runtime_Architecture.md`](Runtime_Architecture.md), [`../20_Engineering/Technical_Standards.md`](../20_Engineering/Technical_Standards.md), [`../30_Implementation/ADR/`](../30_Implementation/ADR/)

---

# Engineering Architecture Handbook

**A note on this document's provenance.** No standalone "Engineering Architecture Handbook" existed in this repository before this refactor. This document was compiled — not invented — from architecture content already approved and scattered across `90_Historical/Original_Technical_Requirements.md` §1/§3, `30_Implementation/Technical_Design/Litigation_Module_Architecture.md`, and the confirmed-built subsystem list in `30_Implementation/Build_Tracker.md` §6. Every claim below traces to one of those sources. Where this handbook and a source document disagree on current state, the Build Tracker's evidence-tagged status wins (see [Documentation Precedence Policy](../README.md#documentation-precedence-policy)).

This handbook is the index. Detail lives in three companion documents, split along the seams the system actually has:

- **[Business_Architecture.md](Business_Architecture.md)** — the domain model: matters, modules, jurisdiction, roles.
- **[AI_Architecture.md](AI_Architecture.md)** — the LLM gateway, RAG retrieval, citation verification, PII masking, prompt isolation.
- **[Runtime_Architecture.md](Runtime_Architecture.md)** — hosting topology, request flow, deployment targets.

## System shape, at a glance

```
Frontend (Next.js, Vercel)
        │ HTTPS/JSON
        ▼
Backend (FastAPI, Render)
   ├─ LLM Gateway ─────────► Gemini → Groq → SambaNova → Cerebras (failover)
   ├─ RAG Retriever ───────► pgvector + tsvector hybrid search over statute_chunks
   ├─ Citation Verifier ───► Indian Kanoon API, cache-first
   ├─ PII Masker ──────────► runs before every external LLM call
   └─ Template Engine ─────► Jinja2 → python-docx → LibreOffice → PDF
        │
        ▼
Data (Supabase: Postgres + pgvector + Auth + Storage)
```

This is the same shape described in `90_Historical/Original_Technical_Requirements.md` §1, with two corrections reflecting what actually shipped: Ollama was dropped from the LLM chain (SambaNova and Cerebras took its place — see [ADR-003](../30_Implementation/ADR/ADR-003-multi-provider-llm-failover.md)), and ChromaDB was never adopted (pgvector is the only vector store in production).

## The five subsystems every module depends on

Per Build Tracker §6, these are confirmed built and shared across Contracts (live) and Litigation (architected):

| Subsystem | Responsibility | Detail |
|---|---|---|
| LLM Gateway | Routes generation requests through the provider failover chain; per-task-type system prompts | [AI_Architecture.md](AI_Architecture.md) |
| RAG Retriever | Hybrid (vector + keyword) search over the statute corpus | [AI_Architecture.md](AI_Architecture.md) |
| Citation Verifier | Resolves proposed case citations against Indian Kanoon; gates hyperlink rendering | [AI_Architecture.md](AI_Architecture.md), [ADR-005](../30_Implementation/ADR/ADR-005-zero-hallucination-citation-gate.md) |
| PII Masker | Masks identifying data before any external LLM call, unmasks on render | [AI_Architecture.md](AI_Architecture.md), [ADR-004](../30_Implementation/ADR/ADR-004-mandatory-pii-masking.md) |
| Template Engine | Jinja2 `.docx` skeletons + JSON schema-driven intake, versioned drafts | [Business_Architecture.md](Business_Architecture.md), [ADR-002](../30_Implementation/ADR/ADR-002-deterministic-document-structure.md) |

## Non-functional posture

Cost, availability, and security targets are documented in [`../20_Engineering/Technical_Standards.md`](../20_Engineering/Technical_Standards.md) (extracted from TRD §5/§6). The zero-recurring-cost constraint is treated there as a primary architectural driver, not an incidental requirement — see [ADR-009](../30_Implementation/ADR/ADR-009-freeware-zero-cost-constraint.md).

## Architecture decisions

Every named decision referenced above (and several more) has a standalone record in [`../30_Implementation/ADR/`](../30_Implementation/ADR/), with its context, the alternative considered, and consequences. That folder — not this handbook — is the place to look for *why* a given subsystem is shaped the way it is; this handbook only describes *what* exists.
