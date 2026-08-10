> **Title:** Local Development Setup
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Engineers setting up a fresh checkout
> **Last Updated:** 1 August 2026
> **Canonical Reference:** Yes, for local dev environment setup. See "Known gaps" section for what this document does NOT cover (CI/deployment, sandboxed E2E).
> **Supersedes:** N/A
> **Related Documents:** [`40_Operations/Deployment.md`](Deployment.md), [`40_Operations/Runbooks.md`](Runbooks.md), [`20_Engineering/Lessons_Learned.md`](../20_Engineering/Lessons_Learned.md)

---

# Setup — First-Time Environment

Everything a fresh checkout needs on a bare Ubuntu machine, in the order
you'll actually hit them. Written after a real gap: LibreOffice wasn't
documented anywhere and the first PDF-export click 501'd with "soffice
not installed" (Sprint 2, 2026-08-01).

## 1. System packages

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv libreoffice
```

- **Python 3.11 specifically** (CLAUDE.md's stack choice) — a system
  `python3` on a newer Ubuntu release may already be 3.12+/3.14+; the
  backend venv must be built with `python3.11` explicitly, not whatever
  `python3` resolves to.
- **LibreOffice** — TRD §3.4's PDF export path (`app/services/contracts.py::convert_docx_to_pdf`)
  shells out to `soffice --headless --convert-to pdf`. Without it, every
  "Download .pdf" click in the Contracts module 501s with a clear error
  message (docx download is unaffected — LibreOffice is only on the PDF
  path). If disk space is tight, `libreoffice-writer` alone is lighter
  than the full `libreoffice` meta-package and still provides `soffice`;
  the full package is the safer default if you hit missing-component
  errors on conversion.
- **Node.js + npm** for the frontend — install via [nodesource](https://github.com/nodesource/distributions)
  or your preferred method; any reasonably current LTS works (tested
  against Node 22).

## 2. Backend (`/api`)

```bash
cd api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` already pulls the spaCy `en_core_web_sm` model as a
direct wheel URL — no separate `python -m spacy download` step needed,
it comes in with the normal `pip install`.

## 3. Environment variables

```bash
cp .env.example .env
cp web/.env.local.example web/.env.local
```

Fill in `.env` (repo root, read by the backend):
- `INDIAN_KANOON_API_TOKEN` — Citation Verifier
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `SAMBANOVA_API_KEY`, `CEREBRAS_API_KEY` — LLM gateway failover chain, in that order
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` — from your Supabase project settings

Fill in `web/.env.local` (read by the frontend):
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — same Supabase project, public-safe keys
- `NEXT_PUBLIC_API_URL` — defaults to `http://localhost:8000`, correct for local dev against the backend above

Never commit either file — both are gitignored already; double-check
`git status` shows neither as staged if you ever see them listed.

## 4. Database

Run every migration in `api/migrations/`, **in numeric order**, in the
Supabase SQL Editor (Project → SQL Editor → New query). Each file's own
header comment states what it depends on; all are idempotent (safe to
re-run). As of Sprint 2 Deliverable 2: `0001` through `0008`.

Then seed the reference data (statute corpus + contract templates), from
`/api` with the venv active:

```bash
python scripts/ingest_statutes.py          # every PDF under /corpus
python scripts/seed_nda_template.py
python scripts/seed_service_agreement_template.py
# + one seed_<template>_template.py per template as they're built
```

Seed scripts are idempotent (upsert by natural key) — safe to re-run
after editing clause content.

## 5. Verify it worked

```bash
cd api && source .venv/bin/activate && python -m pytest tests/ -q
```

Should show all tests passing, including `test_golden.py` (the
retrieval regression guardrail — see `docs/20_Engineering/Lessons_Learned.md` /
Sprint 1 signoff for what that suite protects). If `test_golden.py`'s
`recall@3` prints below 4/5, something in retrieval regressed — see
Sprint 1's signoff notes on the one documented, accepted miss (GT-02)
before assuming a new bug.

## 6. Run it

```bash
# Terminal 1 — backend
cd api && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 — frontend
cd web && npm install && npm run dev
```

Frontend at `http://localhost:3000`, backend at `http://localhost:8000`
(health check: `curl http://localhost:8000/health`).

## Known gaps in this doc

- No CI/deployment setup documented yet — this covers local dev only
  (Render/Vercel deploy config, if/when it exists, belongs in a separate
  doc).
- No guidance yet for running the Playwright-driven browser E2E tests
  under `api/tests/e2e/` in a sandboxed environment without normal audio
  library access — that workaround is sandbox-specific, not part of a
  standard setup, and isn't documented here on purpose.
