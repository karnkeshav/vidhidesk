> **Title:** ADR-011 — AI Case Analysis as a Pre-Pleading Deliverable
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers, legal
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../Technical_Design/Litigation_Module_Architecture.md`](../Technical_Design/Litigation_Module_Architecture.md), [`ADR-002-deterministic-document-structure.md`](ADR-002-deterministic-document-structure.md), [`ADR-005-zero-hallucination-citation-gate.md`](ADR-005-zero-hallucination-citation-gate.md), [`ADR-006-human-in-the-loop-clause-review.md`](ADR-006-human-in-the-loop-clause-review.md)

---

# ADR-011: AI Case Analysis as a Pre-Pleading Deliverable

## Status
Accepted. Introduced and implemented in Sprint 3.5.3 (End-to-End Advocate Experience vertical slice).

## Context
`Litigation_Module_Architecture.md` (Sprint 3.5) specifies the Litigation module's workflow as running straight from facts intake to pleading generation. Building the full pleading pipeline first, before any part of the Litigation module had shipped end-to-end, would have meant the advocate's first experience of the module was a court-ready document — the highest-stakes, hardest-to-trust output the product can produce — with no intermediate checkpoint for the advocate to sanity-check the AI's read of the matter before committing to drafting.

## Decision
A new intermediate deliverable — **AI Case Analysis** — sits between facts/evidence intake and pleading generation. It produces a structured, versioned review (matter summary, chronological facts, missing information, applicable statutes, possible causes of action, jurisdiction summary, limitation summary, potential risks, evidence gaps, recommended next steps, and any case law worth flagging) that the advocate reviews *before* deciding whether — and how — to draft anything. It is explicitly not a pleading and does not claim to be one anywhere in its output.

The analysis enforces a hard deterministic/LLM split, not just a UI convention:

- **Never LLM-generated:** chronological facts (sorted, not synthesized), jurisdiction summary (passed through verbatim from the Forum Advisor), limitation summary (passed through verbatim from the Limitation Engine), and the identity (act + section number) of every applicable statute (from the RAG Retriever's actual retrieved chunks).
- **LLM-synthesized, but never trusted un-gated:** matter summary, missing information, possible causes of action, potential risks, evidence gaps, recommended next steps. Every statute a cause of action claims to rely on is cross-checked against the retrieved corpus and flagged `grounded: true/false` rather than silently trusted or silently dropped (extends [ADR-002](ADR-002-deterministic-document-structure.md)'s "no hallucinated structure" principle to structured legal reasoning, not just document boilerplate). Every case name the model proposes is run through the Citation Verifier before it can render as anything but an explicit "unverified — confirm manually" claim (the exact [ADR-005](ADR-005-zero-hallucination-citation-gate.md) gate, applied here for the first time to something other than a pleading citation).

Versioning reuses the immutable, auto-incrementing per-matter pattern established by `draft_versions` (see `20_Engineering/Database_Architecture.md`), applied to a new artifact type (`litigation_case_analyses`) rather than overloading the existing table, since a case analysis is structured data, not a docx draft.

## Alternatives Considered
Skipping straight to pleading generation as originally scoped in `Litigation_Module_Architecture.md` was the default path — rejected because it collapses "does the AI understand this matter correctly" and "is this specific document court-ready" into a single, high-stakes checkpoint, with no cheaper earlier point for the advocate to catch a misread of the facts before a full pleading draft is generated around it.

## Consequences
- The Litigation Module Gating Rule (`Build_Tracker.md` §0.3: no Litigation implementation begins before all Litigation Stitch designs are approved) still applies to any *future* pleading-generation UI; this vertical slice's screens were built directly against `UI_UX_Guidelines.md`'s established design system rather than through a full Stitch design cycle, consistent with how the module's existing Overview/Facts/Hearings tabs were already built.
- Pleading generation, when it is built, should reuse this analysis (particularly its statute grounding and jurisdiction/limitation snapshots) as its own starting context rather than re-deriving them — the analysis is meant to be a real input to drafting, not a disconnected preview.
- Any future module (Consulting, RERA) that wants a similar "AI reasoning the advocate checks before committing to drafting" step should follow the same deterministic/LLM split established here, not invent a new one.

## Source
`Litigation_Module_Architecture.md` (original pleading-first workflow this ADR modifies); `api/app/services/case_analysis.py` (implementation); Sprint 3.5.3 task scope ("Generate AI Case Analysis — not a pleading yet... Focus on producing a trustworthy legal analysis that an advocate can review before deciding to draft").
