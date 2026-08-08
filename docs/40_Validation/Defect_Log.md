> **Title:** Defect Log — Sprint 3.5.5
> **Version:** 1.0
> **Status:** Active
> **Owner:** Keshav
> **Audience:** Nitesh, Keshav
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes, for defects found in this round
> **Related Documents:** [`README.md`](README.md), [`../30_Implementation/Backlog.md`](../30_Implementation/Backlog.md)

---

# Defect Log — 6 August 2026

Classification scheme for this round: **Critical / Major / Minor / Enhancement**, per this sprint's explicit instructions. Note this differs from `Product_Validation_Report_Template.md`'s own default scheme (Critical/High/Medium/Low) — both are recorded here as a housekeeping note, not a defect in either document; a future round should pick one scheme and use it consistently.

**Per this sprint's rules, no defect below was fixed.** Backlog entries are created only for reproducible *product* defects not already tracked; TICKET-7 and TICKET-8 already exist and were explicitly excluded from modification this sprint, so they are referenced, not re-filed.

## D-1: COM-04's documented expected forum result is stale

**Classification:** Minor — Test Documentation (not a product defect)

**Description:** `Sprint_3.5.3_Acceptance_Testing_Guide.md`'s COM-04 scenario states the expected recommended forum is "District Court/Additional District Judge, Delhi." Running the live code against COM-04's exact documented inputs (Commercial Dispute, ₹1,20,00,000, Delhi) returns "Designated Commercial Court, Delhi" instead — because COM-04 is, like COM-01/COM-02/COM-03/IA-03, a Commercial Dispute above the ₹3,00,000 Commercial Courts Act threshold, and the TICKET-6 fix correctly applies to it too. COM-04 was tagged in the guide's coverage matrix as an AI-synthesis stress scenario, not a forum-ordering one, and was overlooked when the guide's other forum-ordering scenarios were updated after the TICKET-6 fix.

**Reproduction:** `determine_forum(suit_type="Commercial Dispute", claim_value_inr=12000000, jurisdiction_state="Delhi")` → `recommended_forum.forum_name == "Designated Commercial Court / Commercial Division, Delhi"`, confirmed this round.

**Impact:** Low. The system's behavior is correct; a future tester following the guide's current text would flag a false "failure" that isn't one, wasting review time and potentially causing confusion about whether TICKET-6 actually holds.

**Recommendation:** Correct COM-04's "Expected Forum Result" text in the guide (not done this round, per the "do not fix defects during validation" rule) to state the Commercial Court is now the correct recommendation, consistent with COM-01/02/03/IA-03.

**Backlog entry:** Not filed in `Backlog.md` — this is an acceptance-testing document accuracy issue, not an application defect, and is fully described here.

## D-2: TICKET-7 (UP/Bihar forum state-coverage gap) — re-confirmed, unchanged

**Classification:** Major (per its original Backlog classification carried forward — this round did not re-derive severity, only re-confirmed presence)

**Description:** Already tracked in `Backlog.md`. Re-confirmed this round via live execution in four scenarios: PROP-01 (UP, Possession), PROP-04 (Bihar, Declaratory), RERA-02 (UP, RERA — the general-civil fallback specifically, not the RERA branch which is state-name-correct), IA-02 (Bihar, Appeal). In every case, the Forum Advisor silently returned the generic `DEFAULT` pecuniary band with no distinguishing indicator, exactly as previously documented.

**Status:** Open. Explicitly out of scope to modify this sprint per this task's instructions. No new backlog entry filed — this re-confirms TICKET-7, it does not add a new defect.

## D-3: TICKET-8 (AI Case Analysis blind to hearing/IA data) — not independently re-testable this round

**Classification:** Major (per its original Backlog classification carried forward)

**Description:** Already tracked in `Backlog.md`, based on a code-trace finding during the acceptance guide's authoring (`_facts_narrative()` never reads `litigation_hearings`). This round could not execute the AI Case Analysis pipeline at all, so this finding could not be behaviorally re-confirmed or refuted — it remains logged as open on the strength of the prior code trace, not newly validated.

**Status:** Open, unchanged, out of scope to modify this sprint. No new backlog entry filed.

## Environment blocker (not a product defect — logged separately, does not fit the Critical/Major/Minor/Enhancement scale)

**Description:** This execution environment has no `api/.env` (no `GEMINI_API_KEY`, `GROQ_API_KEY`, `SAMBANOVA_API_KEY`, `CEREBRAS_API_KEY`, `SUPABASE_SERVICE_KEY`, or `INDIAN_KANOON_API_TOKEN`), and no way to establish a real authenticated user session. This blocked execution of: AI Case Analysis generation for all 26 scenarios, evidence file upload, citation verification, and the full browser-based workflow requested (Matter → ... → Structured Review).

**Impact:** This is the dominant limiting factor on this round's completeness — see `Validation_Summary.md` and `Go_No_Go_Decision.md`. It is not a defect in VidhiDesk; it is a gap in what this particular execution session can reach. The same 26 scenarios, run by Nitesh against a live deployment with real credentials, would close this gap directly.

**Recommendation:** See `Recommendations.md` — either provision this environment with real (ideally free-tier, low-quota-risk) credentials for a follow-up automated pass, or have Nitesh execute the guide manually against the live deployed app, using `Product_Validation_Report_Template.md` per scenario.

## Summary

| ID | Classification | Status | New this round? |
|---|---|---|---|
| D-1 | Minor (test documentation) | Open, not fixed | Yes — found this round |
| D-2 (TICKET-7) | Major | Open, unchanged | No — re-confirmed |
| D-3 (TICKET-8) | Major | Open, unchanged | No — not re-testable this round |
| Environment blocker | N/A (process, not product) | Open | Yes — first time formally logged as its own item, though the underlying gap was already noted in `Build_Tracker.md` E28 |

**Zero new product defects found this round.** No Critical or Enhancement-classified items this round.
