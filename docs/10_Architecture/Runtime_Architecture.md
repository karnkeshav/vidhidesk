> **Title:** Runtime Architecture
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Engineers, operations
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for hosting topology and deployment targets
> **Supersedes:** `90_Historical/Original_Technical_Requirements.md` §1 (hosting portion), §2 (stack table's hosting rows)
> **Related Documents:** [`Engineering_Architecture_Handbook.md`](Engineering_Architecture_Handbook.md), [`../40_Operations/Deployment.md`](../40_Operations/Deployment.md), [`../20_Engineering/Technical_Standards.md`](../20_Engineering/Technical_Standards.md)

---

# Runtime Architecture

## Hosting topology (confirmed live)

| Layer | Platform | Evidence |
|---|---|---|
| Frontend | Next.js 14, deployed on Vercel (Hobby tier) | Build Tracker E15 |
| Backend | Python 3.11 / FastAPI, deployed on Render (free tier) — live at `vidhidesk.onrender.com` | Build Tracker E15 |
| Database / Auth / Storage / Vectors | Supabase free tier (Postgres + pgvector + Auth + Storage) | Build Tracker throughout |
| Judgment source | Indian Kanoon API (the one pre-procured paid dependency) | `CLAUDE.md` |

## Request flow

```
Browser (Next.js client)
   → HTTPS/JSON → FastAPI router (api/app/routers/*.py)
      → service layer (contracts.py / litigation.py / limitation.py / forum.py / citations.py / retrieval.py / llm_gateway.py / pii_mask.py)
         → Supabase Postgres (matters, drafts, citations, statute_chunks)
         → external: LLM provider (masked prompt only), Indian Kanoon API (cache-first)
      ← JSON response
   ← rendered UI (LegalDocumentSheet, AI Assistant sidebar, citation panel)
```

## Cold-start posture

Render's free tier cold-starts are accepted by design — this is a single-user tool, and availability target is ≥95% during working hours, not 24/7 hot infrastructure. See [`../20_Engineering/Technical_Standards.md`](../20_Engineering/Technical_Standards.md) for the full non-functional requirements table.

## Document generation path

`.docx` generation: Jinja2 templates rendered via `python-docx`/`docxtpl`. `.pdf` generation: `.docx` piped through LibreOffice headless (`soffice --headless --convert-to pdf`), capped at a 15-second subprocess timeout (`PERF-01`, Build Tracker E21) that returns HTTP 504 rather than hanging a worker indefinitely. LibreOffice is a required system package for local dev — see [`../40_Operations/Local_Development_Setup.md`](../40_Operations/Local_Development_Setup.md).

## What this document does not cover

CI/CD pipeline configuration, deployment runbooks, and monitoring/alerting are not yet documented anywhere in this repository beyond the bare fact that Render and Vercel deployments exist and work. This is a real, acknowledged gap — see [`../40_Operations/Deployment.md`](../40_Operations/Deployment.md) and [`../40_Operations/Monitoring.md`](../40_Operations/Monitoring.md), both of which flag it rather than paper over it.
