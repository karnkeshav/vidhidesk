> **Title:** ADR-001 — Matter-Centric Data Architecture
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../10_Architecture/Business_Architecture.md`](../../10_Architecture/Business_Architecture.md), [`../../20_Engineering/Database_Architecture.md`](../../20_Engineering/Database_Architecture.md)

---

# ADR-001: Matter-Centric Data Architecture

## Status
Accepted. Implicit from Sprint 0 (`matters` as the root table in the original data model), formalized explicitly as the "Matter-Centric Loading Model" in the Contracts module.

## Context
VidhiDesk spans four modules (Contracts, Litigation, RERA, Consulting) that each produce different kinds of work product (contract drafts, pleadings, research briefs, deed drafts) but all belong to a single advocate's ongoing engagement with a client on a specific issue.

## Decision
Every unit of work is anchored to a `matter` row (`matters(id, user_id, title, client_name, module, template_id, created_at)`). Draft versions, citations, clause reviews, hearing dockets, and facts/exhibits timelines all reference `matter_id` as their organizing foreign key, regardless of which module produced them. Routes are matter-centric (`/contracts/{matterId}`, `/litigation/[matterId]`) rather than template- or document-centric.

This was reinforced in production via migration `0010_add_template_id_to_matters.sql`, which added a permanent `template_id` column to `matters` specifically so that a matter's routing and identity no longer depends on a query parameter (`?template=`) — the matter itself is now sufficient to reconstruct everything about the work in progress.

## Alternatives Considered
A document-centric model (where a draft is the primary entity and a "matter" is just a label) was the implicit alternative in earlier iterations, evidenced by the pre-migration-0010 pattern of routing via `?template=` query parameters rather than through the matter. This was abandoned because it made matter history, search, and cross-module continuity ("what am I walking into" on the dashboard) harder to implement consistently.

## Consequences
- Every new table that stores work product must carry `matter_id` and inherit RLS scoped to matter ownership (see [`../../20_Engineering/Database_Architecture.md`](../../20_Engineering/Database_Architecture.md)).
- Matter history and search work uniformly across all four modules without module-specific plumbing.
- A matter can outlive any single draft or citation within it — deleting a draft version does not delete the matter's identity or history.

## Source
`30_Implementation/Build_Tracker.md` §6, Evidence E26 ("Matter-Centric Loading Model Release"); `90_Historical/Original_Technical_Requirements.md` §4 (original `matters` table definition).
