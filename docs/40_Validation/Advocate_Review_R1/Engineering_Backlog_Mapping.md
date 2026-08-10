> **Title:** Engineering Backlog Mapping — Review Milestone R1
> **Version:** 1.0
> **Status:** Active — classification framework ready; no new tickets filed yet (this milestone does not fix or file anything, per its own rules — see `README.md`)
> **Owner:** Keshav
> **Audience:** Keshav (or whoever scopes Sprint 3.6 Phase 2A), Nitesh (for context on how his feedback will be used)
> **Last Updated:** 9 August 2026
> **Related Documents:** [`Feedback_Capture_Template.md`](Feedback_Capture_Template.md), [`../../30_Implementation/Backlog.md`](../../30_Implementation/Backlog.md)

---

# Engineering Backlog Mapping

**This document does not itself file any tickets.** It is the triage framework that turns a completed `Feedback_Capture_Template.md` into new `Backlog.md` entries once Nitesh's review round is done — per this milestone's explicit rule ("Do NOT fix backlog items... Prepare the backlog so that every advocate comment can be translated into an engineering task"), that translation step happens in Sprint 3.6 Phase 2A, not here.

---

## 1. Classification scheme (Critical / Major / Minor / Enhancement)

Same four-tier scale as `Feedback_Capture_Template.md` and `Backlog.md`, now with the **engineering** lens added on top of Nitesh's **legal** severity rating — the two are recorded separately, never collapsed into one, because a legally minor issue can be an engineering-major fix (or vice versa):

| Tier | Legal criterion (Nitesh's rating, from the Feedback Log) | Engineering translation |
|---|---|---|
| **Critical** | Fabricated or legally false content; would expose the client/advocate to real risk if filed unreviewed | Becomes a **Certification Blocker** — the next round's Defect Policy (like this sprint's) would not permit shipping past it without a fix. Escalate immediately, don't wait for the next full sprint. |
| **Major** | A real, legally material gap or error a competent advocate would always catch, but that ordinary review would also catch | Standard `Backlog.md` ticket, prioritized for the next clause-engine-focused sprint (candidate: Sprint 3.6 Phase 2A) |
| **Minor** | A completeness/phrasing/register gap, no correctness risk | Standard `Backlog.md` ticket, unprioritized — picked up opportunistically or bundled with related work |
| **Enhancement** | Not a defect — a "would be nice" | Logged for visibility; only actioned if it turns out to unblock something else |

**A Critical finding from Nitesh changes this milestone's own conclusion**, not just the backlog — if the review round surfaces a fabricated fact, statute, or citation presented as confirmed, treat this the same way `Product_Validation_Report_Template.md`'s zero-tolerance check does: it overrides every other metric in `Review_Dashboard.md`, and should be raised to Keshav immediately rather than sitting in the Feedback Log until the round formally ends.

## 2. Converting a Feedback Log row into a ticket

For each row in `Feedback_Capture_Template.md`'s Feedback Log with Severity Major or above (Minor/Enhancement rows may be batched rather than filed individually, at Keshav's discretion — same convention `Backlog.md` already uses, e.g. the bundled Contracts "review UX" notes), draft a new entry using this shape — copy the voice and structure every existing `Backlog.md` ticket uses:

```
**TICKET-NN: <one-line summary, stated as the defect, not the fix>.**
Classification: **<Critical|Major|Minor|Enhancement>**. <2-4 sentences:
what was observed, in which matter(s), reproduced how. Cite the exact
clause/version/matter from the Feedback Log row. If a root cause is
already suspected, name it — but don't guess if you don't have evidence
yet (the existing tickets are careful to distinguish "found and diagnosed"
from "found, cause unclear"). Cross-reference any related existing ticket
(§3 below) rather than re-describing the same root cause from scratch.>
*Source: Review Milestone R1 Advocate Review, Feedback ID R1-NN, matter
<label>, 9 August 2026 (or later, if filed in a follow-up triage
session) — found via structured advocate review of already-generated,
real outputs, not inferred from code reading.*
```

