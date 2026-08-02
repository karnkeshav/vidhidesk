#!/usr/bin/env python3
"""Seed the Employment Agreement template + its clause library (Sprint 2
Deliverable 2, Batch 4).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_employment_template.py

Idempotent: upserts the templates row by (name, category), and
template_clauses rows by (template_id, clause_key); prunes any orphaned
clause row via _prune_orphaned_clauses (same mechanism as every
template seeded before this one — see docs/lessons_learned.md).

Employment introduces this rollout's first genuine statutory-compliance
content (PF/ESI/Gratuity) and non-compete doctrine (Section 27, Indian
Contract Act, 1872), but no new technical mechanism — six domain
deviations from Consultancy's shape, all approved 2026-08-02:

  - No party_b_entity_type: an Employee is always a natural person.
  - Confidentiality is a single fixed clause, not the applicable_
    condition-per-variant pattern — Employment confidentiality only has
    one sensible real-world configuration (Employee owes Employer),
    unlike Consultancy/Service Agreement/MoU where mutual was a genuine
    possibility. The variant pattern is for when >1 configuration is
    actually sensible, not a checklist item to force onto every clause.
  - Intellectual Property is fixed_boilerplate, not llm_fillable —
    second clean application of the classification bar established from
    the MoU Governing Law finding (see feedback_llm_fillable_
    classification_bar memory / docs/sprint_3_backlog.md): Employment
    IP is near-universally "work product created during employment
    belongs to the Employer," no real alternative ownership model to
    weigh, unlike Consultancy's genuine 3-way choice.
  - Statutory Compliance (PF/ESI/Gratuity) is ONE conservative,
    non-computed fixed_boilerplate clause — deliberately NOT driven by
    a selectable "PF/ESI applicable?" field, because actual coverage
    depends on employee-count/wage thresholds this form has no way to
    verify per matter. A dropdown would risk asserting a legal
    conclusion the system can't back. States obligations apply "to the
    extent applicable," cites the correct Acts, asserts no specific
    rate/threshold/ceiling as fact — same conservative posture as
    state_rules' stamp-duty PENDING VERIFICATION notes.
  - No payment_frequency field — Indian salaries are near-universally
    monthly; hardcoded in the Compensation clause.
  - Restrictive Covenants (llm_fillable — this one genuinely needs
    narrative synthesis) has an explicit Section 27 (Indian Contract
    Act, 1872) caveat baked into its prompt: post-termination restraints
    on trade are void in India save narrow exceptions, so the clause
    must not draft an unenforceable non-compete as if it were binding,
    and must end with an [ADVOCATE REVIEW: ...] flag.

Governing Law and Jurisdiction is fixed_boilerplate from the start here
(third clean application of the bar) — a Jinja branch on `arbitration`
is all it needs; no template author cannot enumerate this in Jinja.

Only 3 of 12 logical clauses are llm_fillable: Recitals, Position/Duties
and Reporting (genuine narrative from duties_description), and
Restrictive Covenants (genuine legal-doctrine synthesis).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "employment.schema.json"
DOCX_PATH = "templates/contracts/employment.docx"

TEMPLATE_NAME = "Employment Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "employment"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Employment "
            "Agreement between {{ party_a_name }} (the Employer) and "
            "{{ party_b_name }} (the Employee). The Employee is being "
            "engaged as {{ designation }} in the {{ department }} "
            "department. Write 1-2 formal WHEREAS paragraphs establishing "
            "that the Employer wishes to employ the Employee, and the "
            "Employee wishes to accept such employment, on the terms set "
            "out in this Agreement. Refer to the parties by their actual "
            "names given above — never a generic placeholder like 'Party "
            "A' or 'Party B' — ending with 'NOW THEREFORE, in "
            "consideration of the mutual covenants contained herein, the "
            "Parties agree as follows:'. Do not invent facts beyond what "
            "is provided, and do not describe specific duties, "
            "compensation, or benefits here — those are covered by "
            "separate clauses below."
        ),
    },
    {
        "clause_key": "definitions",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Definitions",
        "source_text": (
            "(a) “Duties” means the duties and responsibilities of the "
            "Employee as set out in the Position, Duties and Reporting "
            "clause below.\n"
            "(b) “Confidential Information” has the meaning given in the "
            "Confidentiality clause below.\n"
            "(c) “Applicable Law” means the laws of India, including all "
            "statutes, rules, and regulations referred to in this "
            "Agreement, as amended from time to time."
        ),
    },
    {
        "clause_key": "position_duties_reporting",
        "display_order": 3,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Position, Duties and Reporting",
        "source_text": (
            "Draft the Position, Duties and Reporting clause for this "
            "Employment Agreement (do not include a numbered heading — "
            "the caller adds one). The Employee is engaged as "
            "{{ designation }} in the {{ department }} department"
            "{% if reporting_to %}, reporting to {{ reporting_to }}"
            "{% endif %}. Duties and responsibilities provided by the "
            "client: {{ duties_description }}. Write a clause stating the "
            "Employee's designation, department, and reporting line as "
            "given above, and describing the Employee's key duties and "
            "responsibilities drawing only on the information provided — "
            "do not invent specific duties beyond what is given. State "
            "that the Employer may reasonably modify the Employee's "
            "duties from time to time consistent with the Employee's "
            "designation and skill level, and that the Employee shall "
            "devote their full working time and attention to the "
            "performance of their duties"
            "{% if employment_type == 'Part-Time' %} on a part-time "
            "basis as agreed between the Parties{% endif %}."
        ),
    },
    # Probation as a real intake choice, two applicable_condition-gated
    # clause rows — the "expected instance" of the applicable_condition-
    # per-variant pattern named when that pattern was first documented
    # (see docs/lessons_learned.md).
    {
        "clause_key": "probation_with_period",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "has_probation", "equals": True},
        "heading": "Probation",
        "source_text": (
            "The Employee shall serve a probationary period of "
            "{{ probation_period }} from the Date of Joining ('Probation "
            "Period'), during which either Party may terminate this "
            "Agreement by giving {{ termination_notice_period }} written "
            "notice, or payment in lieu thereof at the Employer's "
            "discretion — provided that where a shorter notice period is "
            "customary for probationary employees under the Employer's "
            "policy, such shorter period may apply. Upon satisfactory "
            "completion of the Probation Period, as assessed by the "
            "Employer, the Employee's employment shall be confirmed by "
            "written notice, and the notice period set out in the "
            "Termination clause below shall thereafter apply."
        ),
    },
    {
        "clause_key": "no_probation",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "has_probation", "equals": False},
        "heading": "Probation",
        "source_text": (
            "The Employee's employment under this Agreement is confirmed "
            "with effect from the Date of Joining, without any "
            "probationary period."
        ),
    },
    {
        "clause_key": "compensation_and_benefits",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Compensation and Benefits",
        "source_text": (
            "The Employer shall pay the Employee an annual cost-to-"
            "company (CTC) of {{ annual_ctc }}, payable in monthly "
            "instalments in accordance with the Employer's standard "
            "payroll practice, subject to applicable statutory "
            "deductions.{% if other_benefits %} The Employee shall "
            "additionally be entitled to the following benefits: "
            "{{ other_benefits }}.{% endif %} The compensation and "
            "benefits set out in this clause are subject to periodic "
            "review by the Employer in accordance with its policies then "
            "in force."
        ),
    },
    {
        "clause_key": "statutory_compliance",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Statutory Compliance",
        # Approved verbatim 2026-08-02 — see the batch plan discussion:
        # deliberately not driven by a selectable applicability field;
        # states obligations apply "to the extent" covered, asserts no
        # rate/threshold/ceiling as fact.
        "source_text": (
            "The Employer shall, to the extent it is covered under the "
            "applicable provisions, make deductions and contributions in "
            "respect of the Employee under the Employees' Provident "
            "Funds and Miscellaneous Provisions Act, 1952, the "
            "Employees' State Insurance Act, 1948, and shall pay gratuity "
            "in accordance with the Payment of Gratuity Act, 1972, "
            "subject to the Employee meeting the eligibility criteria "
            "prescribed thereunder (including the minimum period of "
            "continuous service). Applicability of the foregoing to the "
            "Employer's establishment, and the precise rates, "
            "thresholds, and ceilings in force, shall be confirmed by "
            "the Employer's advisors and are not asserted as fact in "
            "this Agreement."
        ),
    },
    {
        "clause_key": "confidentiality",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Confidentiality",
        "source_text": (
            "The Employee acknowledges that in the course of employment "
            "the Employee will have access to confidential and "
            "proprietary information of the Employer (“Confidential "
            "Information”), including without limitation business plans, "
            "client and customer information, pricing, financial "
            "information, technical know-how, and trade secrets. The "
            "Employee agrees that the Employee shall: (a) hold such "
            "Confidential Information in strict confidence both during "
            "and after the term of employment; (b) use it solely for the "
            "performance of the Employee's duties under this Agreement; "
            "(c) not disclose it to any third party except as required "
            "in the ordinary course of the Employee's duties or as "
            "required by law; and (d) return or destroy all Confidential "
            "Information in the Employee's possession upon termination "
            "of employment. This clause survives termination of this "
            "Agreement."
        ),
    },
    {
        "clause_key": "intellectual_property",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Intellectual Property",
        "source_text": (
            "All inventions, works of authorship, designs, processes, "
            "know-how, and other intellectual property created, "
            "conceived, or developed by the Employee in the course of "
            "employment and relating to the business of the Employer "
            "(“Work Product”) shall belong exclusively to the Employer, "
            "and the Employee hereby assigns, and agrees to assign, all "
            "right, title, and interest in such Work Product to the "
            "Employer. The Employee shall, at the Employer's request and "
            "expense, execute all documents and take all actions "
            "reasonably necessary to perfect the Employer's ownership of "
            "the Work Product. Nothing in this clause extends to any "
            "intellectual property created by the Employee wholly "
            "outside the course of employment, using none of the "
            "Employer's resources, and unrelated to the Employer's "
            "business."
        ),
    },
    {
        "clause_key": "restrictive_covenants",
        "display_order": 9,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Restrictive Covenants",
        # Approved verbatim 2026-08-02.
        "source_text": (
            "Draft the Restrictive Covenants clause for this Employment "
            "Agreement (do not include a numbered heading — the caller "
            "adds one). Additional notes from the client, if any: "
            "{{ non_compete_notes }}. Note that under Indian law, a "
            "restraint on the Employee's ability to engage in a lawful "
            "profession, trade, or business after termination of "
            "employment is void under Section 27 of the Indian Contract "
            "Act, 1872, save for narrow, well-established exceptions "
            "(e.g. protection of trade secrets/confidential information, "
            "which the Confidentiality clause above already covers). Do "
            "not draft a post-termination non-compete restriction as if "
            "it were enforceable. You may draft reasonable "
            "non-solicitation of the Employer's employees and clients, "
            "and confidentiality-protective language, operative during "
            "employment and for a limited period after (not exceeding 12 "
            "months, unless a different period is indicated in the notes "
            "above), and must end the clause with the following "
            "bracketed note verbatim: '[ADVOCATE REVIEW: post-termination "
            "restraints on trade are void under Section 27, Indian "
            "Contract Act, 1872, save narrow exceptions — confirm this "
            "clause does not overreach before use.]'"
        ),
    },
    {
        "clause_key": "termination",
        "display_order": 10,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Termination",
        "source_text": (
            "Either Party may terminate the Employee's employment under "
            "this Agreement for convenience by giving the other Party "
            "{{ termination_notice_period }} written notice, or payment "
            "in lieu of notice at the Employer's discretion (subject to "
            "the shorter notice applicable during the Probation Period, "
            "if any, as set out above). The Employer may terminate this "
            "Agreement immediately, without notice or payment in lieu of "
            "notice, in the event of the Employee's proven misconduct, "
            "breach of this Agreement, or other cause recognised under "
            "applicable law."
            "{% if employment_type == 'Fixed-Term' %} Unless earlier "
            "terminated in accordance with this clause, this Agreement "
            "shall automatically terminate on {{ fixed_term_end_date }} "
            "without further notice.{% endif %} Upon termination, the "
            "Employee shall return all property of the Employer in the "
            "Employee's possession, and accrued but unpaid compensation "
            "up to the date of termination shall be paid in accordance "
            "with applicable law."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 11,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Jurisdiction",
        # fixed_boilerplate from the start (third clean application of
        # the classification bar established from the MoU finding) — a
        # single Jinja {% if arbitration %} branch is all this needs; no
        # narrative judgment, so it never qualified for llm_fillable in
        # the first place.
        "source_text": (
            "{% if arbitration %}Any dispute arising out of or in "
            "connection with this Agreement shall be referred to "
            "arbitration under the Arbitration and Conciliation Act, "
            "1996, seated at {{ arbitration_seat }}, before a sole "
            "arbitrator, in the English language, with the courts at the "
            "seat having exclusive supervisory jurisdiction. [ADVOCATE "
            "REVIEW: confirm the number of arbitrators, whether an "
            "institution and rules apply (ad hoc vs. institutional, e.g. "
            "MCIA, SIAC, DIAC), and the language of arbitration are "
            "appropriate for this specific matter before use.]"
            "{% else %}This Agreement is governed by the laws of India, "
            "and the courts at the principal city of {{ state }} shall "
            "have exclusive jurisdiction over any dispute arising out of "
            "or in connection with this Agreement.{% endif %}"
        ),
    },
    {
        "clause_key": "miscellaneous",
        "display_order": 12,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Miscellaneous",
        "source_text": (
            "(a) Entire Agreement: This Agreement constitutes the entire "
            "understanding between the Parties with respect to its "
            "subject matter and supersedes all prior discussions, "
            "negotiations, and agreements, whether oral or written, "
            "relating thereto.\n"
            "(b) Amendment: This Agreement may be amended only by a "
            "written instrument signed by authorised representatives of "
            "both Parties.\n"
            "(c) Severability: If any provision of this Agreement is "
            "held invalid or unenforceable, the remaining provisions "
            "shall continue in full force and effect, and the invalid "
            "provision shall be replaced by a valid provision that most "
            "closely approximates its intent.\n"
            "(d) No Waiver: No failure or delay by either Party in "
            "exercising any right under this Agreement shall operate as "
            "a waiver of that right.\n"
            "(e) Notices: All notices under this Agreement shall be in "
            "writing and delivered to the addresses of the Parties set "
            "out above, by hand, registered post, or electronic mail "
            "with confirmation of receipt.\n"
            "(f) Counterparts: This Agreement may be executed in "
            "counterparts, including by electronic signature, each of "
            "which shall be deemed an original."
        ),
    },
]

# --- State law notes (TRD §3.4) -----------------------------------------
# Notice periods under the state Shops & Establishments Acts are
# deliberately NOT hardcoded into the Termination clause — the advocate
# specifies termination_notice_period directly per matter — but the
# statutory hook is surfaced here for Nitesh's awareness, same
# PENDING VERIFICATION posture as every other template's state_rules.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Employment Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 "
        "(as applicable to Delhi), Schedule 1A. Exact current figure pending confirmation. Also "
        "verify notice-period and other requirements under the Delhi Shops and Establishments Act, "
        "1954 for the specific establishment before relying on a contractually agreed notice period.",
        "registration_req": "Not compulsorily registrable — an employment agreement is not ordinarily "
        "an instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm stamp duty and Shops & Establishments Act notice-period "
        "requirements before relying on this note.",
        "source_url": "https://legislative.gov.in/sites/default/files/A1899-02.pdf",
    },
    {
        "state": "Maharashtra",
        "instrument": "Employment Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Maharashtra Stamp Act, 1958, "
        "Schedule I, Article 5. Exact current figure pending confirmation. Also verify notice-period "
        "and other requirements under the Maharashtra Shops and Establishments Act, 2017 for the "
        "specific establishment.",
        "registration_req": "Not compulsorily registrable — an employment agreement is not ordinarily "
        "an instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm stamp duty and Shops & Establishments Act notice-period "
        "requirements before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Employment Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 as "
        "applicable to Uttar Pradesh. Exact current figure pending confirmation. Also verify "
        "notice-period and other requirements under the applicable Uttar Pradesh Shops and "
        "Establishments legislation for the specific establishment.",
        "registration_req": "Not compulsorily registrable — an employment agreement is not ordinarily "
        "an instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm stamp duty and Shops & Establishments Act notice-period "
        "requirements before relying on this note.",
        "source_url": "https://igrsup.gov.in/",
    },
]


def _prune_orphaned_clauses(db, template_id: str, current_clause_keys: set[str]) -> None:
    """Delete template_clauses rows whose clause_key no longer appears in
    this script's CLAUSES list, so a rename/removal doesn't leave a
    landmine behind. See seed_service_agreement_template.py's identical
    helper for the full story (Sprint 2, 2026-08-02).
    """
    existing = (
        db.table("template_clauses")
        .select("id,clause_key")
        .eq("template_id", template_id)
        .execute()
        .data
        or []
    )
    for row in existing:
        if row["clause_key"] in current_clause_keys:
            continue
        clause_id = row["id"]
        has_fills = bool(
            db.table("draft_clause_fills").select("id").eq("template_clause_id", clause_id).limit(1).execute().data
        )
        has_reviews = bool(
            db.table("clause_reviews").select("id").eq("clause_id", clause_id).limit(1).execute().data
        )
        if has_fills or has_reviews:
            print(
                f"WARNING: orphaned template_clauses row {clause_id} "
                f"(clause_key={row['clause_key']!r}) is referenced by "
                f"{'draft_clause_fills' if has_fills else ''}"
                f"{' and ' if has_fills and has_reviews else ''}"
                f"{'clause_reviews' if has_reviews else ''} — not deleted. "
                f"It will keep rendering in new drafts if its "
                f"applicable_condition can still match; review manually."
            )
            continue
        db.table("template_clauses").delete().eq("id", clause_id).execute()
        print(f"Pruned orphaned template_clauses row {clause_id} (clause_key={row['clause_key']!r})")


class ReviewedClauseConflict(Exception):
    """A re-seed would silently change the baseline text under a clause
    Nitesh has already reviewed. See _write_clauses_preserving_review
    below for the full story."""


def _write_clauses_preserving_review(db, template_id: str, clauses: list[dict]) -> None:
    """Upsert template_clauses without ever silently touching current_text
    or review_status for an already-reviewed clause (review_status in
    ('kept', 'redrafted')); HALTS the whole run if this seed's
    source_text for such a clause has actually changed. See
    seed_service_agreement_template.py's identical helper for the full
    story (found live 2026-08-02: the old unconditional upsert reset
    current_text = source_text on every re-seed regardless of review
    state, silently destroying redrafts even on a no-op re-run).
    """
    existing_by_key = {
        row["clause_key"]: row
        for row in (
            db.table("template_clauses")
            .select("id,clause_key,source_text,review_status")
            .eq("template_id", template_id)
            .execute()
            .data
            or []
        )
    }

    protected_keys: set[str] = set()
    conflicts: list[tuple[str, str]] = []
    for clause in clauses:
        existing = existing_by_key.get(clause["clause_key"])
        if not existing or existing["review_status"] not in ("kept", "redrafted"):
            continue
        protected_keys.add(clause["clause_key"])
        if existing["source_text"] != clause["source_text"]:
            conflicts.append((clause["clause_key"], existing["review_status"]))

    if conflicts:
        lines = "\n".join(f"  - {key} (review_status={status!r})" for key, status in conflicts)
        raise ReviewedClauseConflict(
            "Re-seed HALTED — the following clauses have already been reviewed, "
            "but this seed script's source_text for them no longer matches what's "
            "stored. Re-seeding would silently change the baseline text under an "
            "already-reviewed clause. Resolve manually before re-running: either "
            "revert the source_text change for these clauses, or explicitly reset "
            "their review_status to 'unreviewed' (they will then need review again) "
            "if the content change is intentional.\n" + lines
        )

    normal_rows = []
    for c in clauses:
        if c["clause_key"] in protected_keys:
            continue
        row = {
            "template_id": template_id,
            "clause_key": c["clause_key"],
            "display_order": c["display_order"],
            "clause_type": c["clause_type"],
            "applicable_condition": c["applicable_condition"],
            "heading": c["heading"],
            "source_text": c["source_text"],
            "current_text": c["source_text"],
        }
        # review_status is deliberately omitted for a clause that
        # already has a DB row (even a non-protected one, i.e.
        # 'unreviewed' or 'deleted'), relying on Postgres upsert leaving
        # an omitted column untouched on conflict rather than resetting
        # it. Only a genuinely new clause (no existing row) needs it
        # explicit here, since there's no column DEFAULT to fall back
        # on when we're the ones constructing the row.
        if c["clause_key"] not in existing_by_key:
            row["review_status"] = "unreviewed"
        normal_rows.append(row)
    if normal_rows:
        db.table("template_clauses").upsert(normal_rows, on_conflict="template_id,clause_key").execute()

    for c in clauses:
        if c["clause_key"] not in protected_keys:
            continue
        db.table("template_clauses").update(
            {
                "display_order": c["display_order"],
                "clause_type": c["clause_type"],
                "applicable_condition": c["applicable_condition"],
                "heading": c["heading"],
            }
        ).eq("id", existing_by_key[c["clause_key"]]["id"]).execute()

    print(
        f"Upserted {len(normal_rows)} template_clauses rows; "
        f"preserved {len(protected_keys)} already-reviewed clause(s) untouched "
        f"(current_text/review_status kept, only structural fields refreshed)"
    )


def seed() -> None:
    db = service_client()
    schema_json = json.loads(SCHEMA_PATH.read_text())

    existing = (
        db.table("templates")
        .select("id")
        .eq("name", TEMPLATE_NAME)
        .eq("category", TEMPLATE_CATEGORY)
        .execute()
        .data
    )
    if existing:
        template_id = existing[0]["id"]
        db.table("templates").update(
            {
                "schema_json": schema_json,
                "docx_path": DOCX_PATH,
                "states_supported": STATES_SUPPORTED,
                "template_key": TEMPLATE_KEY,
            }
        ).eq("id", template_id).execute()
        print(f"Updated existing template row {template_id}")
    else:
        result = (
            db.table("templates")
            .insert(
                {
                    "name": TEMPLATE_NAME,
                    "category": TEMPLATE_CATEGORY,
                    "schema_json": schema_json,
                    "docx_path": DOCX_PATH,
                    "states_supported": STATES_SUPPORTED,
                    "template_key": TEMPLATE_KEY,
                }
            )
            .execute()
        )
        template_id = result.data[0]["id"]
        print(f"Inserted template row {template_id}")

    _write_clauses_preserving_review(db, template_id, CLAUSES)
    _prune_orphaned_clauses(db, template_id, {c["clause_key"] for c in CLAUSES})

    for rule in STATE_RULES:
        existing_rule = (
            db.table("state_rules")
            .select("id")
            .eq("state", rule["state"])
            .eq("instrument", rule["instrument"])
            .execute()
            .data
        )
        if existing_rule:
            db.table("state_rules").update(rule).eq("id", existing_rule[0]["id"]).execute()
        else:
            db.table("state_rules").insert(rule).execute()
    print(f"Upserted {len(STATE_RULES)} state_rules rows")


if __name__ == "__main__":
    seed()
