> **Title:** ADR-008 — Prompt-Injection Boundary Isolation (SEC-01)
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers, security
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../10_Architecture/AI_Architecture.md`](../../10_Architecture/AI_Architecture.md)

---

# ADR-008: Prompt-Injection Boundary Isolation (SEC-01)

## Status
Accepted. Implemented in Phase A Backend P0 Stabilization (Build Tracker Evidence E21).

## Context
Litigation and Consulting flows accept free-text user input (fact patterns, amendment instructions) that is interpolated into LLM prompts alongside system instructions and retrieved statutory context. Without isolation, adversarial or even accidentally-formatted user input could be interpreted by the model as an instruction rather than data — e.g. a fact pattern containing text that resembles a system directive could attempt to override statutory procedural limits or drafting constraints.

## Decision
All user-supplied content is enclosed within explicit XML boundary tags (`<user_facts>`, `<user_instruction>`, `<user_amendment>`) at every LLM entry point, paired with an explicit system-prompt instruction that content inside these tags must be treated strictly as data and never permitted to override system instructions or statutory limits. This is a fixed convention (`SEC-01`) applied uniformly, not a per-endpoint judgment call.

## Alternatives Considered
Relying on the base model's own instruction-following robustness against injected commands within free text was the implicit prior state — rejected as insufficient given this product's specific requirement that statutory procedural limits (e.g. limitation periods, mandatory notice requirements) must never be overridden by user input, however phrased.

## Consequences
- Any new LLM entry point must wrap user content in the appropriate boundary tag before prompt assembly — this is a standing requirement, not optional (see [`../../20_Engineering/API_Standards.md`](../../20_Engineering/API_Standards.md)).
- The pattern is uniform across Contracts amendment commands and Litigation fact/amendment inputs.

## Source
`30_Implementation/Build_Tracker.md` Evidence E21 ("Phase A P0 Backend Stabilization... SEC-01 XML prompt injection boundary delimiters across all LLM entry points"); `30_Implementation/Technical_Design/Litigation_Module_Architecture.md` §9 ("Prompt Architecture & Injection Isolation").
