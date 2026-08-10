> **Title:** Product Vision — Module Scope
> **Version:** 1.0
> **Status:** Active — Canonical
> **Owner:** Keshav (build) / Nitesh (product authority)
> **Audience:** Founders, product leaders, engineers, designers, future AI agents
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for what each module does and its Phase 1 acceptance bar. For *why* the product exists, see [`Product_Constitution.md`](Product_Constitution.md); for *when* things ship, see [`Roadmap.md`](Roadmap.md).
> **Supersedes:** `90_Historical/Original_Scope_of_Work.md` §1–§2 (module descriptions and acceptance criteria, carried forward here; build-order content superseded separately by Roadmap.md)
> **Related Documents:** [`Product_Constitution.md`](Product_Constitution.md), [`Roadmap.md`](Roadmap.md), [`../10_Architecture/Business_Architecture.md`](../10_Architecture/Business_Architecture.md)

---

# Product Vision — Module Scope

This document answers "what does VidhiDesk actually do, module by module." It is the practical companion to the [Product Constitution](Product_Constitution.md), which answers "why." Content here is extracted and carried forward from `90_Historical/Original_Scope_of_Work.md` §1–§2; nothing below is a new decision.

## The Dashboard

A single dashboard with four module tiles: **Litigation**, **Contracts**, **RERA / Real Estate**, **Consulting & Litigation Support**. Clicking a tile opens that module's workspace. This structure is unchanged since the original Scope of Work and remains accurate to the live product.

## Module 1 — Litigation

A chat-style interface backed by a legal reasoning pipeline: fact pattern in → query validated as a litigation matter and classified (civil/criminal/labour/consumer/other) → applicable statute and provisions returned with plain-language rationale → on request, a draft (plaint, complaint, reply, notice, application) → every case citation in the draft carries a hyperlink to the actual judgment on Indian Kanoon, verified via the Indian Kanoon API, or is flagged `⚠ Unverified — confirm manually`, never presented as fact.

**Acceptance bar (Phase 1):** a fact pattern returns the governing statute with section numbers; 100% of hyperlinked citations open a real Indian Kanoon judgment page; zero unflagged unverifiable citations; drafts downloadable as `.docx`.

## Module 2 — Contracts

The largest module by business value. Advocate picks from a library of 25–30 contract types (see Appendix A of the historical SOW for the full list) → guided intake form captures party details, commercial terms, jurisdiction (Central or a specific state) → system generates a draft aligned with prevailing Indian law within minutes → state-specific rules (stamp duty, registration) surface in a side panel → amendment loop via chat command produces new tracked versions.

**Acceptance bar (Phase 1):** all Phase 1 templates generate a complete, internally consistent draft from intake; state selection changes stamp-duty/registration notes; amendment commands version without loss; drafts export to `.docx` and `.pdf`.

## Module 3 — RERA / Real Estate

Two halves:
- **Litigation support:** RERA complaints (delayed possession, substandard construction, refund + interest) against builders, plus a state-specific guided walkthrough of online RERA complaint filing, sourced from official state RERA portals.
- **Property transaction drafting:** lease deed, leave & license, sale agreement, sale deed, gift deed, mortgage deed, relinquishment deed — same state selector and state-law-notes pattern as Contracts.

**Acceptance bar (Phase 1):** a delayed-possession fact pattern produces a filing-ready complaint citing RERA Act §18 etc.; filing walkthroughs for priority states match official portal steps.

## Module 4 — Consulting & Litigation Support

A general-purpose "which law covers this?" engine for matters outside the advocate's core expertise. Facts in → applicable law(s), specific sections, correct forum, available remedies, limitation period. In litigation-support mode, produces a strategy brief (arguments, counter-arguments, authorities) for matters another advocate is arguing.

**Acceptance bar (Phase 1):** transcript test cases pass (customs seizure → Customs Act 1962 route; defective goods → Consumer Protection Act 2019, correct forum by claim value); every cited judgment follows the same Indian Kanoon verification rule as Litigation.

## Cross-Cutting Requirements (unchanged since original SOW)

| # | Requirement |
|---|---|
| X-1 | Citation authenticity is non-negotiable — verified-on-Indian-Kanoon or flagged. |
| X-2 | Human-in-the-loop: every screen carries "Draft for advocate review — not legal advice." |
| X-3 | Bilingual input (Hindi/English/Hinglish); English legal drafting output by default. |
| X-4 | Freeware constraint: free/open-source tools and free API tiers only, except the pre-procured Indian Kanoon API. |
| X-5 | Client confidentiality: single-user auth, encrypted storage, no data used for model training. |
| X-6 | Matter history: every chat/draft saved and searchable by client/matter name. |

## Out of Scope — Phase 1

Manupatra / SCC Online APIs (paid), cause-list tracking, court e-filing integration, billing/invoicing, multi-user/client-facing portal, automated "is this judgment still good law" analysis, native mobile app.

For the current build status of each module, see [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md). For the full original template and statute library appendices, see [`../90_Historical/Original_Scope_of_Work.md`](../90_Historical/Original_Scope_of_Work.md).
