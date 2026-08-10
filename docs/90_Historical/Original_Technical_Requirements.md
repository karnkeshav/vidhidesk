> **Title:** Original Technical Requirements Document (TRD)
> **Version:** 1.0 (as originally issued)
> **Status:** Historical
> **Owner:** Keshav
> **Audience:** Historical record for engineers, architects, future AI agents
> **Last Updated:** 23 July 2026 (frozen; not maintained further)
> **Canonical Reference:** No — see Superseded By
> **Supersedes:** N/A (first technical requirements document)
> **Superseded By:** [`10_Architecture/Engineering_Architecture_Handbook.md`](../10_Architecture/Engineering_Architecture_Handbook.md), [`20_Engineering/Technical_Standards.md`](../20_Engineering/Technical_Standards.md), [`20_Engineering/Database_Architecture.md`](../20_Engineering/Database_Architecture.md)
> **Reason:** Build Tracker §1/§8.2 records that the live schema and subsystem set have outgrown this document (e.g. Ollama was dropped from the LLM chain in favor of SambaNova/Cerebras per `CLAUDE.md` Decision 3; ChromaDB was never adopted; ~10 new tables/columns exist beyond §4's list). Preserved verbatim as the original design intent and rationale record.
> **Related Documents:** [`Original_Scope_of_Work.md`](Original_Scope_of_Work.md), [`Original_Implementation_Plan.md`](Original_Implementation_Plan.md)

---

# Technical Requirements Document (TRD)
## Project: VidhiDesk — Phase 1
**Version:** 1.0 | **Date:** 23 July 2026
**Hard constraint:** 100% free / open-source / free-tier tooling. Only pre-procured paid asset: the **Indian Kanoon API** key held by the Product Owner.

---

## 1. System Architecture (High Level)

```
┌────────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js + Tailwind + shadcn/ui (Vercel free)   │
│  Dashboard → 4 module workspaces (chat + forms + viewer)   │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTPS/JSON
┌──────────────────────────▼─────────────────────────────────┐
│  BACKEND — Python FastAPI (Render/HF Spaces free tier)     │
│  ┌──────────────┐ ┌───────────────┐ ┌───────────────────┐  │
│  │ Orchestrator │ │ Citation      │ │ Template Engine   │  │
│  │ (LangChain / │ │ Verifier      │ │ (Jinja2 →         │  │
│  │  plain code) │ │ (IK API)      │ │  python-docx)     │  │
│  └──────┬───────┘ └───────┬───────┘ └───────────────────┘  │
│         │                 │                                │
│  ┌──────▼───────┐  ┌──────▼────────┐                       │
│  │ LLM Gateway  │  │ RAG Retriever │                       │
│  │ Gemini free →│  │ pgvector /    │                       │
│  │ Groq → Ollama│  │ ChromaDB      │                       │
│  └──────────────┘  └───────────────┘                       │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  DATA — Supabase free tier (Postgres + pgvector + Auth +   │
│  Storage) · Statute corpus from India Code (free PDFs)     │
│  · Indian Kanoon API (judgments)                           │
└────────────────────────────────────────────────────────────┘
```

## 2. Technology Stack (all free)

| Layer | Choice | Why / Free status |
|---|---|---|
| Frontend | **Next.js 14 + TypeScript, Tailwind, shadcn/ui** | Open source; Vercel Hobby tier hosts it free |
| Backend | **Python 3.11 + FastAPI** | Open source; best ecosystem for RAG/doc generation |
| Backend hosting | **Render free tier** (or Hugging Face Spaces / Railway trial) | Free; accepts cold starts for a single-user tool |
| Database + Auth + Files | **Supabase free tier** (500 MB Postgres, pgvector, Auth, 1 GB storage) | One free service covers DB, vectors, login, file storage |
| Vector search | **pgvector** on Supabase (primary); **ChromaDB** local for dev | Free, no extra service |
| Embeddings | **BAAI/bge-small-en-v1.5** or **all-MiniLM-L6-v2** via sentence-transformers | Free, local, small enough for free-tier RAM |
| LLM (primary) | **Google Gemini 2.5 Flash — free API tier** | Strong reasoning + long context; free tier rate limits acceptable for single user |
| LLM (fallback) | **Groq free tier (Llama-3.3-70B)**; **Ollama (Llama-3.1-8B)** locally for dev/offline | Redundancy against rate limits; zero cost |
| Doc generation | **Jinja2 → python-docx** (docx) · **docx→pdf via LibreOffice headless** | Free, produces real Word files the lawyer can edit |
| OCR / PDF parsing (statutes) | **PyMuPDF + pytesseract** | Free ingestion of India Code bare-act PDFs |
| Judgment source | **Indian Kanoon API** (procured) | Search + fetch by doc ID; canonical hyperlink source |
| CI/CD & repo | **GitHub free + GitHub Actions free minutes** | — |
| Monitoring | **Sentry free tier / plain logging** | — |

> **LLM note:** free tiers carry rate limits and (for Gemini free tier) possible data-usage terms. Mitigation: single-user volume is low; the gateway retries across providers; genuinely sensitive matters can be routed to local Ollama. Revisit if the tool is ever commercialized.

## 3. Core Subsystems

### 3.1 LLM Gateway
- Single interface `generate(prompt, task_type)`; routes to Gemini → Groq → Ollama on failure/rate-limit.
- Per-module system prompts (litigation analyst, contract drafter, RERA specialist, consulting analyst).
- All prompts instruct: *cite only what retrieval provides; never invent case names.*

### 3.2 RAG Retriever (Statute Knowledge Base)
- **Corpus:** bare acts downloaded from India Code (free, official) per SOW Appendix B; RERA state rules from official state portals.
- **Pipeline:** PDF → text (PyMuPDF) → section-level chunking (each section = one chunk with act name, section no., year metadata) → embed → pgvector.
- **Query:** user facts → hybrid search (vector + keyword on section metadata) → top-k sections fed to LLM as the only permissible statutory grounding.
- Statutes are versioned; BNS/BNSS/BSA and IPC/CrPC/Evidence coexist with an "offence date" disambiguation rule.

### 3.3 Citation Verifier — the product's heart
Every case citation follows this state machine before display:

```
LLM proposes case (name / citation / year)
   → IK API /search (title + citation + court filter)
      → exact/high-confidence match?
           YES → fetch doc ID → attach https://indiankanoon.org/doc/{id}/
                 store {case, ik_id, url, court, date} in citations table
           NO  → retry with normalized query (party names only)
                 → still no → render as ⚠ UNVERIFIED (grey, no link,
                   "confirm manually — may exist only on SCC/Manupatra")
```
- Verified citations are cached in Postgres to conserve IK API quota.
- A nightly job re-checks cached URLs (HTTP 200) to catch dead links.
- **Hard rule enforced in code, not just prompt:** the renderer refuses to display a blue hyperlink unless an `ik_id` exists in the DB.

### 3.4 Template Engine (Contracts + RERA deeds + pleadings)
- Each template = **Jinja2 .docx skeleton + JSON schema** (required fields, party roles, optional clauses, state-dependent blocks).
- Intake form is auto-generated from the JSON schema (so adding a template = adding two files, no code).
- **State law notes:** a lookup table `state_rules(state, instrument, stamp_duty, registration, notes, source_url)` maintained per the 5 priority states; rendered beside the draft.
- **Amendment loop:** each chat edit produces a new version row (`draft_versions`); diffs shown with `difflib`; nothing is overwritten.
- LLM's role in drafting: fill bespoke clauses (recitals, scope, confidential-info list) *within* the fixed skeleton — structure and boilerplate never hallucinated.

### 3.5 Query Validator (Litigation & Consulting entry step)
- Lightweight LLM classification: {is_legal_matter, domain: civil/criminal/labour/consumer/property/customs/other, urgency, missing_facts[]}.
- If facts are insufficient, the bot asks targeted follow-ups before opining (mirrors how the lawyer works).

### 3.6 RERA Filing Guides
- Hand-curated per state (5 states), stored as structured steps with screenshots optional and **official portal source links** on every step.
- Marked with "last verified" date; a monthly reminder task to re-verify.

## 4. Data Model (Postgres, key tables)
```
users(id, email, ...)                      -- Supabase Auth
matters(id, user_id, title, client_name, module, created_at)
messages(id, matter_id, role, content, created_at)
citations(id, case_name, neutral_citation, ik_doc_id, ik_url,
          court, decided_on, verified_at, status)
templates(id, name, category, schema_json, docx_path, states_supported)
draft_versions(id, matter_id, template_id, version_no, docx_path,
               change_summary, created_at)
statute_chunks(id, act, section_no, year, text, embedding vector)
state_rules(id, state, instrument, stamp_duty, registration_req,
            notes, source_url, last_verified)
rera_guides(id, state, step_no, instruction, source_url, last_verified)
```

## 5. Non-Functional Requirements
| Area | Requirement |
|---|---|
| Security | Supabase Auth (email + TOTP); RLS so only owner reads matters; TLS everywhere; API keys in env vars only |
| Confidentiality | No client data in third-party analytics; option to route sensitive prompts to local Ollama; explicit "no training on data" posture |
| Availability | Single user — cold starts acceptable; target ≥95% during working hours |
| Performance | Provision lookup ≤15 s; contract draft ≤60 s; citation verification ≤10 s per case |
| Cost | ₹0/month recurring (excl. pre-owned IK API plan); monitor IK quota via cached citations |
| Auditability | Every AI output stored with prompt, model used, retrieval sources — so the lawyer can reconstruct "why did it say this" |
| Legal posture | Persistent banner: "AI-generated draft for advocate review. Not legal advice." Tool is single-lawyer internal use (no UPL exposure) |

## 6. Key Technical Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Free LLM tier rate limits / policy changes | Multi-provider gateway (Gemini→Groq→Ollama); low single-user volume |
| IK API quota/cost per document | Aggressive citation caching; search-first, fetch-only-on-click |
| Hallucinated statutes (not just cases) | RAG-grounding on India Code corpus; section numbers must match retrieved chunks or get flagged |
| Old-law vs new-law confusion (IPC↔BNS) | Offence-date disambiguation rule + dual mapping table |
| State-rule drift (stamp duty changes) | `last_verified` dates + monthly review task; source URL on every state note |
| Supabase 500 MB limit as corpus grows | Statute embeddings ≈ small; archive old matter files to free storage tier; prune |
| Render free-tier cold starts | Acceptable for single user; keep-alive ping during work hours if needed |
