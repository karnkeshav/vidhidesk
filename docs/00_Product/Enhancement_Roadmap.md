> **Title:** Enhancement Roadmap — Multi-Tenancy, Litigation Objects, eCourts Integration
> **Version:** 1.0
> **Status:** Active — Approved Enhancement Plan (product discussion summary, 26 August 2026; consolidates and supersedes the "Phase 4 not started, deferred 4–6 weeks post-Phase 3" framing in [`Roadmap.md`](Roadmap.md)'s Phase 4 row for the multi-tenancy piece specifically — see Section 6)
> **Owner:** Keshav (build) / Nitesh (product authority)
> **Audience:** Founders, engineers, future AI agents
> **Last Updated:** 26 August 2026
> **Canonical Reference:** Yes, for the next build sequence (tenant foundation → master dashboard → litigation object model → eCourts integration). [`Roadmap.md`](Roadmap.md) remains canonical for Phase 0–3 history and overall phasing language; this document is the detailed plan for what comes next and should be read alongside it.
> **Supersedes:** None outright — narrows and makes concrete the "Phase 4: Productisation" line in `Roadmap.md`, and adds the platform-owner Master Dashboard as new scope not previously documented anywhere.
> **Related Documents:** [`Product_Constitution.md`](Product_Constitution.md), [`Roadmap.md`](Roadmap.md), [`Product_Vision.md`](Product_Vision.md), [`../10_Architecture/Engineering_Architecture_Handbook.md`](../10_Architecture/Engineering_Architecture_Handbook.md), [`../20_Engineering/Database_Architecture.md`](../20_Engineering/Database_Architecture.md), [`../30_Implementation/Technical_Design/Litigation_Module_Architecture.md`](../30_Implementation/Technical_Design/Litigation_Module_Architecture.md), [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md)

---

# VidhiDesk — Enhancement Roadmap

**Date:** 26 August 2026
**Context:** VidhiDesk is live at vidhidesk.vercel.app (Contracts, Litigation, RERA walkthroughs for all states, Consulting). This document consolidates everything discussed in this session and proposes a single next step. Note (2026-09-11): the Oracle migration mentioned below was later abandoned for capacity reasons and the backend instead cut over to a GCP Compute Engine VM on 2026-09-05/06 — see `docs/40_Operations/Deployment.md` for the authoritative, current hosting facts.

---

## 1. Why this document exists

Three separate threads came up in this session and they need to be built as one coherent plan, not three parallel efforts:

1. Turning VidhiDesk from single-user into **multi-tenant** (individual lawyers + law firms as customers), with a **master dashboard for the platform owner** to track onboarding.
2. Restructuring the **litigation workflow** (Pleading, Filing, Hearing, Order, Evidence, Witness) from a chat-driven flow into connected, first-class objects.
3. Integrating the **eCourtsIndia API** to automate the highest-pain moment in a litigation lawyer's week: finding out the court room/bench allocation and being ready to argue with almost no notice.

All three share one dependency: **every new table needs `organization_id` from day one.** If the tenant model is retrofitted after the litigation objects are built, it's a much more expensive and riskier migration than building it in from the start.

---

## 2. Multi-Tenancy & Master Dashboard

### 2.1 What "multi-user" actually means here
Two distinct things were bundled together and need to stay distinct:

- **Firm-internal multi-user** — a firm's partners/associates sharing matters (this is Phase 4 of the existing product blueprint).
- **Platform-owner dashboard** — a view for you, across *all* customers (individual lawyers and firms), to track who has onboarded, plan/status, and usage. This does not exist in the current blueprint; it is genuinely new scope.

### 2.2 Data model
- New `organizations` table (one row per customer — could be a solo lawyer or a firm).
- New `memberships` table (`user_id`, `org_id`, `role`).
- Add `organization_id` to every existing owner-scoped table: `matters`, `contracts`, `draft_versions`, `documents`, `hearings`/calendar, consulting sessions.
- Rewrite RLS policies from "owner reads own row" to "member of org reads org's rows."
- Migration: wrap Nitesh's existing live data into "Organization #1" so nothing is lost.

### 2.3 Roles (start minimal)
- `org_admin` — manages the firm's members, sees all firm matters.
- `member` — individual lawyer/associate.
- Defer partner/associate/junior granularity until usage patterns are known.

### 2.4 Master Dashboard (platform owner view — the new ask)
Purpose: know at a glance how many individuals and firms have onboarded, and their status.

**Core views:**
- **Organizations list** — name, type (individual / firm), plan/status (trial / active / suspended), signup date, seat count, last activity date.
- **Onboarding funnel** — signed up → first matter created → first draft generated → active user (helps distinguish "onboarded" from "registered but unused").
- **Individual vs. Firm split** — simple counts/trend, since these are different customer segments with different sales motions.
- **Per-org drill-down** — members list, matters count, modules used (Contracts/Litigation/RERA/Consulting), last login.
- **Manual controls** — set plan/status, suspend/activate an org, adjust seat count.

**Explicitly out of scope for v1:**
- Automated billing/payment collection (Stripe/Razorpay subscription lifecycle) — set plan/status manually until there are enough paying customers for automation to pay for itself.
- Usage-based seat-limit enforcement.
- Revenue analytics/invoicing (this is Phase 5, "Practice Management," in the existing blueprint — unrelated to the tracking dashboard itself).

### 2.5 Also out of scope (deferred from the broader blueprint)
- Conflict checking across clients
- Firm knowledge base / template marketplace
- Client portal
- Time tracking, billing, collections
- SSO/SAML

---

## 3. Litigation Workflow — Object Model

### 3.1 Correcting the mental model
Pleading → Hearing → Order → Evidence → Witness → Filing is **not a pipeline** — it's a graph around the Matter. An Order can trigger a *new* Pleading (e.g., "file reply in 4 weeks"), and Filing is really the lifecycle state of a Pleading, not a peer object.

```
                              MATTER
                                │
        ┌──────────┬───────────┼────────────┬───────────┐
        │          │           │            │           │
     PLEADING   EVIDENCE    WITNESS      HEARING       (loops back)
        │          │           │            │
        │◄─────────┘           │            │
        │   (annexed to)       │            │
        │◄─────────────────────┘            │
        │   (examined re: pleading)         │
        ├──── FILING (event log) ───────────┤
        │     (draft→review→file→           │
        │      acknowledgement→defects)      │
        │                                    ▼
        │                               produces
        │                                    ▼
        │                                 ORDER
        │            directions extracted ──┤
        │◄──── triggers next pleading ───────┤
        │                          triggers next HEARING
        └────────────────────────────────────┘
```

### 3.2 The six objects
| Object | Key fields | Relationships |
|---|---|---|
| **Pleading** | matter_id, type, facts/issues/grounds, versions, lifecycle stage | annexes Evidence; has many Filings |
| **Filing** (child of Pleading, not a peer) | pleading_id, court, filing_date, filing_no, diary_no, case_no, status, defects[], refiling_deadline | logs every filing attempt (defects → refiling) |
| **Hearing** (exists today — calendar) | matter_id, prep checklist, linked pleadings due, order_id (nullable) | produces 0–1 Order; links Witnesses examined that day |
| **Order** (currently just an upload — needs structuring) | hearing_id (nullable), matter_id, order_date, court, raw text/upload, AI-extracted directions[]/deadlines[], status | triggers next Pleading + Task (lawyer-confirmed, never automatic) |
| **Evidence** | matter_id, source, date, related fact/issue, exhibit number, status | many-to-many with Pleading (annexures) and Witness (testimony) |
| **Witness** | matter_id, role, statement/notes, examination prep | many-to-many with Evidence and Hearing |

### 3.3 Build order within this cluster
1. Pleading as a structured object (everything else attaches to it)
2. Filing as an event log under Pleading (small, high daily value)
3. Order as a structured entity linked to Hearing (powers the "order → action" loop — the most differentiating item)
4. Evidence and Witness (lower daily urgency; build once Pleading/Order are solid)

### 3.4 Explicitly deferred within this cluster
- AI-suggested cross-examination questions / inconsistency detection on Witness
- Automatic (non-confirmed) task/deadline creation from Order directions — must always be a suggestion, per the "human control" design principle
- Court-specific exhibit-numbering conventions — start with free text

---

## 4. eCourtsIndia API Integration

### 4.1 What it provides
Third-party (non-government) API over official eCourts data. Bearer-token REST API. Relevant endpoints: case detail/search by CNR, order downloads (certified PDF + AI-extracted markdown), cause-list search, case refresh (single + bulk up to 50 CNRs/call), live enums. Metered/paid (₹200 free credits to start) — treat like the existing Indian Kanoon quota: cache aggressively, verify rather than trust blindly.

### 4.2 Where it plugs in
- New field: `matters.cnr_number` (nullable — optional, attached once a matter is filed and a CNR exists).
- New service: a "Court Data Gateway" (parallel to the existing LLM Gateway pattern), separate from the Indian Kanoon citation-verifier integration.
- New table: `court_case_cache` (matter_id, cnr_number, last_synced_at, raw_response_json, case_status, next_hearing_date, orders_json, sync_status) — same verify-and-cache pattern already used for citations.
- Writes into the **Hearing** and **Order** objects from Section 3, tagged `source = 'ecourtsindia'` vs `source = 'manual_upload'`.

### 4.3 Feature 1 (priority build): Automated Court-Room/Bench Alert + Pre-Drafted Argument Brief

**Problem it solves:** courts allocate room/bench the evening before a hearing, giving lawyers very little prep time.

**Trigger pipeline:**
```
Evening polling window (e.g. 3pm–11pm, hourly), per matter with a CNR
        ↓
Bulk case-refresh (up to 50 CNRs/call) → next_hearing_date == tomorrow?
        ↓ yes
Cause-list search for that court/date → match STRICTLY by CNR (never by name alone)
        ↓
Extract court_room, bench/judge, item_no
        ↓
Create/update Hearing record → status "listed"
```

**Brief-generation pipeline:**
```
Hearing Listed
        ↓
Assemble Matter Bundle: all Pleadings (latest versions), prior Orders
   (esp. last order's directions), linked Evidence, saved/verified
   Research & citations, Timeline, prior Argument Notes
        ↓
AI drafts Hearing/Argument Brief — grounded ONLY in this matter's own bundle
        ↓
Notify lawyer (in-app + email): "Matter X listed tomorrow, Room 4,
   Bench Y — brief ready for review"
        ↓
Lawyer reviews/edits before the hearing — never auto-used
```

**New object required:** extend Hearing with `court_room`, `bench`, `item_no` (from cause list), `argument_notes` (what was actually argued, what the judge asked, opposing counsel's position, next steps), and `brief_id → HEARING_BRIEF`. Argument notes from each hearing feed the *next* hearing's brief — this is what makes the feature compound in value over a matter's life instead of being a one-off summary.

**Brief content, explicitly separated:**
- Grounded in your filings (pleading position, citations already verified for this matter, last order's pending directions, what was raised last hearing)
- AI-suggested talking points (clearly labeled as such, never blurred with the above)

**Scope for v1**
- In: CNR-based evening polling, Hearing auto-update with room/bench, matter-bundle assembly, grounded AI brief, in-app + email notification, mandatory lawyer review.
- Out: judge-pattern analytics (ethically sensitive, defer until brief pipeline is trusted); auto-pulling opposing party's filings not already in VidhiDesk; WhatsApp/SMS push (start with in-app + email); multi-lawyer courtroom conflict detection across a firm.

### 4.4 Sequencing note
This feature needs Order and Hearing to already exist as structured objects (Section 3) — it is the automated data source for them, not a replacement for building them. Build Section 3 first, then wire this in.

---

## 5. Consolidated Priority Order

```
1. Tenant foundation
   organizations + memberships + organization_id on all tables + RLS rewrite
   (do this on a stable, fully-verified Oracle environment — not mid-migration)
        ↓
2. Master Dashboard (platform owner)
   org list, onboarding funnel, individual vs. firm split, manual plan/status controls
        ↓
3. Litigation object model
   Pleading (structured) → Filing (event log) → Order (structured, linked to Hearing)
   → Evidence & Witness
        ↓
4. eCourts integration
   CNR field + Court Data Gateway + court_case_cache
        ↓
5. Feature 1: Automated room/bench alert + pre-drafted argument brief
   (depends on 3 and 4 both being in place)
```

Firm-internal collaboration features (invite members, shared matters, task delegation), the "My Day" dashboard, and the Universal Task Engine can proceed in parallel with steps 3–4, since they depend only on step 1.

---

## 6. Recommended Single Next Step

**Build the tenant foundation (Section 2.2) first, and nothing else, before starting any of the litigation or eCourts work.**

Reasoning:
- It is the one piece every other item in this document depends on — retrofitting `organization_id` and RLS after new litigation tables (Pleading, Filing, Order, Evidence, Witness) already exist is materially more expensive and risky than building on top of it from day one.
- It directly unblocks the Master Dashboard, which is the most immediately useful thing for you as the business owner right now — you cannot track onboarding of individuals vs. firms until organizations exist as a concept in the database.
- It should be done as an isolated, heavily-tested phase, separate from finishing the Oracle/Render cutover — don't run both migrations concurrently.

**Concrete first sprint:**
1. Create `organizations` and `memberships` tables.
2. Add `organization_id` to existing tables; migrate current live data into "Organization #1."
3. Rewrite RLS policies to be org-scoped.
4. Ship a minimal Master Dashboard: organizations list with plan/status/seat count/signup date, and manual status toggles.
5. Only after this is verified in production — begin Section 3 (litigation objects).
