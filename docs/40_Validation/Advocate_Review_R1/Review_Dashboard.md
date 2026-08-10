> **Title:** Review Dashboard — Review Milestone R1
> **Version:** 1.0
> **Status:** Active — system metrics below are real and measured (9 August 2026); legal-quality columns are blank pending Nitesh's review and must be filled in from the completed `Clause_Review_Questionnaire.md`
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav
> **Last Updated:** 9 August 2026
> **Related Documents:** [`README.md`](README.md), [`Clause_Review_Questionnaire.md`](Clause_Review_Questionnaire.md), [`../Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md`](../Sprint_3.6_Phase2_Clause_Engine_Report_2026-08-09.md)

---

# Review Dashboard — Review Milestone R1

## Legend

- 🟢 **System metric** — a real, measured number from the Sprint 3.6 Phase 2 live evaluation (see the Phase 2 report). Not an estimate.
- ⚪ **Pending advocate review** — this column can only be filled in after Nitesh completes `Clause_Review_Questionnaire.md`. Do not treat a blank cell here as a zero or a pass.

---

## 1. Matter-by-matter status

| Matter | Clauses generated | Clauses approved (engineering pre-check) 🟢 | Composed draft complete? 🟢 | Avg AI confidence, composed clauses 🟢 | Legal quality score (1-5) ⚪ | Would-file rate ⚪ | Overall readiness ⚪ |
|---|---:|---:|:---:|---:|:---:|:---:|:---:|
| APP-01 | 14/14 | 14/14 | ✅ Yes | 0.95 | | | |
| CIV-01 | 14/14 | 14/14 | ✅ Yes | 0.94 | | | |
| COM-01 | 14/14 | 13/14 | ❌ No — Legal Grounds missing | 0.90 | | | |
| IA-01 | 14/14 | 14/14 | ✅ Yes | 0.92 | | | |
| PROP-03 | 14/14 | 13/14 | ❌ No — Legal Grounds missing | 0.76 | | | |
| RERA-01 | 14/14 | 14/14 | ✅ Yes | 0.88 | | | |
| **Average / Total** | **84/84** | **82/84 (98%)** | **4/6 (67%)** | **0.89** | | | |

**"Clauses approved (engineering pre-check)"** reflects the Sprint 3.6 Phase 2 evaluation's own auto-approval of every clause that generated without a warning (a scripted stand-in for review, done to exercise the composer — see the Phase 2 report §5) — **it is not advocate sign-off**, and every clause listed as "approved" here is still fully open for Nitesh to reject, request a rewrite of, or flag as unfit to file in this review round. The three columns marked ⚪ are the actual point of this milestone.

## 2. Grounding — what's missing, matter by matter

| Matter | Missing legal arguments (from composed draft) 🟢 | Missing/ungrounded statutes 🟢 | Missing precedents 🟢 |
|---|---|---|---|
| APP-01 | None — all 14 clauses composed | None flagged ungrounded | No verified precedent was available to cite (outline had none) |
| CIV-01 | None — all 14 clauses composed | None flagged ungrounded | No verified precedent was available to cite (outline had none) |
| COM-01 | **Legal Grounds clause entirely absent** — the clause connecting statutes to the pleaded facts was never successfully generated (see TICKET-25) | None flagged ungrounded (the clauses that DID generate cited nothing that failed verification) | No verified precedent was available to cite (outline had none) |
| IA-01 | None — all 14 clauses composed | None in the composed draft; **a regenerated-but-not-yet-approved Facts clause (v2) additionally cited CPC Section 151 and Order XXXIX Rules 1 & 2 — the correct injunction provisions for this matter — that the outline's own statute retrieval never surfaced**, flagging them "not grounded" purely because the earlier retrieval step missed them (see Phase 1's TICKET-16, still open) | No verified precedent was available to cite (outline had none) |
| PROP-03 | **Legal Grounds clause entirely absent** (same TICKET-25 failure as COM-01) | **Reliefs clause cites Specific Relief Act, 1963, Section 10 — the correct provision for specific performance — but it's flagged "NOT grounded"** because the outline's retrieval never surfaced it either (same underlying TICKET-16 gap, a second live instance) | No verified precedent was available to cite (outline had none) |
| RERA-01 | None — all 14 clauses composed | None flagged ungrounded | No verified precedent was available to cite (outline had none) |

**The pattern worth Nitesh's attention specifically:** in both real ungrounded-citation instances found this round (IA-01, PROP-03), the AI cited what is very likely the *legally correct* provision, and the system correctly declined to present it as confirmed — because grounding is checked against what the earlier retrieval step actually found, not against what's legally true. This is the system behaving exactly as designed (never silently trust an unverified claim), but it also means a real, correct citation and a genuinely fabricated one currently look identical to an advocate reading "NOT grounded" — worth Nitesh's explicit judgment on whether that distinction needs to be surfaced differently in a future UI.

**All 6 matters had zero verified precedents available to any clause.** This is a carried-forward, not new, finding (Phase 1 Foundation Report §9 point 3) — every AI-drafted clause in every matter correctly cited no case law, because none was available to cite, not because the system chose not to. This round produced no evidence either way about whether the clause engine cites precedent well when precedent *is* available — flag any matter where Nitesh independently knows a real, relevant precedent exists that the system never surfaced anywhere upstream (AI Case Analysis or Pleading Outline), since that's a retrieval-layer finding, not a clause-engine one.

## 3. System-side quality signals (for context only — not a substitute for legal review)

| Signal | Value | Source |
|---|---:|---|
| Clause generation reliability | 84/84 attempted, 82/84 (98%) succeeded without a warning | Phase 2 report §5 |
| Legal Grounds reliability specifically | 4/6 (67%) succeeded | Phase 2 report §5/§6 — the system's own weakest clause type |
| Statute citations that were checkable and passed | 5/6 (83%) in the original evaluation round's LLM clauses; both new instances found while building this dashboard (IA-01, PROP-03) are plausibly correct-but-unretrieved, not fabricated | Phase 2 report §6, this dashboard §2 |
| Case-law citations available to cite | 0 across all 6 matters | Phase 2 report §6, Phase 1 Foundation Report §9 |
| Model degradation | 100% of LLM clause calls served by a weaker model than the architecture's top tier (`gemini-2.5-pro` served none) | Phase 2 report §7 |

---

## 4. Overall Readiness — to be completed by Nitesh after the full review

| Question | Answer |
|---|---|
| Of the 6 matters reviewed, how many drafts would you use as a starting point for real drafting? | |
| Of those, how many would need only light editing vs. substantial rewriting? | |
| Is there any single clause type you would trust the system to draft unsupervised, based on this round? | |
| Is there any single clause type you would NOT want the system attempting again without a fix first? | |
| Given this round's evidence, do you agree with the engineering recommendation ("CLAUSE ENGINE REQUIRES FURTHER WORK," Phase 2 report §9)? | |
| **Overall readiness verdict** | ☐ Ready for supervised pilot use on real (non-test) matters ☐ Ready with named exceptions ☐ Not ready — needs the fixes identified in this round first |
| **Reasoning (required)** | |
