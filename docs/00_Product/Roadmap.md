> **Title:** Product Roadmap
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav (build) / Nitesh (domain expert, review, prioritization)
> **Audience:** Founders, engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for build order and phasing. Current implementation status lives in [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md) — this document answers "what's the plan," the tracker answers "where are we against it."
> **Supersedes:** `90_Historical/Original_Project_Plan_Revised.md` §5 (Phasing), `90_Historical/Original_Implementation_Plan.md` §2 (Sprint Plan)
> **Related Documents:** [`Product_Constitution.md`](Product_Constitution.md) §11, [`Product_Vision.md`](Product_Vision.md), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)

---

# Product Roadmap

## Build order (approved, in force)

Contracts → Litigation → Consulting → RERA. Foundations (LLM Gateway, PII Masker) and the Statute RAG + Citation Verifier are built early regardless, because Litigation depends on them, but the first user-facing module is Contracts.

This reverses the original Scope of Work's Litigation-first sequence. Two separate reasons, per `90_Historical/Original_Project_Plan_Revised.md` §2 and Build Tracker §1.1 — not to be conflated: (1) Contracts is the largest revenue portfolio, template-constrainable, and carries near-zero citation-hallucination risk, so something usable ships fastest; Litigation is also the area where the advocate's own expertise makes him least dependent on the tool. (2) Separately, no gold-standard sample drafts existed to imitate, so every module's template quality — not just Contracts' — had to be reached through clause-by-clause review cycles rather than whole-document approval. See [ADR-007](../30_Implementation/ADR/ADR-007-contracts-before-litigation-build-order.md) for the full decision record.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| Phase 0 | Foundations: repo, hosting scaffolds, LLM Gateway, Indian Kanoon API spike | ✅ Complete |
| Phase 1 | Contracts MVP — full Phase 1 template library, intake→draft→amend loop, jurisdiction layer | ✅ Complete — 10/10 Phase 1 templates live |
| Phase 2 | Litigation + citation engine — RAG pipeline, pleading generation, full citation verification | 🔶 Partially complete: matter/parties/facts/evidence-upload, Limitation Engine, Forum Advisor, and a full end-to-end AI Case Analysis vertical slice (Sprint 3.5.3, [ADR-011](../30_Implementation/ADR/ADR-011-ai-case-analysis-before-pleading.md)) are ✅ built and tested. Pleading generation itself ([`Litigation_Module_Architecture.md`](../30_Implementation/Technical_Design/Litigation_Module_Architecture.md)) remains 📐 architecture approved, implementation not started — gated on user signoff |
| Phase 3 | Consulting & RERA | 📐 Designed only — tiles live on dashboard, no workspace implementation |
| Phase 4 | Productisation (multi-user, matter management, billing, client portal) | 🔮 Not started — explicitly deferred until the advocate has used the tool in live practice for 4–6 weeks post-Phase 3 |

For evidence-backed detail behind each status, see [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md) §4–§8.

## Phase 1 exit criteria (met)

- ≥10 real matters run through the tool across live modules
- Zero incidents of an unflagged fake citation reaching a draft
- Contract turnaround (intake → vetted draft) under 30 minutes
- ₹0 recurring cost beyond the pre-procured Indian Kanoon API plan

## Phase 2 gate (not yet reached)

100 generated citations audited; target zero fabricated citations reaching the user. Per `90_Historical/Original_Project_Plan_Revised.md` §5.

## Parking lot (post-Phase 4, unscoped)

Manupatra/SCC Online integration (if commercially justified), cause-list watcher + client WhatsApp updates, contradiction/chronology tools for trial prep, multi-user & client portal, billing, "still good law" citator analysis. Nothing on this list enters scope before Phase 4 begins — this boundary is itself an approved decision (risk mitigation against scope creep), not just a suggestion.

## Long-term direction

See [`Product_Constitution.md`](Product_Constitution.md) §11 for the values-level statement of long-term direction (depth over breadth, cautious collaboration features, the bar every future capability must clear). This roadmap will be updated as each phase closes; the Constitution's §11 is not expected to change on the same cadence.
