> **Title:** Architecture Decision Records — Index
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav
> **Audience:** Architects, engineers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for the index and numbering of all ADRs
> **Related Documents:** [`../../10_Architecture/Engineering_Architecture_Handbook.md`](../../10_Architecture/Engineering_Architecture_Handbook.md)

---

# Architecture Decision Records

Each ADR here records a decision already approved elsewhere in the project's history (`CLAUDE.md`, the original SOW/TRD/Implementation Plan, the revised Project Plan, or the Build Tracker) — extracted into a standalone, citable record. None of these ADRs introduces a new decision; each cites its source.

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001-matter-centric-architecture.md) | Matter-Centric Data Architecture | Accepted |
| [002](ADR-002-deterministic-document-structure.md) | Deterministic Document Structure — No Hallucinated Structure | Accepted |
| [003](ADR-003-multi-provider-llm-failover.md) | Multi-Provider LLM Failover Strategy | Accepted |
| [004](ADR-004-mandatory-pii-masking.md) | Mandatory PII Masking Before External LLM Calls | Accepted |
| [005](ADR-005-zero-hallucination-citation-gate.md) | Zero-Hallucination Citation Verification Gate | Accepted |
| [006](ADR-006-human-in-the-loop-clause-review.md) | Human-in-the-Loop Review (Clause-by-Clause) | Accepted |
| [007](ADR-007-contracts-before-litigation-build-order.md) | Contracts-Before-Litigation Build Order | Accepted |
| [008](ADR-008-prompt-injection-boundary-isolation.md) | Prompt-Injection Boundary Isolation (SEC-01) | Accepted |
| [009](ADR-009-freeware-zero-cost-constraint.md) | Freeware / Zero-Recurring-Cost Constraint as Architectural Driver | Accepted |
| [010](ADR-010-phase-1-state-coverage.md) | Phase 1 State Coverage Scope | Accepted |
| [011](ADR-011-ai-case-analysis-before-pleading.md) | AI Case Analysis as a Pre-Pleading Deliverable | Accepted |

## A note on requested ADRs not included here

The task that produced this documentation restructure named two additional example ADRs — **"AI Runtime DAG"** and **"Prompt Registry"** — as illustrative titles to extract. Neither corresponds to an approved decision found anywhere in this repository's documentation, migrations, or code comments:

- No document describes the AI pipeline as a DAG. Every pipeline diagram found (retrieval, citation verification, pleading generation) is a linear flowchart or state machine, not a directed acyclic graph with the branching/merging semantics that name would imply.
- No document or code establishes a "Prompt Registry" as an architectural component. What exists is a `SYSTEM_PROMPTS` dictionary of per-task-type strings inside `llm_gateway.py` and `litigation.py` — a straightforward constant map, not a registry pattern with its own lifecycle, versioning, or approval process.

Per this refactor's explicit instruction to extract only decisions already approved and not invent new architectural decisions, these two were not fabricated into ADRs. If a DAG-based orchestration model or a formal prompt registry is a direction the team actually wants, that is a new architectural decision to be made and documented going forward — not one to backfill a record for.

## Numbering vs. the originally requested list

The originally requested ADR numbering (001, 002, 005, 006, 007 corresponding to Matter-Centric / Deterministic / Multi-Provider LLM / Human-in-the-Loop / Zero Hallucination) has been renumbered here to run 001–010 sequentially, incorporating additional real decisions (PII masking, prompt-injection isolation, contracts-first build order, the zero-cost constraint, and Phase 1 state scope) that are equally well-documented and approved but were not in the original example list. Cross-references elsewhere in this documentation use the numbering in this index.
