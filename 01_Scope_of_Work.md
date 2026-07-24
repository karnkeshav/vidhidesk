# Scope of Work (SOW)
## Project: "VidhiDesk" — AI Legal Assistant for Independent Practice (Working Title)
**Version:** 1.0 (Phase 1) | **Date:** 23 July 2026
**Product Owner:** Nitesh (Advocate) | **Developer:** Keshav
**Source:** Requirements call transcript (Nitesh ↔ Keshav) + follow-up brainstorming

---

## 1. Project Overview

A private, web-based AI assistant for a practicing Indian lawyer transitioning to independent / freelance consulting work. The tool is an **internal lawyer's assistant** — the lawyer always vets the output before it reaches any client. It is NOT a public-facing legal advice product in Phase 1.

The core promise, taken directly from the transcript: *every output must be authentic and verifiable* — no hallucinated citations, every judgment linked to a real, clickable source (Indian Kanoon), so the lawyer does not have to re-verify on a third-party site.

### 1.1 The Dashboard (Entry Point)
A single dashboard with **four modules** (tiles). Clicking a tile opens that module's workspace:

1. **Litigation**
2. **Contracts**
3. **RERA / Real Estate**
4. **Consulting & Litigation Support**

---

## 2. Module Scope — Phase 1

### 2.1 Module 1: Litigation

A chat interface (ChatGPT/Claude-style) with a legal reasoning pipeline behind it.

**User flow (as agreed on the call):**
1. Lawyer types a fact situation or query (free text, Hindi/English/Hinglish accepted).
2. System **validates** the query — confirms it is a legal/litigation matter and classifies it (civil / criminal / labour / consumer / other).
3. System returns the **applicable laws and specific provisions** (e.g., BNS sections, CPC/CrPC-BNSS provisions, special acts) with plain-language explanation of why each applies.
4. On request, system **drafts** the document (plaint, complaint, reply, legal notice, application) incorporating those provisions.
5. Drafts include **supporting case law citations** (Supreme Court / relevant High Court) — and this is the hard requirement:
   - Every citation must carry a **hyperlink to the actual judgment on Indian Kanoon**.
   - Citations are verified via the **Indian Kanoon API** before being shown.
   - Anything the AI proposes that cannot be verified on Indian Kanoon is either dropped or clearly flagged **⚠ Unverified — confirm manually** (never presented as fact).

**Explicitly out of scope, Phase 1:** Manupatra and SCC Online integration (paid APIs; violates the freeware constraint). Judgments available only on those platforms will show name + citation with the Unverified flag.

**Acceptance criteria:**
- AC-1.1: A fact pattern (e.g., courier company damages goods in transit Delhi→Mumbai) returns the governing statute (Carriage by Road Act, Consumer Protection Act 2019) with section numbers.
- AC-1.2: 100% of hyperlinked citations open a real Indian Kanoon judgment page.
- AC-1.3: Zero unflagged unverifiable citations in output.
- AC-1.4: Draft documents are downloadable as .docx.

### 2.2 Module 2: Contracts

The largest portfolio for the lawyer's corporate/freelance work.

**User flow:**
1. Clicking "Contracts" shows a **library of 25–30 contract types** (list in Appendix A).
2. Lawyer selects a type (e.g., NDA) → a **guided intake form + chat** appears:
   - Party A details, Party B details (name, entity type, address, role — e.g., Disclosing / Receiving Party)
   - Purpose of the contract, key commercial terms
   - Confidentiality items, tenure ("during subsistence of contract" or fixed years)
   - **Jurisdiction selector:** Central (India-wide) or a specific **State** (Maharashtra, UP, Delhi, Bihar…)
3. System generates the draft **within minutes**, aligned with **prevailing Indian law** (Indian Contract Act 1872, Transfer of Property Act 1882, IT Act, state stamp acts, etc.).
4. Where state-specific rules apply (stamp duty, registration, rent control), the system shows a short **"State law notes"** panel alongside the draft.
5. **Amendment loop:** lawyer gives change commands in chat ("reduce lock-in to 12 months", "add arbitration seat Delhi") → system produces a revised draft, tracked as versions v1, v2, v3…

**Acceptance criteria:**
- AC-2.1: All 25 Phase-1 templates generate a complete, internally consistent draft from the intake form.
- AC-2.2: Selecting a state changes stamp-duty / registration notes accordingly.
- AC-2.3: Amendment commands produce a new version without losing prior versions.
- AC-2.4: Drafts export to .docx and .pdf.

### 2.3 Module 3: RERA / Real Estate

Two halves, exactly as described on the call:

**(a) Real-estate litigation support**
- Draft **RERA complaints** (delayed possession, substandard construction, refund + interest claims) against builders.
- **Step-by-step guided walkthrough of online RERA complaint filing** — state-specific (each state authority has its own portal, fees, forms). Authentic, sourced from official state RERA websites, so the lawyer never needs third-party confirmation.
- Central RERA Act 2016 + the selected **state's RERA Rules** (penalties and procedure differ by state).

