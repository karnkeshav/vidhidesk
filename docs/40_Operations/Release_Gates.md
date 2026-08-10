> **Title:** Release Gates
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav / Nitesh (legal-content sign-off)
> **Audience:** Engineers, product, future AI agents deciding whether something is "done"
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for what "shippable" means at each phase
> **Supersedes:** N/A — consolidates gates that were previously scattered across the Scope of Work, Implementation Plan, and Project Plan
> **Related Documents:** [`../00_Product/Roadmap.md`](../00_Product/Roadmap.md), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)

---

# Release Gates

## Phase 1 exit gate (met — see Roadmap.md)

- ≥10 real matters run through the tool across live modules
- Zero incidents of an unflagged fake citation reaching a draft
- Contract turnaround (intake → vetted draft) under 30 minutes
- ₹0/month recurring cost beyond the Indian Kanoon API plan

## Per-template gate (Contracts, applies to every template before it counts as "shipped")

A template is not complete on generation working — it additionally requires: clause-by-clause review by the advocate (keep/redraft/delete per clause, not whole-document approval), a live browser E2E walkthrough on the real seeded template (not just passing unit tests — see [`../20_Engineering/Lessons_Learned.md`](../20_Engineering/Lessons_Learned.md) for why this is a hard rule, not a suggestion), and export to both `.docx` and `.pdf` verified working. Any template not yet clause-reviewed ships labeled "beta — unreviewed skeleton" and does not count toward the Phase 1 template-count gate.

## Phase 2 gate (Litigation, not yet reached)

100 generated citations audited; target zero fabricated citations reaching the user.

## Standing gate, applies to every module forever

Per the Product Constitution's Legal Safety Principles: no output reaches a client or a court without advocate review and sign-off. This is not a phase-specific gate that relaxes as the product matures — it is permanent.

## UI-specific gate

No screen may move directly from "Designed" to "Implemented" — see the Google Stitch 6-step lifecycle in [`../50_Reference/Stitch_Guidelines.md`](../50_Reference/Stitch_Guidelines.md). A screen requires explicit user (Nitesh) sign-off on its visual design before implementation begins.
