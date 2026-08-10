> **Title:** ADR-002 — Deterministic Document Structure (No Hallucinated Structure)
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../00_Product/Product_Constitution.md`](../../00_Product/Product_Constitution.md) §5, [`../../10_Architecture/Business_Architecture.md`](../../10_Architecture/Business_Architecture.md)

---

# ADR-002: Deterministic Document Structure — No Hallucinated Structure

## Status
Accepted. Stated as a hard rule in `CLAUDE.md` from the project's foundation; operationalized through the Template Engine and, later, the explicit `fixed_boilerplate` vs. `llm_fillable` clause classification bar.

## Context
An LLM asked to draft a legal document freely will sometimes omit statutorily required boilerplate, invent clause structure, or produce inconsistent formatting across otherwise-identical documents. For a legal drafting tool, structural hallucination is as dangerous as citation hallucination — a missing verification clause or a malformed cause title can be a real defect in a real filing.

## Decision
Contract and deed structure and boilerplate come from fixed Jinja2 `.docx` skeletons, authored by a human (or extracted from statute-prescribed model forms), never generated free-form by the LLM. The LLM's role is strictly bounded to filling bespoke clause content *inside* a structure a human has already approved.

This is enforced by a concrete classification bar, established after a live failure (Governing Law clause blending both branches of its own if/else logic because it had incorrectly been marked `llm_fillable`): a clause is `llm_fillable` only if it requires synthesizing free prose from intake inputs in a way a template author cannot enumerate in Jinja. If the variation is expressible as `{field, equals}`/`{field, not_equals}` branching, it is `fixed_boilerplate` — deterministic, not model-generated, and therefore incapable of blending mutually exclusive branches.

## Alternatives Considered
Free-form generation with a post-hoc structural linter was considered implicitly (this is the default failure mode the classification bar was introduced to prevent) but rejected — a linter catches malformed output after the fact; a fixed skeleton makes malformed structure impossible by construction.

## Consequences
- Adding a new template means adding schema + skeleton files, not new generation logic (see [`../../20_Engineering/Repository_Standards.md`](../../20_Engineering/Repository_Standards.md)).
- Clause-level `applicable_condition` gating handles most "same conceptual clause, different content by variant" cases without an LLM call, reducing both cost and hallucination surface (converting Governing Law alone yielded a measured ~20% cost/latency reduction per draft).
- Any clause candidate must pass the classification bar before being marked `llm_fillable`; the default assumption is `fixed_boilerplate` unless free-prose synthesis is genuinely required.

## Source
`CLAUDE.md` Hard Rule 2 ("No Hallucinated Structure"); `30_Implementation/Backlog.md` ("Governing Law: llm_fillable → fixed_boilerplate conversion... Formal bar established from this finding"); `20_Engineering/Lessons_Learned.md` (`applicable_condition`-per-variant pattern).
