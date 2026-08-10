> **Title:** ADR-005 — Zero-Hallucination Citation Verification Gate
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers, legal
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes — this is the product's central architectural decision
> **Related Documents:** [`../../00_Product/Product_Constitution.md`](../../00_Product/Product_Constitution.md) §6, [`../../10_Architecture/AI_Architecture.md`](../../10_Architecture/AI_Architecture.md)

---

# ADR-005: Zero-Hallucination Citation Verification Gate

## Status
Accepted from project inception. This is the product's stated reason to exist.

## Context
The advocate's pre-existing workflow with generic AI tools (ChatGPT) required re-opening every cited judgment on Indian Kanoon to manually confirm it exists before trusting it. The founding acceptance criterion for this entire product is: *if this tool does not eliminate that second check, it has failed.* Generic LLMs fabricate plausible-sounding case citations at a rate that makes them unusable for legal work without independent verification.

## Decision
Every case citation proposed by an LLM is resolved against the Indian Kanoon API by case name, year, and court before it can render as anything other than an explicit warning. The renderer refuses to display a live hyperlink for any citation unless a verified `ik_id` exists in the database — enforced in code (a rendering-layer check against a database field), not merely requested in a prompt. Citations that fail verification render grey, with no link, labeled "Unverified — confirm manually (may exist only on SCC/Manupatra)," never presented as fact.

## Alternatives Considered
Prompt-only instruction ("only cite real cases") was the implicit baseline every generic AI tool already uses and was explicitly rejected as insufficient — an LLM's confidence in its own output is not evidence of accuracy, and a prompt instruction has no mechanism to prevent a hallucinated citation from being displayed. Paid citation sources (Manupatra, SCC Online) were investigated as a complement, but assumed unavailable by design (Indian legal publishers are historically restrictive about third-party/AI access) — the product was built to not depend on that access being granted, with such judgments deep-linked and labeled "subscription required" rather than fabricated or silently dropped.

## Consequences
- This is one of two subsystems (with PII masking) explicitly called out as "must never regress," carrying its own dedicated test suite.
- Every citation-bearing surface across all four modules must route through the same verifier and renderer gate — no module gets a citation shortcut.
- Verified citations are cached (cache-first) to conserve Indian Kanoon API quota; unresolved citations are retried once with a normalized query before falling back to the unverified label.
- The Phase 2 (Litigation) release gate is explicitly citation-count-based: 100 generated citations audited, target zero fabricated citations reaching the user — a stricter bar than a typical feature-completeness gate.

## Source
`CLAUDE.md` Hard Rule 1 ("Citation Gate"); `90_Historical/Original_Technical_Requirements.md` §3.3; `90_Historical/Original_Project_Plan_Revised.md` §3 ("The verification gate (non-negotiable)"); `30_Implementation/Technical_Design/Litigation_Module_Architecture.md` §7 and §13 (risk register: "Case Citation Hallucination — High (P0)").
