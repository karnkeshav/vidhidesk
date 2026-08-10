> **Title:** ADR-009 — Freeware / Zero-Recurring-Cost Constraint as Architectural Driver
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers, product
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../20_Engineering/Technical_Standards.md`](../../20_Engineering/Technical_Standards.md), [`ADR-003-multi-provider-llm-failover.md`](ADR-003-multi-provider-llm-failover.md)

---

# ADR-009: Freeware / Zero-Recurring-Cost Constraint as Architectural Driver

## Status
Accepted from project foundation.

## Context
VidhiDesk is a single-user internal tool with no dedicated infrastructure budget. The only pre-procured paid dependency is the Indian Kanoon API, held by the product owner before the project began.

## Decision
Every other component runs on a free tier or is fully open-source: Next.js/Vercel Hobby, FastAPI/Render free tier, Supabase free tier, sentence-transformers embeddings run locally in the backend (no paid embedding API), a multi-provider LLM failover chain built entirely from free tiers (see [ADR-003](ADR-003-multi-provider-llm-failover.md)). This is treated as a primary architectural driver, not an incidental line item — it directly explains the choice of a failover chain (redundancy against any single free tier's rate limits) rather than a single paid provider, and the deliberate exclusion of SCC Online/Manupatra (paid, and historically restrictive toward third-party/AI access) from Phase 1 scope.

## Alternatives Considered
A single paid LLM provider with generous rate limits was the implicit simpler alternative — rejected on cost grounds given the explicit ₹0/month recurring cost target, and because a single-provider design has no fallback if that provider's free/cheap tier terms change.

## Consequences
- Any future architectural decision that would introduce a new recurring cost must be evaluated against this constraint explicitly, not assumed acceptable because it improves capability.
- Free-tier limitations (cold starts, rate limits, 500MB Postgres cap) are accepted trade-offs, not defects to be engineered around at cost.
- If the tool is ever commercialized or scaled beyond single-user use, this constraint is explicitly flagged (in the original Technical Requirements) as one to revisit — it is not asserted as a permanent constraint the way the Citation Gate and PII masking are.

## Source
`90_Historical/Original_Technical_Requirements.md` (hard constraint statement, header); `30_Implementation/Build_Tracker.md` §2 ("the effectively-zero-recurring-cost constraint... functions as a primary architectural driver, not an isolated requirement line"); `90_Historical/Original_Project_Plan_Revised.md` §8 (cost as a named success metric).
