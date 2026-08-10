> **Title:** API Standards
> **Version:** 1.0
> **Status:** Active — extracted from observed convention, not a separately authored spec (see note below)
> **Owner:** Keshav
> **Audience:** Backend engineers, future AI agents adding routers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Partial — no dedicated API standards document existed before this refactor. This consolidates the conventions actually followed across `api/app/routers/*.py`, as documented in `30_Implementation/Technical_Design/Litigation_Module_Architecture.md` §4 and observable in the shipped Contracts endpoints.
> **Supersedes:** N/A
> **Related Documents:** [`../10_Architecture/Runtime_Architecture.md`](../10_Architecture/Runtime_Architecture.md), [`Database_Architecture.md`](Database_Architecture.md)

---

# API Standards

**Provenance note:** unlike the other documents in this folder, this one was not extracted from a single existing source — it consolidates conventions that are consistently followed in the codebase but were never written down as a standard. Treat it as descriptive of current practice, and update it if practice diverges rather than treating it as a spec that was violated.

## Router organization

One router module per domain area under `api/app/routers/` (`matters.py`, `profile.py`, `litigation.py`, etc.), registered on the FastAPI app in `api/app/main.py`. Routes are prefixed by domain (`/api/litigation/...`, `/api/profile`, `/api/matters/...`).

## Response and error convention

Every endpoint documents its response schema and the specific error codes it can return, rather than a generic catch-all. Observed pattern from `Litigation_Module_Architecture.md` §4:

| Situation | Code |
|---|---|
| Request validation failure | HTTP 400 |
| Resource not found (e.g. matter) | HTTP 404 |
| Upstream LLM failure (after exhausting the full provider failover chain) | HTTP 502 |
| Subprocess timeout (LibreOffice PDF conversion, capped at 15s) | HTTP 504 |
| Missing system dependency (e.g. `soffice` not installed) | HTTP 501 |

## PII and prompt-boundary handling at the router layer

Any endpoint that accepts free-text user input destined for an LLM call must pass it through the PII masker before it reaches `llm_gateway.generate()`, and must wrap it in the appropriate XML boundary tag (`<user_facts>`, `<user_instruction>`, `<user_amendment>`) per [SEC-01 / ADR-008](../30_Implementation/ADR/ADR-008-prompt-injection-boundary-isolation.md). This is not optional per-endpoint discretion — it applies to every LLM entry point.

## Auditability requirement

Any endpoint that produces or amends an AI-generated draft must persist the masked prompt, the model used, and retrieval sources alongside the resulting `draft_versions` (or equivalent) row, per the Product Constitution's AI Principles §5.

## Schema-driven endpoints

Where an endpoint's behavior is meant to vary by template (Contracts intake, future RERA deed intake), the variation belongs in the template's JSON schema, not in endpoint-specific code branches — adding a new template should mean adding schema + skeleton files, not new router logic. This mirrors the Template Engine's design intent in [`../10_Architecture/Business_Architecture.md`](../10_Architecture/Business_Architecture.md).
