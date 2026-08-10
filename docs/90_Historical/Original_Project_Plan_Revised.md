> **Title:** Original Project Plan — Revised (Contracts-First, Citation Policy)
> **Version:** 1.0 (as originally issued, revised after IK API procurement)
> **Status:** Historical
> **Owner:** Keshav
> **Audience:** Historical record for founders, engineers, future AI agents
> **Last Updated:** 23 July 2026 (frozen; not maintained further)
> **Canonical Reference:** No — see Superseded By
> **Supersedes:** [`Original_Scope_of_Work.md`](Original_Scope_of_Work.md) (build order only), [`Original_Implementation_Plan.md`](Original_Implementation_Plan.md) (build order only)
> **Superseded By:** [`00_Product/Roadmap.md`](../00_Product/Roadmap.md) (phasing), [`30_Implementation/ADR/`](../30_Implementation/ADR/) (citation gate, contracts-first, and freeware-constraint decisions extracted as standalone ADRs), [`30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md) (live status)
> **Reason:** This document was previously the CLAUDE.md-designated tie-breaker ("where /docs conflict, this file wins") and Build Tracker's "authoritative for build order and phasing" source. As of this documentation refactor, the Product Constitution and the Documentation Precedence Policy (`docs/README.md`) now hold that role, and this plan's live decisions have been extracted into the Roadmap and ADRs so they carry forward with current status rather than a July 2026 snapshot. Preserved verbatim as the original decision record — the citation-verification design in §3 and the "working without sample drafts" quality process in §6 are still the accurate account of why those mechanisms exist.
> **Related Documents:** [`Original_Scope_of_Work.md`](Original_Scope_of_Work.md), [`Original_Implementation_Plan.md`](Original_Implementation_Plan.md)

---

# Project Plan — AI Legal Assistant for an Independent Advocate

**Client / Domain Expert:** Nitesh (Delhi-based advocate, moving from employment → independent & online practice)
**Build:** Keshav
**Date:** 23 July 2026
**Status of this document:** Working plan, revised after two confirmations — (1) the Indian Kanoon API has been procured, (2) no sample client drafts will be supplied.

---

## 1. What the tool is

Not a chatbot with a legal skin. It is a **retrieval-grounded drafting and research assistant** in which the lawyer remains the final authority on every output.

Nitesh's current workflow defines the acceptance criterion: he uses ChatGPT for office work, then re-opens each citation on Indian Kanoon to confirm it exists before trusting it. **If this tool does not eliminate that second check, it has failed.**

Core design principle: *no output without a resolvable source.* The system flags or refuses rather than guessing.

---

## 2. The four modules

| Module | Core function | Output |
|---|---|---|
| **Litigation** | Query → validate it is a litigation matter → identify applicable law and sections → draft the pleading | Draft + citations with working links |
| **Contracts** | Select contract type (25–30 in a library) → enter party details and commercial terms → generate, then amend by command | Draft aligned to prevailing Indian law, jurisdiction-aware |
| **RERA / Real Estate** | Transfer-of-property drafting (lease, licence, sale deed, gift deed, mortgage) + RERA complaints + online filing walkthrough | Drafts plus step-by-step procedural guidance |
| **Consulting & Litigation Support** | Facts in → applicable statute, provisions, correct forum, remedy, quantum | Structured advisory note; strategy brief for matters argued by another advocate |

### Build order

**Contracts first, not Litigation.** Contracts is the largest revenue portfolio ("the major, major, major part of any lawyer's life"), is template-driven, and carries near-zero citation-hallucination risk — so something usable ships in weeks. Litigation is the harder problem and is the area where Nitesh's own expertise makes him *least* dependent on the tool.

This inverts the sequencing assumed on the call and is worth an explicit decision before Phase 1 starts.

---

## 3. Citation authenticity — the core problem

### 3.1 Resolved: Indian Kanoon API is secured

This settles the corpus question. Indian Kanoon becomes the canonical citation source and the link target for every verified judgment.

Remaining work on it is integration, not procurement:

- Confirm per-document pricing, quota, and rate limits
- Build a thin API client with a **cache-first** design — never re-fetch a judgment already verified and stored
- Search-first, fetch-on-demand: resolve a citation via search, only pull the full document when Nitesh clicks through

### 3.2 Unresolved: SCC Online and Manupatra

The call assumed 90–95% of platforms expose APIs. That assumption is unsafe for Indian legal publishers, who monetise licensed, editorially-enhanced content and are historically restrictive about third-party access — particularly for AI products.

**Plan as if this access will not be granted.** Treat it as upside if it is.

Fallback behaviour for judgments not on Indian Kanoon: do not fake it and do not silently drop it. Show the citation with a clear label — *available on SCC Online / Manupatra, subscription required* — plus a deep link. Nitesh opens it in his own subscription. Honest, and still saves him time.

### 3.3 Supplementary free sources

- **Supreme Court** — official judgment portal and DigiSCR (free, authoritative)
- **High Court portals** — judgments published free per court
- **eCourts / NJDG** — case status and cause lists
- **India Code** — central and state bare acts

### 3.4 The verification gate (non-negotiable)

1. Model generates the draft with proposed citations
2. Every citation is resolved against Indian Kanoon by case name + year + court
3. Unresolvable citations are **stripped and flagged**, never passed through silently
4. Surviving citations render as hyperlinks that open the actual judgment

Enforced in code, not in the prompt. The renderer refuses to output a live hyperlink unless a verified document ID exists in the database.

---

## 4. Architecture

- **Frontend:** Next.js dashboard — four module tiles, chat pane per module, document viewer
- **Backend:** Python (FastAPI)
- **Retrieval:** Postgres + pgvector; hybrid semantic + keyword search over bare acts, judgments, and rules
- **Generation:** Claude/GPT-class model with tool-calling for corpus search and citation resolution
- **Contracts:** structured, versioned clause bank — not free-form generation. Boilerplate and structure are fixed; the model fills bespoke clauses inside that skeleton
- **Export:** .docx, formatted for track-changes review
- **Jurisdiction layer:** state metadata on every rule and template, so "Maharashtra sale agreement" and "Bihar sale agreement" resolve differently

---

## 5. Phasing

### Phase 0 — Scope freeze and template sourcing (3 weeks)

*Extended from 2 weeks because the template inputs now have to be built rather than supplied.*

- Indian Kanoon API spike: auth, endpoints, response shapes, quota, cost per call
- Send written API enquiries to SCC Online and Manupatra, so the answer is definitive rather than assumed
- Nitesh supplies the ChatGPT-compiled list of in-demand contract types he mentioned on the call
- **Template sourcing (see §6)** — assemble first-draft skeletons for the initial 10 contracts from public sources
- Lock module scope; everything else goes to a written backlog

### Phase 1 — Contracts MVP (8–10 weeks)

*Extended from 6–8 weeks: without gold-standard drafts, template quality has to be reached through review cycles instead.*

- 10 highest-frequency contract types: NDA (mutual and one-way), Joint Venture, Software Development, Lease, Leave & Licence, Agreement to Sell, Employment, Service Agreement, MoU, Consultancy/Retainer
- Two-party intake form plus free-text requirement capture
- Draft → review → amendment loop by chat command ("reduce lock-in to 12 months", "add arbitration seat Delhi"), with versions preserved
- Indian Contract Act and Stamp Act compliance checks; jurisdiction selector for three states initially (Delhi, Maharashtra, UP)
- **Gate:** Nitesh runs 10 real matters through it. Target: 8/10 usable with only minor edits.

### Phase 2 — Litigation and the citation engine (6–8 weeks)

- Corpus ingestion: central bare acts, Supreme Court, Delhi HC, Bombay HC
- Query validation, provision identification, pleading drafting
- Full citation verification and hyperlinking through the Indian Kanoon API
- **Gate:** 100 generated citations audited. Target: zero fabricated citations reaching the user.

### Phase 3 — RERA and Consulting (6 weeks)

- Transfer of Property Act drafting suite — lease, licence, sale deed, gift deed, mortgage, relinquishment
- RERA complaint drafting (delayed possession, substandard construction, refund with interest) plus filing walkthroughs, starting with Delhi RERA, UP-RERA and MahaRERA, each step carrying its official source link
- Consulting module: facts → applicable law → forum → remedy → limitation
- Litigation-support mode: guidance framed for relay to a client or their counsel, not for filing

### Phase 4 — Productisation (post-launch, ongoing)

Multi-user, matter management, billing, client portal — only after Nitesh has used the tool in live practice for four to six weeks.

---

## 6. Working without sample drafts

This is the significant change to the plan and the main new risk. Without Nitesh's past drafts there is no gold standard for what "good" looks like in his practice, no house style, and no worked examples to steer generation.

### Substitute inputs

| Source | Use |
|---|---|
| Bare acts and schedules (India Code) | Mandatory clauses, statutory formalities, stamp and registration requirements |
| Model forms in statutes and rules | Several instruments have prescribed or indicative forms — treat these as authoritative skeletons |
| Standard practitioner form books and drafting texts | Structural reference for clause ordering and coverage; used as reference, not copied |
| Publicly filed contracts (SEBI/exchange disclosures by listed Indian companies) | Real, executed, India-law-governed commercial drafting for JV, software development, service agreements |
| Registered deeds available on state registration portals | Real-world formatting for sale, lease, gift deeds |
| Judgments on disputed clauses | Which clause formulations survive litigation — sourced through the Indian Kanoon API we now hold |

### Revised quality process

Because there is no example to match, correctness has to come from review rather than imitation:

1. **Skeleton first.** Keshav builds each template from statute plus public sources.
2. **Clause-by-clause review.** Nitesh reviews each template clause by clause and marks each one *keep / redraft / delete*, rather than approving whole documents. Slower per template, but it produces the house style that the missing drafts would have provided.
3. **Cadence.** Two templates per week through Phase 1. Ten templates therefore takes five weeks of Nitesh's review time, running in parallel with development.
4. **Beta labelling.** Any template not yet clause-reviewed ships marked "beta — unreviewed skeleton" and is excluded from the Phase 1 gate.
5. **Learn from live use.** Every edit Nitesh makes to a generated draft is captured. After ~20 real matters, those edits are the corpus the sample drafts would have been — fold them back into the templates.

### Consequences to accept

- Phase 1 is roughly two weeks longer
- Early drafts will read generically until Nitesh's edits accumulate
- **Nitesh's time commitment rises from ~4 to ~6 hours per week during Phase 1.** Without sample drafts, his review *is* the specification. If that time is not available, the honest options are to cut the initial library from 10 templates to 5, or to accept a longer Phase 1 — not to ship unreviewed templates.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| No SCC/Manupatra API access | Indian Kanoon is now the backbone; paywalled judgments labelled and deep-linked, never fabricated |
| Indian Kanoon quota or per-call cost exceeds budget | Cache-first architecture; verify only citations that survive into a final answer |
| No gold-standard drafts → generic or incomplete contracts | §6 process: statute-grounded skeletons, clause-by-clause review, beta labelling, edit capture |
| Hallucinated citations destroy trust | Hard verification gate; refuse rather than guess |
| Client confidentiality and privilege | No-training terms with the model provider, encryption at rest, India data residency where feasible, per-matter access logs |
| Scope creep | Phase 0 freeze; written backlog; nothing enters before Phase 3 completes |
| Domain-expert bandwidth | ~6 hrs/week during Phase 1, non-negotiable; if unavailable, cut library size rather than skip review |
| Bar Council of India advertising rules | Review BCI Rules (Chapter II, Part VI) before any public-facing marketing of legal services |
| State-law breadth | Three states done well rather than twenty-eight done badly |
| Old-law vs new-law confusion (IPC ↔ BNS) | Offence-date disambiguation rule plus a dual mapping table |

---

## 8. Success metrics

- **Citation accuracy:** 100% of surfaced citations resolve to a real judgment
- **Zero-recheck rate:** proportion of outputs Nitesh accepts without separately opening Indian Kanoon — target above 90%
- **Draft turnaround:** first usable contract draft in under five minutes
- **Template maturity:** proportion of the library that is clause-reviewed rather than beta — target 100% by the Phase 1 gate
- **Adoption:** matters per week run through the tool, tracked from the Phase 1 gate onward

---

## 9. Immediate next steps

1. **Keshav:** Indian Kanoon API spike — confirm quota, cost per call, and response formats; build the client and cache layer
2. **Keshav:** send API enquiries to SCC Online and Manupatra so the answer is on record
3. **Nitesh:** send the ChatGPT-compiled contract-type list; confirm the initial 10
4. **Nitesh:** confirm the ~6 hrs/week review commitment, or agree a reduced library
5. **Both:** decide Contracts-first vs Litigation-first, and record the decision
6. **Both:** agree the three priority states for Phase 1

---

*Draft plan for discussion. Nothing here is legal advice; all legal content in the tool is generated for advocate review.*
