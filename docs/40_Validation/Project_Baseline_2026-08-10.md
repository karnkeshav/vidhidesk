> **Title:** Project Baseline & Release Readiness — 10 August 2026
> **Version:** 1.0
> **Status:** Active — Canonical for current project state as of this date; supersedes the milestone-status claims in `Advocate_Review_R1/README.md`'s own "Recommendation for Sprint 3.6 Phase 2A" section, which was written before Phase 2A shipped
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav, whoever plans the next engineering sprint
> **Last Updated:** 10 August 2026
> **Canonical Reference:** Yes, for release-readiness status specifically — `Build_Tracker.md` remains canonical for detailed build history
> **Related Documents:** [`../30_Implementation/Build_Tracker.md`](../30_Implementation/Build_Tracker.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md), [`../40_Operations/Release_Gates.md`](../40_Operations/Release_Gates.md), [`README.md`](README.md), [`Advocate_Review_R1/README.md`](Advocate_Review_R1/README.md)

---

# Project Baseline — 10 August 2026

Produced by the Project Re-Baselining Sprint. This is a documentation/project-management deliverable only — no application code, infrastructure, or database schema was touched producing it.

## 1. Project Status

Reviewed against `Build_Tracker.md`, `Backlog.md`, `Release_Gates.md`, and `docs/40_Validation/README.md` directly (not from memory).

### Completed milestones
- **Documentation Restructure** — numbered hierarchy + precedence policy (`632418e`)
- **Advocate Profile Simplification** (`ffb0040`)
- **Sprint 3.6 Phase 1** — AI Pleading Generation foundation: Pleading Outline, corpus expansion (6→12 acts), Citation Verifier non-determinism fix, model-routing transparency
- **Sprint 3.6 Phase 2** — Clause-Based Drafting Engine: 14 clause generators, reasoning-free document composer, live-evaluated against 6 real matters
- **Sprint 3.6 Phase 2A** — Legal Grounds Intelligence: TICKET-25 root-caused and substantially resolved (33%→0% malformed rate), gateway-level JSON-mode + repair hardening
- **Repository Stabilization** — all of the above committed and pushed in a clean 4-commit history (`632418e`…`56ec3ac`)
- **Authentication Investigation + Logging Enhancement + Release Integration** — real production incident traced to Render deploy timing + a stale session (not a code defect); diagnostic logging gap closed (`61e695e`, `02fec96`)

(Phases 1/2/2A/Authentication are all confirmed on `origin/main` as of this document — see §5.)

### Active milestone
**Advocate Review R1.** The complete package (6 matter reviews, 84-row clause questionnaire, feedback capture template, dashboard, backlog-mapping framework) is built and pushed. **Nothing in it has been filled in yet** — every legal-quality field is still blank. This is the actual current bottleneck: nothing downstream can start until Nitesh works through it.

### Remaining milestones
Engineering Improvements (from R1 feedback) → Pleading Pipeline Re-Validation → Beta Readiness Review → Beta Release. None have started. Detail in §4.

### A documentation gap worth naming here, not hidden
`docs/40_Validation/README.md`'s own round-by-round index currently stops at Sprint 3.6 Phase 1 — it does not yet mention Phase 2, Phase 2A, the Repository Stabilization commits, Advocate Review R1, or the Authentication work. This document does not fix that (out of this sprint's "review, don't rewrite other docs" scope) — flagging it as a real, small gap for whoever next has reason to edit that file.

---

## 2. Backlog Review — Open Tickets Classified

Per this sprint's rule: no ticket created, no ticket closed. Closed tickets (`TICKET-5, 6, 9, 10, 14, 17, 21, 22`) are excluded below — they're already resolved and out of scope for this classification.

| Ticket | Summary | Severity | Classification |
|---|---|---|---|
| TICKET-7 | UP/Bihar missing from Forum Advisor's state table | Major (scope) | **Blocking Public Release** — CLAUDE.md Decision 2 names UP as in-scope for Phase 1; not needed for a supervised Beta pilot |
| TICKET-8 | AI Case Analysis blind to `litigation_hearings` data | Major (design gap) | **Blocking Beta** — litigation matters routinely have hearings; a time-sensitive gap an advocate would notice |
| TICKET-11 | `CEREBRAS_API_KEY` invalid (4th fallback tier, never reached in practice) | Minor | **Future Enhancement** |
| TICKET-12 | Migrations 0011/0013/0014 lack idempotency guard | Major (deploy safety) | **Blocking Beta** — deploy-safety risk grows with deploy frequency, which Beta increases |
| TICKET-13 | `evidence` Storage bucket is public, not signed-URL | Major (confidentiality posture) | **Blocking Beta** — real client evidence documents need this before any real (even supervised) matter data flows through |
| TICKET-15 | PII auto-detection over-masks some non-name tokens | Minor | **Future Enhancement** |
| TICKET-16 | Statute corpus recall 73%, not resolved | Major, ongoing | **Blocking Beta** — central to output quality for the whole pleading platform; does not block Advocate Review, which exists specifically to surface exactly this |
| TICKET-18 | Some real precedents fail to verify even on retry (genuine indexing gap) | Minor | **Future Enhancement** — safe-failure, under-serves rather than misleads |
| TICKET-19 | Model proposed one real-but-irrelevant precedent | Minor | **Future Enhancement** |
| TICKET-20 | `flash-lite` shows weaker reasoning; partially addressed, not closed generally | Major | **Blocking Beta** — ties directly to the free-tier capacity concern (TICKET-21's legacy) that affects reliability of what any real Beta user would see |
| TICKET-23 | No token-usage/cost capture in LLM Gateway | Enhancement | **Future Enhancement** |
| TICKET-24 | PII-mask placeholder leaked into final clause text | Major | **Blocking Beta** — a real, visible defect in drafted text; must not ship to any real client-facing use |
| TICKET-25 | `legal_grounds` malformed-JSON rate — substantially resolved, one follow-up pending (`gemini-2.5-flash-lite`-targeted re-confirmation, script already built) | Major → nearly closed | **Blocking Beta** — close the one remaining follow-up before relying on this in Beta; does not block Advocate Review |
| TICKET-26 | Most LLM clauses claim zero citations even when available (safe-by-construction coverage gap) | Minor | **Future Enhancement** |
| TICKET-27 | Clause regeneration doesn't guarantee the same model tier | Minor | **Future Enhancement** |

**None of the open tickets block Advocate Review.** R1's own review packages already disclose every one of TICKET-16/24/25/26/27 inline as "Known Limitations" — the review was deliberately designed to proceed with these named, not wait for them.

**Six tickets block Beta** (TICKET-8, 12, 13, 16, 20, 24) plus TICKET-25's one remaining follow-up. **One ticket blocks Public Release specifically, not Beta** (TICKET-7). **Eight tickets are Future Enhancements** with no release-blocking claim (TICKET-11, 15, 18, 19, 23, 26, 27, plus TICKET-25's already-substantially-resolved status once the flash-lite follow-up lands).

