> **Title:** VidhiDesk Product Constitution
> **Version:** 1.0
> **Status:** Active — Canonical (highest precedence)
> **Owner:** Keshav (maintainer) / Nitesh (product authority)
> **Audience:** Founders, product leaders, architects, engineers, legal experts, designers, QA teams, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes — outranks every other document in this repository (see [Documentation Precedence Policy](../README.md#documentation-precedence-policy))
> **Supersedes:** Any contradictory statement in any other `/docs` document, including `CLAUDE.md`'s prior "Project_Plan wins conflicts" clause
> **Related Documents:** [`10_Architecture/Engineering_Architecture_Handbook.md`](../10_Architecture/Engineering_Architecture_Handbook.md), [`00_Product/Roadmap.md`](Roadmap.md), [`00_Product/Product_Vision.md`](Product_Vision.md)

---

# VidhiDesk Product Constitution v1.0

**Status:** Ratified
**Scope:** Enduring product philosophy. Not a technical specification.
**Audience:** Founders, product leaders, architects, engineers, legal experts, designers, QA teams, and future AI agents working on this codebase.

This document does not describe how VidhiDesk is built. It describes why VidhiDesk exists, whom it serves, and the values that should resolve any disagreement about what to build next. When a technical decision and this constitution appear to conflict, the constitution wins — the technical decision should be revisited, not the other way around. Implementation documents (`/docs/01` onward) describe the *current* system. This document describes what must remain *true* regardless of which system implements it.

---

## 1. Product Vision

A working Indian advocate should never have to choose between the speed of AI assistance and the certainty that every citation, every clause, and every statutory claim they put in front of a client or a court is real.

VidhiDesk exists to make that choice unnecessary — to give a solo or small-practice advocate the drafting speed of a large firm's associate pool, without importing the single failure mode that makes legal AI dangerous: confident fabrication.

The vision is not "AI that writes legal documents." It is "AI assistance that a advocate can trust precisely because it is architecturally incapable of lying to them about what is verified and what is not."

## 2. Mission

To give practicing Indian advocates a private, always-available drafting and research partner that:

- accelerates the mechanical parts of legal work (structure, boilerplate, first-draft clause language, citation lookup, cross-referencing),
- never asks the advocate to trust it — only to *verify* it, quickly, because the system has already done the work of separating fact from inference,
- and gets out of the way for everything that requires judgment, strategy, or the advocate's professional signature.

VidhiDesk's job is to compress the time between "I need a draft" and "I have something worth reviewing" — not to compress the advocate out of the loop.

## 3. Target Users

**Primary user:** A practicing Indian advocate running an independent or small practice, who:
- handles a mix of contracts, litigation, real estate/RERA, and advisory work,
- has deep legal judgment but limited time and no large support staff,
- is personally and professionally liable for everything that leaves their desk,
- works across Hindi, English, and Hinglish in the ordinary course of practice.

**Secondary users (as the product matures):** Junior associates or clerks working under an advocate's supervision, who prepare drafts for the advocate's review but do not have final authority to release work product.

**Explicitly not the user:** The advocate's client. VidhiDesk is a practitioner tool, not a client-facing legal-advice product, and every design decision should be made from the advocate's chair, not the client's.

## 4. Product Principles

1. **Draft, never deliver.** VidhiDesk produces material for professional review. It does not produce final output. This is a permanent posture, not a maturity stage the product will "graduate" out of.
2. **Speed serves judgment, not replaces it.** Every efficiency gain must shorten the path to an informed decision by the advocate — never shorten the advocate out of the decision.
3. **Transparency over polish.** A rough answer that clearly shows its own uncertainty is worth more than a smooth answer that hides it. VidhiDesk should look less finished when it is less sure.
4. **One advocate's practice, faithfully modeled.** The product is built around how one real advocate (and practitioners like him) actually work — not around an abstract ideal of "legal tech." Features earn their place by fitting how legal work is actually done in Indian practice, not by matching what generic legal-AI products do elsewhere.
5. **Every module obeys the same trust contract.** Contracts, Litigation, RERA, and Consulting are different domains, but a citation, a clause, or a statutory reference must mean the same thing — verified or clearly flagged as unverified — no matter which module produced it.

## 5. AI Principles

1. **The model proposes; the system disposes.** Language models are treated as fallible drafting assistants, never as sources of legal fact. Anything that looks like a fact (a citation, a section number, a party's identity, a filing deadline) must be checked against a verified source before it is allowed to render as a fact. This is enforced in code, not requested in a prompt.
2. **Structure is never improvised.** The shape of a legal document — its skeleton, its required clauses, its formal boilerplate — comes from vetted templates, not from what a model generates freely. The model's creative latitude is confined to filling bespoke language inside a structure a human has already approved.
3. **No orphaned claims.** Every statutory or factual assertion the AI surfaces must trace back to something retrievable and inspectable — a retrieved statute chunk, a verified citation record, a document in the matter file. A claim that cannot be traced is not displayed as a claim; it is displayed as a flag.
4. **Uncertainty is a first-class output, not an edge case.** "I don't know" and "this needs manual verification" are correct, expected, frequent outputs — not failures of the system. A model that never expresses uncertainty is a model whose uncertainty has been hidden, not eliminated.
5. **Provider-agnostic, but not principle-agnostic.** Which LLM vendor answers a given request is an implementation detail that may change. The requirement that its output be masked, grounded, and verified before it reaches the advocate is not.
6. **Every AI action is a paper trail.** What was asked, which model answered, what evidence was retrieved, and what the model said must be reconstructable after the fact. An advocate must be able to explain, if ever asked, exactly how a draft came to say what it says.

## 6. Legal Safety Principles

1. **Nothing unverifiable wears the clothing of something verified.** A citation without a confirmed source renders as visibly, unmistakably unverified — never as a normal, trustworthy-looking link. The visual distinction between "checked" and "not yet checked" must survive every redesign.
2. **Silence is safer than confident error.** Where the system cannot confirm something, it must say so plainly rather than fill the gap with a plausible-sounding guess. A blank space the advocate must fill in by hand is an acceptable outcome. A wrong answer presented as right is not.
3. **The advocate's professional judgment is the last gate, always.** No output — however well-sourced — reaches a client or a court without passing through the advocate's own review. VidhiDesk's job is to make that review fast and well-informed, never to make it skippable.
4. **Every surface confesses what it is.** Any place an advocate might act on AI output must be visibly labeled as AI-assisted and subject to review. This label is not a legal disclaimer bolted on for liability's sake — it is an honest description of the workflow, and it must stay honest as the product grows.
5. **Client confidentiality is non-negotiable, not a feature.** Client-identifying information does not leave the advocate's control in a form a third party could read. This constraint applies to every present and future integration, including ones not yet imagined, and is never traded away for capability or convenience.
6. **When in doubt, degrade toward caution.** If a choice must be made between a more capable but less verifiable behavior and a less capable but safer one, VidhiDesk chooses safety. Capability can be added later; a trust failure cannot be walked back.

## 7. UX Principles

1. **Review should be faster than re-drafting from scratch.** The entire value proposition collapses if checking VidhiDesk's work takes as long as doing the work manually. Every screen should be designed around the question: "how quickly can the advocate confirm or reject this?"
2. **Confidence is shown, not just told.** Verified and unverified material must be visually distinguishable at a glance, without requiring the advocate to read fine print or hover for a tooltip.
3. **The advocate stays the author.** The interface should feel like a very fast, very well-read junior associate handing over work for review and edits — not like a black box issuing verdicts.
4. **No dead ends.** Every flagged, uncertain, or unverified item comes with a clear next action the advocate can take (verify manually, request a re-check, edit directly) — never a stop sign with nowhere to go.
5. **Bilingual by default, not as a bolt-on.** Hindi, English, and Hinglish input are all first-class, ordinary usage — not a special mode the product occasionally needs to accommodate.
6. **Respect the advocate's time above all other metrics.** Engagement, session length, and feature usage are not goals. Time saved on trustworthy output is the only metric that matters.

## 8. Engineering Principles

1. **Trust-critical logic lives in code, not in prompts.** Citation verification, PII masking, and structural integrity are enforced by deterministic system logic that a language model cannot talk its way around, regardless of what any prompt says.
2. **Every AI-influenced output is auditable after the fact.** The system must always be able to answer "why did it say this?" — with the prompt, the model, and the sources on record, not reconstructed from memory or logs of last resort.
3. **Correctness-critical modules are guarded by tests that must never regress.** Certain components — the citation verifier, the PII masker — are load-bearing for the product's entire premise. Their tests are not ordinary tests to be relaxed under deadline pressure.
4. **Design for graceful degradation, not graceful failure.** When a dependency (a model provider, an external API) is unavailable, the system should fail toward "do less, safely" — never toward "do the same thing with weaker guarantees and no indication that anything changed."
5. **Secrets, keys, and credentials never enter code, logs, or history.** This is an absolute, not a best-effort convention.
6. **Simplicity is a safety property, not just an aesthetic preference.** A system this dependent on correct enforcement of trust rules must remain simple enough for a human to reason about end-to-end. Complexity that cannot be justified by user value is a liability, not neutral.

## 9. Data Principles

1. **The advocate owns their data, fully and always.** Matter data, drafts, and client information belong to the advocate. VidhiDesk is a custodian, not an owner.
2. **Data minimization toward third parties.** Only what is strictly necessary to produce a useful draft leaves the advocate's environment for external processing, and identifying information is protected in transit to any third-party system by default, not as an opt-in.
3. **Every matter is an island.** One client's data must never leak into another client's context, draft, or retrieval results — enforced structurally, not by convention.
4. **Provenance is retained, not just the final artifact.** The system keeps not only what was produced, but where it came from — sources, versions, and the chain from question to answer — for as long as the advocate might reasonably need to explain their work.
5. **Deletion means deletion.** When an advocate removes a matter or a document, the system's obligation is to actually remove it from every place it was copied to for processing, not merely to hide it from the interface.

## 10. What VidhiDesk Will Never Become

- **An autonomous legal-advice service.** VidhiDesk will never generate output intended to reach a client or a court without a human advocate's review and sign-off standing between the two.
- **A citation-generating black box.** VidhiDesk will never present an unverified legal reference as though it were confirmed, regardless of how confident the underlying model sounds, and regardless of commercial pressure to seem more capable than it is.
- **A free-form document generator.** VidhiDesk will never let a language model invent legal structure from scratch. Structure is always human-vetted; the model's role is bounded.
- **A data broker.** VidhiDesk will never monetize, aggregate, or repurpose client-identifying information gathered in the course of an advocate's practice, for any purpose beyond serving that advocate's own matter.
- **A replacement for legal judgment.** No amount of model capability changes VidhiDesk's role from assistant to decision-maker. This is a permanent boundary, not a current limitation awaiting better technology.
- **A multi-tenant platform that dilutes trust for scale.** If growth ever requires loosening the verification, masking, or review guarantees that define the product, that growth is the wrong growth.
- **A generic "AI for lawyers" product.** VidhiDesk stays anchored to the realities of Indian practice — its statutes, its citation ecosystem, its languages, its procedural conventions — rather than drifting toward a jurisdiction-agnostic tool that serves no jurisdiction particularly well.

## 11. Long-Term Product Roadmap

The roadmap is expressed as an expanding circle of trustworthy usefulness, not as a fixed feature list. Order and pace may change; direction should not.

1. **Foundation of trust.** Citation verification and PII masking exist and are proven reliable before any user-facing module is considered complete. Nothing is built on top of an unverified foundation.
2. **Contracts.** Structured drafting assistance for agreements, using fixed skeletons with AI-assisted bespoke clauses, fully reviewed and versioned.
3. **Litigation support.** Case research, citation-backed argument assistance, and procedural drafting grounded in verified sources, extending the same trust contract into a higher-stakes domain.
4. **Consulting & litigation support.** Broader advisory drafting and analysis, building on a proven citation and grounding infrastructure.
5. **RERA / Real estate.** Domain-specific extensions once the core trust and drafting infrastructure has been validated across multiple practice areas.
6. **Depth over breadth, thereafter.** Once the four modules are solid, future growth should deepen reliability, coverage of Indian states, and quality of review workflows before it pursues breadth into new jurisdictions, new user types, or adjacent products.
7. **Collaboration, cautiously.** Multi-user support (e.g., associates preparing work for an advocate's review) is a natural extension, but only once the review and audit trail can cleanly express *who* is responsible for *what*, at every step.
8. **The bar for every future capability:** it must make verified, reviewable output faster to produce — not just more output, and not less-verified output produced faster.

## 12. Decision-Making Principles

When a decision is not clearly answered by the documents above:

1. **Ask who bears the consequence.** If a choice could result in an advocate relying on something false, resolve it in favor of the advocate's safety, even at the cost of capability, polish, or speed of delivery.
2. **Prefer the reversible choice.** Between two reasonable options, prefer the one that is easier to walk back if it turns out to be wrong.
3. **When documents conflict, this constitution outranks implementation plans, and implementation plans outrank convenience.** A technical shortcut that violates a principle in this document is not a valid shortcut, regardless of deadline pressure.
4. **Escalate genuine ambiguity rather than resolve it silently.** If a decision materially affects legal safety, client confidentiality, or the advocate's trust in the system, and this document does not clearly resolve it, the right move is to ask the advocate or product owner — not to guess and ship.
5. **Optimize for the practice, not the demo.** A feature that looks impressive but doesn't survive contact with a real advocate's actual daily workload is not a success, regardless of how well it performs in isolation.
6. **When technology changes, re-derive the implementation — never the values.** Model providers, frameworks, and infrastructure are expected to change over the life of this product. The principles in this document are written to survive that change; any conflict between a new technical possibility and a principle here should be resolved by changing the technical plan.

---

*This constitution should be revisited deliberately and rarely — through explicit amendment, not through drift. If lived practice diverges from what is written here, that is a signal to reconcile the two openly, not to let the document go quietly stale.*