The next available ticket number is **TICKET-28** (TICKET-27 is the last filed, in Sprint 3.6 Phase 2's own evaluation).

## 3. Known issues by clause type (check before filing — avoid duplicates)

Nitesh's review may independently rediscover an issue engineering already knows about. Check this table before filing a new ticket — if a Feedback Log row matches an existing ticket's description, **do not re-file**; instead add the matter/version as a new confirmed instance on the existing ticket (same convention `Defect_Log.md` used for TICKET-7/TICKET-8 re-confirmations).

| Clause type | Known open issues |
|---|---|
| Cause Title | None known |
| Court Details | None known |
| Parties | None known |
| Jurisdiction | None known (deterministic; inherits any Forum Advisor gap — see TICKET-7, UP/Bihar state coverage) |
| **Facts** | **TICKET-24** (PII placeholder leak — `PARTY_I#` tokens appearing instead of real exhibit numbers, confirmed in CIV-01 this round) |
| Chronology | None known |
| Cause of Action | Inherits any statute-retrieval gap from the source Pleading Outline (TICKET-16) |
| **Legal Grounds** | **TICKET-25** (33% malformed-output rate, the system's least reliable clause — confirmed missing entirely from the composed draft in COM-01 and PROP-03 this round); **TICKET-26** (low citation-attempt rate even on successful runs) |
| Applicable Statutes | Inherits TICKET-16 (corpus/retrieval recall gap, 73% not 100%) — this clause can only ever be as complete as what was retrieved upstream |
| Applicable Precedents | Inherits Phase 1's open case-law-recall gap (Foundation Report §9 point 3) — confirmed empty in all 6 matters again this round |
| Reliefs | Two live instances this round of a plausibly-correct-but-unretrieved statute citation (PROP-03: Specific Relief Act §10) — same TICKET-16 root cause, not a Reliefs-specific defect |
| Prayer | None known |
| Verification | None known |
| List of Annexures | Inherits TICKET-24 if the underlying evidence_mapping/exhibit data carries a leaked placeholder |
| **Cross-clause / regeneration** | **TICKET-27** (regenerating a clause is not guaranteed to reuse the same model tier, so two regenerations of "the same" clause can differ materially — confirmed again in this round's IA-01 Facts v1→v2 diff, shown in that matter's review package) |
| **Retrieval (upstream of every clause)** | **TICKET-16** (statute corpus recall 73%, not 100% — root cause of both live ungrounded-but-plausible citations found in §2 of `Review_Dashboard.md` this round) |

## 4. What this milestone deliberately did NOT do

Per the milestone's rules, none of the following happened this round, even where the evidence above might tempt it:
- No prompt was changed (Legal Grounds' reliability gap, TICKET-25, is diagnosed but not touched)
- No corpus was expanded (TICKET-16 remains at 73% recall)
- No code was changed (TICKET-24's placeholder leak reproduces exactly as before)
- No new backlog ticket was actually filed — §2/§3 above are the *tool* for filing, not filings themselves

## 5. Recommended first pass at Sprint 3.6 Phase 2A scope, pending Nitesh's actual feedback

**Do not treat this as fixed scope** — it is Keshav's best guess at what Phase 2A will need to cover, based only on the engineering-side findings already known before Nitesh's review starts. Revise once the Feedback Log is populated; a Critical or high-volume Major finding from Nitesh should reorder this list, not just append to it.

1. Diagnose TICKET-25 (Legal Grounds reliability) — this is the single highest-leverage fix, since it's both the system's least reliable clause and, per `Review_Dashboard.md` §1, the reason 2 of 6 matters have an incomplete composed draft at all.
2. Decide a fix direction for TICKET-24 (PII placeholder leak) — low engineering cost (a masking-scope fix, not an architecture change), directly visible to Nitesh in this round's own review packages, and undermines trust in every other clause's polish if left unaddressed.
3. Whatever Nitesh's review adds — this is deliberately last in this provisional list, not because it matters least, but because it cannot be scoped until the review actually happens.
