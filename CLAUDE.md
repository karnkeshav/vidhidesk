# VidhiDesk — AI Legal Assistant for an Indian Advocate

## What this is
A private, single-user, web-based legal assistant for a practicing Indian
lawyer (Nitesh). Four modules: Contracts, Litigation, RERA/Real Estate,
Consulting & Litigation Support. The lawyer always vets output before any
client sees it. Full documentation lives in /docs — start at
/docs/README.md, which indexes the hierarchy and states the Documentation
Precedence Policy (this replaces the old "Project_Plan wins conflicts"
rule below). Read before major work:
- /docs/00_Product/Product_Constitution.md (enduring product philosophy —
  highest-precedence document in the project)
- /docs/00_Product/Product_Vision.md (module scope, acceptance criteria)
- /docs/10_Architecture/Engineering_Architecture_Handbook.md (architecture,
  stack, data model — links out to Business/AI/Runtime Architecture)
- /docs/00_Product/Roadmap.md (build order, phasing)
- /docs/30_Implementation/Build_Tracker.md (current build status)
- /docs/30_Implementation/ADR/ (individual architecture decisions, with
  sources cited back to this file's Decisions section where applicable)

## Decisions (override anything contradictory in /docs)
1. BUILD ORDER: Contracts module first, then Litigation, then Consulting,
   then RERA. (Foundations + Citation Verifier are still built early because
   Litigation depends on them, but the first user-facing module is Contracts.)
2. STATES: Delhi, Maharashtra, UP only in Phase 1. Others fall back to
   Central law + a "verify state rules" flag.
3. LLM PROVIDERS: Gemini 2.5 Flash (free tier) -> Groq (Llama-3.3-70B) ->
   SambaNova -> Cerebras. NO local Ollama — infra does not support it.
   The gateway must fail over in that order on rate-limit or error.
4. PRIVACY: Because there is no local model, ALL prompts go to third-party
   clouds. Therefore a PII-masking layer is MANDATORY in the LLM gateway:
   party names, addresses, phone numbers, Aadhaar/PAN patterns are replaced
   with stable placeholders (PARTY_A, ADDR_1, ...) before any external LLM
   call, and restored in the response. Masking map is stored per-matter in
   Postgres, never sent to the LLM.

## Hard rules (non-negotiable, enforce in CODE not just prompts)
1. CITATION GATE: The renderer must refuse to display a live hyperlink for
   any case citation unless a verified Indian Kanoon doc_id exists in the
   citations table. Unverified citations render grey with the label
   "Unverified — confirm manually (may exist only on SCC/Manupatra)".
   No exceptions. This is the product's entire reason to exist.
2. NO HALLUCINATED STRUCTURE: Contract/deed structure and boilerplate come
   from fixed Jinja2 .docx skeletons. The LLM only fills bespoke clauses
   inside the skeleton. It never generates a whole contract free-form.
3. STATUTE GROUNDING: Statutory claims must trace to retrieved chunks from
   the India Code corpus (RAG). A section number that doesn't match a
   retrieved chunk gets flagged, not displayed as fact.
4. Every AI output is stored with its prompt, model used, and retrieval
   sources (auditability).
5. Every screen shows: "AI-generated draft for advocate review. Not legal
   advice."
6. Secrets only in environment variables. Never write a key into code,
   logs, or commit history.

## Stack (do not substitute without asking)
- Frontend: Next.js 14 + TypeScript + Tailwind + shadcn/ui -> Vercel (Hobby)
- Backend: Python 3.11 + FastAPI -> Render free tier
- DB/Auth/Storage/Vectors: Supabase free tier (Postgres + pgvector + Auth)
- Embeddings: sentence-transformers BAAI/bge-small-en-v1.5, run in backend
- Doc generation: Jinja2 -> python-docx; PDF via LibreOffice headless
- Statute ingestion: PyMuPDF (+ pytesseract only if a PDF is scanned)
- Repo: monorepo — /web (Next.js), /api (FastAPI), /templates, /corpus, /docs

## Environment variables (already provisioned; reference by name only)
INDIAN_KANOON_API_TOKEN, GEMINI_API_KEY, GROQ_API_KEY, SAMBANOVA_API_KEY,
CEREBRAS_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

## Indian Kanoon API (verify live behaviour in Sprint 0 before relying on this)
- Auth: HTTP header `Authorization: Token $INDIAN_KANOON_API_TOKEN`
- Endpoints: /search/ (query via formInput; pagenum starts at 0),
  /doc/{id}/ (full judgment; maxcites/maxcitedby params), /docfragment/
- Canonical public URL for verified citations:
  https://indiankanoon.org/doc/{doc_id}/
- Cache-first: never call the API for a citation already verified and
  stored in the citations table. Log every API call with cost/quota impact.

## Data model
Use the tables defined in /docs/20_Engineering/Database_Architecture.md
(matters, messages, citations, templates, draft_versions, statute_chunks,
state_rules, rera_guides) plus a pii_masks table for the masking layer.
Enable Supabase RLS: only the owning user reads their matters.

## Working style
- Work in small verifiable steps. After each meaningful unit, state how to
  test it manually.
- Write tests for the Citation Verifier and the PII masker — these two must
  never regress.
- When /docs conflict with each other, follow /docs/README.md's
  Documentation Precedence Policy (Product Constitution > Engineering
  Architecture Handbook > ADRs > Engineering standards > module-specific
  Technical Designs > Build Tracker > Historical docs). The Decisions
  section above and the Hard Rules below remain in force regardless —
  they are restated and cited in ADR-001 through ADR-010 for traceability,
  not superseded by that policy. If still ambiguous, ask before building.
- Bilingual input (Hindi/English/Hinglish) is expected; normalize to
  English internally before retrieval.