---

## 3. Release Readiness

| Stage | Status | Basis |
|---|---|---|
| Engineering | **COMPLETE** | Phases 1/2/2A + Authentication work all on `origin/main`, 279/279 tests passing |
| Production Validation | **ACTIVE** | Real production testing happened continuously (live evaluations embedded in Phase 1/2/2A, the Authentication Investigation's live browser/backend testing) but `Release_Gates.md`'s own Phase 2 (Litigation) gate — *"100 generated citations audited; target zero fabricated citations reaching the user"* — is nowhere close to met (current evidence is dozens of generations across 6 matters, not 100 audited citations). Not a dedicated, closed round the way Sprint 3.5.6's 26-scenario certification was for Case Analysis. |
| Advocate Review | **ACTIVE** | R1 package complete and pushed; zero fields filled in yet. This is the current milestone. |
| Engineering Improvements | **BLOCKED** | Blocked on Advocate Review producing real feedback — cannot meaningfully start (TICKET-28 onward is reserved, empty) |
| Beta Release | **NOT STARTED** | Gated behind all of the above plus `Release_Gates.md`'s standing gate: *"no output reaches a client or a court without advocate review and sign-off... permanent."* |

---

## 4. Recommended Roadmap From Today

1. **Advocate Review R1** (active now) — Nitesh works through `Advocate_Review_R1/Clause_Review_Questionnaire.md` and `Feedback_Capture_Template.md`. Splitting into 2–3 sessions (rather than all 6 matters at once) remains a reasonable suggestion, not a requirement.

2. **Engineering Improvements** — two real inputs, not one:
   - Whatever R1 actually surfaces (unknowable in detail until it happens, but by design it takes priority over everything below)
   - The six tickets already classified **Blocking Beta** above (TICKET-8, 12, 13, 16, 20, 24) plus TICKET-25's one remaining follow-up — these don't need to wait for R1 to be known, since they're already documented and evidenced

3. **Pleading Pipeline Re-Validation** — once (2) lands: re-run a Phase-2-style live evaluation against the same 6 (or more) certification matters to confirm the Beta-blocking fixes actually hold, plus make real progress against `Release_Gates.md`'s 100-audited-citation gate — this is the "Production Validation" stage's own remaining gap (§3), not a new phase invented for this roadmap.

4. **Beta Readiness Review** — a formal go/no-go against `Release_Gates.md`'s standing gate (advocate sign-off obtained) and Phase 2 gate (citation audit target), following this project's own established certification-round pattern (Sprint 3.5.6) rather than an ad hoc check.

5. **Beta Release** — supervised pilot use on real (non-test) matters, per `Advocate_Review_R1/Review_Dashboard.md` §4's own "Ready for supervised pilot use" framing.

No additional engineering phases introduced beyond this five-step sequence — every step above is justified by an existing document (`Release_Gates.md`'s gates, `Backlog.md`'s already-filed tickets, `Advocate_Review_R1`'s own dashboard language), not invented for this roadmap.

---

## 5. Cleanup Verification

- `git status`: clean except `supabase/` (local CLI cache, intentionally excluded per standing instruction)
- `origin/main` HEAD: `02fec964f3935bbc26b0c9a73da90542754bc279` — confirmed via `git fetch` + `git rev-parse`, matches local HEAD exactly, before this document's own commit
- Pending migrations: none — `0018_pleading_clauses.sql` is the latest file on disk, and a live schema query confirms it's applied in production (258 real `litigation_pleading_clauses` rows already exist from this project's own live-evaluation sessions)
- Pending pushes: none, prior to this sprint's own doc commit
- Partially completed milestones: none found — Advocate Review R1 being "unfilled" is a legitimate waiting-on-human state (the package itself is complete), not an unfinished engineering task
