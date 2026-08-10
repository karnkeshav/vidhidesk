> **Title:** Business Architecture
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Architects, engineers, product
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for the domain model (matters, modules, jurisdiction, roles)
> **Supersedes:** N/A — first document to consolidate this view
> **Related Documents:** [`Engineering_Architecture_Handbook.md`](Engineering_Architecture_Handbook.md), [`../00_Product/Product_Vision.md`](../00_Product/Product_Vision.md), [`../20_Engineering/Database_Architecture.md`](../20_Engineering/Database_Architecture.md), [`../30_Implementation/ADR/ADR-001-matter-centric-architecture.md`](../30_Implementation/ADR/ADR-001-matter-centric-architecture.md)

---

# Business Architecture

## The matter as the organizing unit

Every unit of work in VidhiDesk — a contract draft, a pleading, a research query, a citation lookup — belongs to a **matter**. A matter is the persistent record a advocate opens once per client engagement and returns to across many sessions; everything else (draft versions, citations, clause reviews, hearing dockets) hangs off `matter_id`. See [ADR-001](../30_Implementation/ADR/ADR-001-matter-centric-architecture.md) for why this became the explicit organizing principle (it was implicit from Sprint 0 but only formalized as "Matter-Centric Loading Model" in Sprint 3.11 per Build Tracker E26).

## Modules

Four modules share the matter-centric model and the five cross-cutting subsystems (see [Engineering_Architecture_Handbook.md](Engineering_Architecture_Handbook.md)), each adding its own domain logic:

| Module | Domain logic on top of the shared core |
|---|---|
| Contracts | Template Engine intake schema, clause-review workflow, state-law-notes lookup |
| Litigation | Fact/Party/Exhibit intake, Limitation Analysis (`app/services/limitation.py`), Forum Advisor (`app/services/forum.py`), pleading skeletons |
| RERA / Real Estate | (Designed only) property deed templates via the same Template Engine; RERA complaint drafting via the same Litigation pipeline |
| Consulting & Litigation Support | (Designed only) ~80% reuse of the Litigation engine, output reframed as advisory brief |

Full module-by-module functional scope lives in [`../00_Product/Product_Vision.md`](../00_Product/Product_Vision.md); this document only covers the architectural pattern each module shares.

## Jurisdiction layer

State metadata attaches to every rule and template so that, e.g., a Maharashtra sale agreement and a Bihar sale agreement resolve differently. Phase 1 state coverage is Delhi, Maharashtra, and Uttar Pradesh only (per `CLAUDE.md` Decision 2); other states fall back to Central law plus a "verify state rules" flag. This is a deliberate narrowing from the original SOW's five-state target (Delhi, Maharashtra, UP, Bihar, Haryana) — see [ADR-010](../30_Implementation/ADR/ADR-010-phase-1-state-coverage.md).

## Roles

Single-user product in the current phase: one advocate (Nitesh), one developer (Keshav) as maintainer. No client-facing surface exists or is planned before Phase 4 (Productisation), and Phase 4 itself is explicitly gated on 4–6 weeks of live single-user practice first (see [Roadmap.md](../00_Product/Roadmap.md)). RACI for the build itself — architecture/code to the developer, legal-content correctness and state-rules data to the advocate — is recorded in `90_Historical/Original_Implementation_Plan.md` §4 and has held throughout the build.

## Document lifecycle

Every draft (contract clause set or pleading) moves through the same lifecycle regardless of module: **skeleton (fixed) → LLM fills bespoke content inside it → advocate reviews clause-by-clause → version recorded → export**. This is the concrete mechanism behind the Product Constitution's "draft, never deliver" principle and "no hallucinated structure" hard rule — see [ADR-002](../30_Implementation/ADR/ADR-002-deterministic-document-structure.md) and [ADR-006](../30_Implementation/ADR/ADR-006-human-in-the-loop-clause-review.md).