**(b) Property transaction drafting** (Transfer of Property Act family)
- Lease deed, Leave & License, Sale Agreement / Agreement to Sell, Sale Deed, Gift Deed, Mortgage Deed, Relinquishment Deed — with the same state selector and state-law notes as Module 2.
- An explainer command ("types of transfer of property in India") returns a structured bullet overview (sale, mortgage, lease, exchange, gift, actionable claims).

**Phase 1 state coverage:** Delhi, Maharashtra, UP, Bihar, Haryana (expandable). Other states fall back to Central Act + a "verify state rules" flag.

**Acceptance criteria:**
- AC-3.1: A delayed-possession fact pattern produces a filing-ready RERA complaint draft citing RERA Act §18 etc.
- AC-3.2: Filing walkthrough for the 5 priority states matches the official portal steps (manually verified at build time, with source links).

### 2.4 Module 4: Consulting & Litigation Support

A general-purpose "which law covers this?" engine across all Indian laws — for matters **outside the lawyer's core expertise** (customs seizure at airport, carriage/courier damage, defective mobile phone, etc.).

**User flow:**
1. Lawyer enters facts (own client's or a referred matter).
2. System returns: **applicable law(s) + specific sections + correct forum** (consumer commission tier, RERA authority, civil court, tribunal) + available remedies/compensation heads + limitation period.
3. **Litigation Support mode:** for matters where another advocate is arguing, the system produces a **strategy brief** — arguments, counter-arguments, supporting provisions and verified case law — that Nitesh can relay to the client/their counsel remotely.

**Acceptance criteria:**
- AC-4.1: The transcript's own test cases pass: (i) customs-seized goods → Customs Act 1962 sections + provisional release route; (ii) defective mobile → Consumer Protection Act 2019, correct forum by claim value, compensation heads.
- AC-4.2: Every cited judgment follows the same Indian Kanoon verification rule as Module 1.

---

## 3. Cross-Cutting Requirements

| # | Requirement |
|---|---|
| X-1 | **Citation authenticity is non-negotiable.** Verified-on-Indian-Kanoon or flagged. This is the product's core differentiator vs. plain ChatGPT. |
| X-2 | **Human-in-the-loop:** every screen carries "Draft for advocate review — not legal advice." The lawyer vets before client sees anything. |
| X-3 | **Bilingual input** (Hindi/English/Hinglish); output in English legal drafting by default, Hindi on request. |
| X-4 | **Freeware constraint:** only free/open-source tools and free API tiers. The single already-procured exception: the Indian Kanoon API held by the Product Owner. |
| X-5 | **Client confidentiality:** party names and facts are sensitive; single-user auth, encrypted storage, no data used for model training. |
| X-6 | Matter history: every chat/draft saved and searchable by client/matter name. |

## 4. Out of Scope — Phase 1
- Manupatra / SCC Online APIs (paid)
- Cause-list tracking, court e-filing integration, billing/invoicing
- Multi-user / client-facing portal
- Automated "is this judgment still good law" analysis
- Mobile app (responsive web only)

## 5. Deliverables
1. Deployed web app (free-tier hosting) with the four modules
2. Contract template library (25 templates, Appendix A)
3. Statute knowledge base (indexed bare acts, Appendix B)
4. RERA filing guides for 5 states with official source links
5. Admin guide + template-editing guide for the Product Owner

## 6. Success Criteria (Phase 1 exit)
- Nitesh uses the tool on ≥10 real matters across all four modules
- Zero incidents of an unflagged fake citation reaching a draft
- Contract turnaround (intake → vetted draft) under 30 minutes
- Total recurring cost: ₹0 beyond the existing Indian Kanoon API plan

---

## Appendix A — Phase 1 Contract Library (25)
1. Non-Disclosure Agreement (mutual & one-way)
2. Joint Venture Agreement
3. Software Development Agreement
4. Service Agreement / Master Service Agreement
5. Consultancy / Retainer Agreement
6. Employment Agreement
7. Freelancer / Independent Contractor Agreement
8. Partnership Deed
9. Founders' Agreement
10. Shareholders' Agreement
11. Memorandum of Understanding
12. Franchise Agreement
13. Distribution Agreement
14. Agency Agreement
15. Supply / Vendor Agreement
16. Loan Agreement
17. Promissory Note
18. Lease Deed (residential / commercial)
19. Leave & License Agreement
20. Agreement to Sell (immovable property)
21. Sale Deed
22. Gift Deed
23. Mortgage Deed
24. Power of Attorney (general & special)
25. Settlement / Compromise Agreement
(+ IP Assignment, Will, Relinquishment Deed as stretch items)

## Appendix B — Core Statute Knowledge Base (initial index)
Indian Contract Act 1872 · Transfer of Property Act 1882 · Registration Act 1908 · Indian Stamp Act 1899 + state stamp acts · RERA 2016 + state rules (5 states) · Consumer Protection Act 2019 · BNS 2023 / BNSS 2023 / BSA 2023 (and IPC/CrPC/Evidence Act for pending matters) · CPC 1908 · Specific Relief Act 1963 · Arbitration & Conciliation Act 1996 · Customs Act 1962 · Carriage by Road Act 2007 · IT Act 2000 · Limitation Act 1963
