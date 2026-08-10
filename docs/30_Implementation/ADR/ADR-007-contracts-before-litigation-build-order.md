> **Title:** ADR-007 — Contracts-Before-Litigation Build Order
> **Version:** 1.0
> **Status:** Accepted (supersedes an earlier decision)
> **Owner:** Keshav
> **Audience:** Product, engineering
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../00_Product/Roadmap.md`](../../00_Product/Roadmap.md)

---

# ADR-007: Contracts-Before-Litigation Build Order

## Status
Accepted. Explicitly reverses the original Scope of Work and Implementation Plan's Litigation-first sequencing before Sprint 0 closed.

## Context
The original requirements call assumed Litigation would ship first — it exercises the two hardest subsystems (RAG + Citation Verifier) that every other module reuses, so building it first would front-load the hard technical risk. On revisiting the plan (after the Indian Kanoon API was secured and it was confirmed no sample client drafts would be supplied), two considerations argued for the opposite order.

## Decision
Build order is Contracts → Litigation → Consulting → RERA, with foundational subsystems (LLM Gateway, RAG retriever, Citation Verifier) still built early because Litigation depends on them.

## Alternatives Considered
Litigation-first (the original plan) was rejected for two independent reasons, which must not be conflated (Build Tracker §1.1 explicitly corrects an earlier draft that had merged them): **(1)** Contracts is the largest revenue portfolio, is template-constrainable, and carries near-zero citation-hallucination risk — a usable module ships in weeks rather than months, and Litigation is precisely the area where the advocate's own expertise makes him least dependent on the tool, so de-risking it later costs less. **(2)** Separately, without sample drafts to imitate, correctness in *any* module requires clause-by-clause review cycles (see [ADR-006](ADR-006-human-in-the-loop-clause-review.md)) — this affected the review process, not the module ordering choice itself.

## Consequences
- Litigation implementation is explicitly gated behind Contracts' completion and its own full Stitch design lifecycle sign-off (see [`../../50_Reference/Stitch_Guidelines.md`](../../50_Reference/Stitch_Guidelines.md)).
- The Citation Verifier and RAG retriever were still built in Sprint 1, ahead of the Contracts UI, because Litigation and Consulting both depend on them and retrofitting them later would be more expensive.
- This build order is a product-strategy decision, not a technical dependency decision — the Roadmap should not be read as claiming Contracts is technically simpler than Litigation, only that it is lower-risk to ship first.

## Source
`90_Historical/Original_Scope_of_Work.md` (original Litigation-first assumption); `90_Historical/Original_Implementation_Plan.md` §1 (original rationale for Litigation-first); `90_Historical/Original_Project_Plan_Revised.md` §2 ("Build order... This inverts the sequencing assumed on the call"); `CLAUDE.md` Decision 1; `30_Implementation/Build_Tracker.md` §1.1.
