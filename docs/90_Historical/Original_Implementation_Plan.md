> **Title:** Original Implementation Plan (Litigation-First Sprint Plan)
> **Version:** 1.0 (as originally issued)
> **Status:** Historical
> **Owner:** Keshav
> **Audience:** Historical record for engineers, future AI agents
> **Last Updated:** 23 July 2026 (frozen; not maintained further)
> **Canonical Reference:** No — see Superseded By
> **Supersedes:** N/A (first implementation plan)
> **Superseded By:** [`Original_Project_Plan_Revised.md`](Original_Project_Plan_Revised.md) (build order), [`30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md) (live sprint tracking), [`00_Product/Roadmap.md`](../00_Product/Roadmap.md)
> **Reason:** This plan's Litigation → Contracts → Consulting → RERA sequence was reversed to Contracts-first before Sprint 0 closed (see `CLAUDE.md` Decision 1 and Build Tracker §1.1). Preserved verbatim as the original sequencing rationale and risk register.
> **Related Documents:** [`Original_Scope_of_Work.md`](Original_Scope_of_Work.md), [`Original_Technical_Requirements.md`](Original_Technical_Requirements.md)

---

# Implementation Plan
## Project: VidhiDesk — Phase 1
**Version:** 1.0 | **Date:** 23 July 2026
**Team:** Keshav (build) · Nitesh (domain expert, templates, testing)
**Assumed capacity:** part-time (~15–20 hrs/week dev) → **~14 weeks total**

---

## 1. Build Order & Rationale

Build sequence follows the transcript's priorities and technical dependencies:

1. **Litigation** first — it exercises the two hardest subsystems (RAG + Citation Verifier) that every other module reuses.
2. **Contracts** second — biggest business value ("major, major, major part of any lawyer's life"); depends only on the Template Engine.
3. **Consulting** third — ~80% reuse of the Litigation engine; cheap to add once Module 1 works.
4. **RERA** last — combines both engines (litigation drafting + property templates) plus state-specific curation work that Nitesh can prepare in parallel during Sprints 2–3.

---

## 2. Sprint Plan

### Sprint 0 — Foundations (Week 1)
- [ ] GitHub repo (monorepo: `/web`, `/api`, `/templates`, `/corpus`)
- [ ] Next.js scaffold on Vercel; FastAPI scaffold on Render; Supabase project (Auth + Postgres + pgvector)
- [ ] LLM Gateway with Gemini free tier + Groq fallback; Ollama on Keshav's machine for dev
- [ ] **Spike (critical): Indian Kanoon API** — confirm auth, search endpoint behaviour, per-call pricing/quota, response formats; write the thin client + caching layer
- **Exit:** "Hello matter" — login, create a matter, send a chat message that round-trips through the LLM gateway.

### Sprint 1 — Statute RAG + Citation Verifier (Weeks 2–3)
- [ ] Download & ingest Appendix-B bare acts from India Code; section-level chunking + embeddings into pgvector
- [ ] Hybrid retrieval endpoint (`facts → relevant sections`)
- [ ] Citation Verifier state machine per TRD §3.3, incl. cache table + UNVERIFIED rendering rule
- [ ] Golden test set (Nitesh writes 15 fact patterns with known correct answers, incl. the transcript's customs / courier / consumer examples)
- **Exit:** ≥12/15 golden queries return correct act + section; 0 unflagged fake citations across 50 test generations.

### Sprint 2 — Litigation Module UI + Drafting (Weeks 4–5)
- [ ] Dashboard + Litigation workspace (chat, provisions panel, citations panel with live IK hyperlinks)
- [ ] Query Validator (classify / ask follow-ups)
- [ ] Pleading drafting: legal notice, consumer complaint, civil plaint skeleton → .docx export
- [ ] Matter history + search
- **🏁 Milestone M1 (end Wk 5): Litigation module live; Nitesh starts daily use on real research.**

### Sprint 3 — Template Engine + First 10 Contracts (Weeks 6–7)
- [ ] Jinja2-docx engine + JSON-schema-driven intake forms + version/diff system
- [ ] Contracts: NDA (mutual + one-way), Service Agmt, Software Dev, Consultancy, Employment, Freelancer, MoU, JV, Lease, Leave & License
- [ ] State selector + `state_rules` table seeded for Delhi, Maharashtra, UP, Bihar, Haryana (Nitesh supplies stamp/registration data with source URLs)
- [ ] Amendment loop via chat commands
- **Exit:** NDA end-to-end test from the transcript scenario (two parties, confidential items, tenure) in <5 minutes.

### Sprint 4 — Remaining 15 Contracts + Polish (Weeks 8–9)
- [ ] Templates 11–25 (Appendix A) — Nitesh reviews 5/week in parallel
- [ ] PDF export (LibreOffice headless), clause library extraction from approved drafts
- **🏁 Milestone M2 (end Wk 9): Contracts module complete — the revenue portfolio is live.**

### Sprint 5 — Consulting & Litigation Support (Week 10)
- [ ] Consulting workspace reusing Litigation engine, output framed as: applicable law → forum → remedies → limitation
- [ ] Forum-selector logic (consumer commission tiers by claim value, RERA vs civil court, tribunal routing)
- [ ] "Litigation Support" output mode: strategy brief (arguments / counters / authorities) formatted for relay to client's counsel
- **Exit:** AC-4.1 test cases pass.

### Sprint 6 — RERA Module (Weeks 11–12)
- [ ] RERA complaint drafting (delayed possession, refund + interest, defects) grounded on RERA 2016 + state rules
- [ ] Property deed templates wired from Template Engine (sale deed, gift deed, mortgage, relinquishment)
- [ ] Filing walkthroughs for 5 states (Nitesh curates from official portals during Sprints 3–5; Keshav builds the guide renderer)
- [ ] "Transfer of property types" explainer command
- **🏁 Milestone M3 (end Wk 12): all four dashboard modules live.**

### Sprint 7 — Hardening & UAT (Weeks 13–14)
- [ ] Nitesh runs the tool on ≥10 real matters spanning all modules; bug triage
- [ ] Security pass (RLS audit, secrets rotation), dead-link re-checker job, backup/export of matters
- [ ] Admin guide + "how to add a template" guide
- **🏁 Milestone M4: Phase 1 exit criteria (SOW §6) signed off.**

---

## 3. Timeline Summary

| Weeks | Sprint | Outcome |
|---|---|---|
| 1 | S0 | Infra + IK API spike |
| 2–3 | S1 | RAG + Citation Verifier (the moat) |
| 4–5 | S2 | **M1: Litigation live** |
| 6–7 | S3 | Template engine + 10 contracts |
| 8–9 | S4 | **M2: 25 contracts live** |
| 10 | S5 | Consulting + litigation support |
| 11–12 | S6 | **M3: RERA live — full dashboard** |
| 13–14 | S7 | **M4: UAT sign-off, Phase 1 done** |

## 4. Responsibilities (RACI-lite)

| Workstream | Keshav | Nitesh |
|---|---|---|
| Architecture, code, hosting, IK API integration | **R/A** | C |
| Golden legal test set & output correctness review | C | **R/A** |
| Contract template legal content (clauses, mandatory terms) | C | **R/A** |
| State rules data (stamp duty, registration) + RERA guides | I | **R/A** |
| Weekly demo & prioritization call (Fri, 45 min) | R | R |

## 5. Dependencies & Pre-work Checklist (start immediately)
- [ ] **Nitesh → Keshav:** IK API credentials + plan/quota details (blocks Sprint 0 spike)
- [ ] **Nitesh:** the ChatGPT-compiled list of in-demand contract types (mentioned on the call) → reconcile with Appendix A
- [ ] **Nitesh:** 15 golden fact patterns with expected acts/sections
- [ ] **Keshav:** Gemini + Groq free-tier keys; Supabase + Vercel + Render accounts
- [ ] **Both:** agree the 5 priority states (assumed: Delhi, Maharashtra, UP, Bihar, Haryana)

## 6. Risk Register (delivery)
| Risk | Impact | Plan |
|---|---|---|
| IK API quota too small for verification volume | High | Cache-first design (TRD §3.3); verify only citations that survive into final answers |
| Nitesh's template-review bandwidth | Med | 5 templates/week cadence; ship module with reviewed subset, mark rest "beta" |
| Free-tier LLM quality on Hindi/Hinglish input | Med | Normalize input to English internally; test in Sprint 1; Groq 70B fallback |
| Scope creep (Manupatra, cause lists, client portal…) | Med | Parking-lot list; nothing enters before M4 |
| Part-time schedule slippage | Med | Milestones M1/M2 deliver standalone value even if M3 slips |

## 7. Phase 2 Parking Lot (post-M4, from brainstorm)
Manupatra/SCC integration (if commercially justified) · cause-list watcher + client WhatsApp updates · contradiction/chronology tools for trial prep · multi-user & client portal · billing · "still good law" citator analysis · marketing/market-capture plan.
