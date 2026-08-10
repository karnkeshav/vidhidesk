> **Title:** Feedback Capture Template — Review Milestone R1
> **Version:** 1.0
> **Status:** Active — living log for this review round
> **Owner:** Keshav (template author) / Nitesh (fills in as reviewer)
> **Audience:** Nitesh, Keshav, whoever scopes Sprint 3.6 Phase 2A
> **Last Updated:** 9 August 2026
> **Related Documents:** [`README.md`](README.md), [`Clause_Review_Questionnaire.md`](Clause_Review_Questionnaire.md), [`Engineering_Backlog_Mapping.md`](Engineering_Backlog_Mapping.md), [`../../30_Implementation/Backlog.md`](../../30_Implementation/Backlog.md)

---

# Feedback Capture Template

Every distinct comment from the Clause Review Questionnaire that is more than a single table cell gets **one row here**, not buried in the questionnaire's Comment column. This is the format that turns directly into a `Backlog.md` ticket — the columns below are exactly the fields `Engineering_Backlog_Mapping.md` needs to file one.

**One row per distinct issue, not per matter.** If the same problem shows up in more than one matter (e.g. "Legal Grounds is too generic" appears in APP-01, COM-01, and RERA-01), log it **once** and list every matter it was seen in — this is the same convention `Defect_Log.md` and `Backlog.md` already use for cross-scenario defects, and it keeps the count of *distinct* issues honest rather than inflated by repetition.

---

## Required fields (every row must have all of these)

| Field | What goes here |
|---|---|
| **Feedback ID** | `R1-01`, `R1-02`, ... sequential, never reused |
| **Matter(s)** | Which of the 6 matter labels (APP-01/CIV-01/COM-01/IA-01/PROP-03/RERA-01) this was observed in — list all that apply |
| **Clause** | One of the 14 clause types (or "Overall pleading" for a cross-clause finding, or "AI Case Analysis" / "Pleading Outline" for an upstream-artifact finding not tied to a specific clause) |
| **Version** | The `vN` shown in the review package for the clause version you are commenting on (matters if the clause was later regenerated — see the questionnaire's per-clause table) |
| **Reviewer** | Name of whoever filed this — for this round, Nitesh, but keep the field even if there's only one reviewer, since a future round may have more than one |
| **Date** | Date the comment was recorded |
| **Severity** | **Critical / Major / Minor / Enhancement** — see the scale below. This is Nitesh's *legal* severity judgment, not an engineering one; `Engineering_Backlog_Mapping.md` may re-classify when translating to a ticket, but must record both if they differ, never silently overwrite the advocate's rating |
| **Finding** | What's wrong (or, for a positive finding worth keeping, what worked well) — 1–3 sentences, specific enough that someone who hasn't read the clause could still understand the problem |
| **Suggested improvement** | What Nitesh would want changed, in his own words — does not need to be technically precise ("cite the actual RERA section" is a fine suggested improvement; `Engineering_Backlog_Mapping.md` translates it into an engineering task) |

## Severity scale (Critical / Major / Minor / Enhancement)

This round uses the same four-tier scale as `Backlog.md` (not the Critical/High/Medium/Low scale `Product_Validation_Report_Template.md` uses for a different kind of round) — `Defect_Log.md` flagged this exact inconsistency as unresolved housekeeping; this round picks one scale and uses it consistently, per that note.

- **Critical** — a clause states something as legally true that is actually false, fabricates a fact/statute/citation not present anywhere upstream, or would expose the client/advocate to real risk if filed as-is. Any Critical finding should also be checked against the Product Constitution's Legal Safety Principles and the zero-tolerance fabrication rule the certification rounds have used since Sprint 3.5.6.
- **Major** — a real, legally material gap or error (a missing argument a competent advocate would include, a wrong-but-not-fabricated citation, a clause an advocate would always rewrite rather than lightly edit) that doesn't rise to "would mislead if filed unreviewed," because ordinary professional review would likely catch it.
- **Minor** — a real gap in completeness, phrasing, or register that a careful advocate would catch on review and costs review time, but carries no correctness risk.
- **Enhancement** — not a defect at all; a "this would be nice" or "this would save more time if..." observation.

---

## Feedback Log

*(Nitesh: add one row per distinct finding as you work through the questionnaire. Do not skip the ID sequence, even if you later decide a finding isn't worth pursuing — record it as Enhancement or note "no action" rather than deleting the row, so the log stays a complete record of what was actually reviewed.)*

| Feedback ID | Matter(s) | Clause | Version | Reviewer | Date | Severity | Finding | Suggested improvement |
|---|---|---|---|---|---|---|---|---|
| R1-01 | | | | | | | | |
| R1-02 | | | | | | | | |
| R1-03 | | | | | | | | |

*(add rows as needed — copy the table row format above)*

---

## Worked examples (already-known engineering findings, shown here only as a shape reference — do not re-file these, they are already in `Backlog.md`)

These are not advocate feedback — they were found during engineering evaluation (Sprint 3.6 Phase 2) — but they show the target shape and are useful context while reviewing, since Nitesh may independently notice the same issues:

| Feedback ID | Matter(s) | Clause | Version | Reviewer | Date | Severity | Finding | Suggested improvement |
|---|---|---|---|---|---|---|---|---|
| *(ref. TICKET-24)* | CIV-01 and others (see review packages §9) | Facts | v1 | Keshav (engineering) | 2026-08-09 | Major | A PII-masking placeholder (`PARTY_I1`) appears instead of a real exhibit number in the filed Facts clause text | Exclude exhibit-number strings from PII auto-detection, or tighten the NER filter to not flag short alphanumeric-hyphen tokens |
| *(ref. TICKET-25)* | COM-01, PROP-03 | Legal Grounds | v1 | Keshav (engineering) | 2026-08-09 | Major | Legal Grounds failed to generate valid output in 2 of 6 matters — missing from the composed draft entirely | Investigate prompt length/complexity for this clause type specifically; consider a stronger-model routing preference |

---

## From feedback row to Backlog ticket

Once the Feedback Log above is complete, `Engineering_Backlog_Mapping.md` §3 walks through converting each row into a numbered `TICKET-NN` entry in `Backlog.md`, in the same voice/format every existing ticket uses (Classification, Description, Source, Status). A feedback row is **not** itself a ticket — it is the raw material Keshav (or whoever picks up Sprint 3.6 Phase 2A) triages from, exactly the same relationship `Defect_Log.md`'s findings already have to `Backlog.md`'s tickets.
