> **Title:** Technical Standards
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for stack choices and non-functional targets. Do not substitute any stack item without asking first, per `CLAUDE.md`.
> **Supersedes:** `90_Historical/Original_Technical_Requirements.md` §2 (stack table), §5 (NFRs)
> **Related Documents:** [`../10_Architecture/Engineering_Architecture_Handbook.md`](../10_Architecture/Engineering_Architecture_Handbook.md), [`Database_Architecture.md`](Database_Architecture.md), [`Repository_Standards.md`](Repository_Standards.md), [`../30_Implementation/ADR/ADR-009-freeware-zero-cost-constraint.md`](../30_Implementation/ADR/ADR-009-freeware-zero-cost-constraint.md)

---

# Technical Standards

## Stack (fixed — do not substitute without asking, per `CLAUDE.md`)

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind + shadcn/ui → Vercel (Hobby) |
| Backend | Python 3.11 + FastAPI → Render free tier |
| DB / Auth / Storage / Vectors | Supabase free tier (Postgres + pgvector + Auth) |
| Embeddings | sentence-transformers `BAAI/bge-small-en-v1.5`, run in backend |
| Doc generation | Jinja2 → python-docx; PDF via LibreOffice headless |
| Statute ingestion | PyMuPDF (+ pytesseract only for scanned PDFs) |
| LLM providers | Gemini 2.5 Flash → Groq (Llama-3.3-70B) → SambaNova → Cerebras, in that fixed failover order. No local Ollama. |

Python **3.11 specifically** — a system `python3` on a newer OS may resolve to 3.12+/3.14+; the backend venv must be built with `python3.11` explicitly (see [`../40_Operations/Local_Development_Setup.md`](../40_Operations/Local_Development_Setup.md)).

## Non-functional requirements

| Area | Requirement |
|---|---|
| Security | Supabase Auth; RLS so only the owning user reads their matters; TLS everywhere; secrets in environment variables only, never in code/logs/commit history |
| Confidentiality | No client data in third-party analytics; PII masked before any external LLM call (mandatory, not optional) |
| Availability | Single user — cold starts acceptable; target ≥95% during working hours |
| Performance | Provision lookup ≤15s; contract draft ≤60s; citation verification ≤10s per case; PDF conversion capped at 15s subprocess timeout |
| Cost | ₹0/month recurring beyond the pre-owned Indian Kanoon API plan — this is a primary architectural driver, not an incidental constraint. See [ADR-009](../30_Implementation/ADR/ADR-009-freeware-zero-cost-constraint.md). |
| Auditability | Every AI output stored with prompt, model used, and retrieval sources |
| Legal posture | Persistent "AI-generated draft for advocate review. Not legal advice." banner on every screen |

## Environment variables

Referenced by name only, never written into code, logs, or commit history: `INDIAN_KANOON_API_TOKEN`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `SAMBANOVA_API_KEY`, `CEREBRAS_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`.

## Testing discipline

Backend: `pytest`, run from `/api` with the venv active. Golden test suite (`docs/golden_tests.json` — kept outside the reorganized hierarchy on purpose; see [README.md](../README.md#exception-golden_testsjson)) is the retrieval regression guardrail — a `recall@3` drop below the accepted baseline signals a real regression, not noise (see the Sprint 1 signoff note in [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)). Frontend: `npm run lint` (0 errors required) and `npm run build` (all static routes must succeed) before any UI change is considered done. Per the project's own hard-won process rule (see [`Lessons_Learned.md`](Lessons_Learned.md)), a passing unit-test suite is necessary but not sufficient — a live browser E2E walkthrough on the real seeded template is required before marking a batch done, because four distinct Sprint 2 bugs passed the full unit suite and were only caught by an actual click-through.

## Bilingual input handling

Hindi/English/Hinglish input is expected and normalized to English internally before retrieval, per `CLAUDE.md`. This is a standing requirement on any new input surface, not a Phase-1-only accommodation.
