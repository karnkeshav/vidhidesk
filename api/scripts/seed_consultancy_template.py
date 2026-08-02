#!/usr/bin/env python3
"""Seed the Consultancy Agreement template + its clause library (Sprint 2
Deliverable 2, Batch 2).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_consultancy_template.py

Idempotent: upserts the templates row by (name, category), and
template_clauses rows by (template_id, clause_key); prunes any
template_clauses row whose clause_key no longer appears in CLAUSES below
(see _prune_orphaned_clauses — added from the start here per the
Sprint 2 lesson: renaming Service Agreement's confidentiality clause_key
left an orphaned row that silently re-rendered as a duplicate clause in
every new draft, caught only by a live browser E2E, not the unit suite).

Clause content hand-authored per Project_Plan §6 (no gold-standard
drafts). Every row is inserted with review_status='unreviewed' and the
template defaults to review_status='beta' (migration 0007) — nothing
here is final until Nitesh's clause-review loop runs.

Design notes carried over from Service Agreement's own lessons (Sprint 2,
2026-08-01/02), applied here from the start rather than discovered live:
  - recitals passes both party names explicitly and forbids generic
    "Party A"/"Party B" labels, and explicitly excludes fee/payment
    terms (the two recitals bugs found live on Service Agreement).
  - any llm_fillable clause using "Consultant"/"Client" terminology
    throughout also forbids generic party labels (the IP-clause
    terminology-drift bug).
  - confidentiality is a real intake choice (confidentiality_direction +
    confidentiality_survival_period), not hardcoded one-way — three
    applicable_condition-gated clause rows, the now-standard mechanism
    for "same logical clause, different content by variant" (see
    docs/lessons_learned.md).
  - the arbitration clause carries the same [ADVOCATE REVIEW: ...]
    bracketed note Service Agreement and NDA now both have.

Scope is split into two clauses (a design decision distinct from Service
Agreement's single fixed_boilerplate Scope-of-Services clause):
Deliverables (fixed_boilerplate, itemized, rendered only when the list
is non-empty) and Scope of Consulting Services (llm_fillable, a
narrative summary from `purpose`/`scope_notes`). Consulting engagements
are commonly advisory/retainer with no itemized deliverables at all
(`deliverables` is optional here, unlike Service Agreement's required
list) — when empty, something still needs to describe the engagement,
and that's inherently narrative, consistent with this project's
field-classification principle (numeric/enumerable -> structured
substitution, never LLM; narrative judgment required -> llm_fillable).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "consultancy.schema.json"
DOCX_PATH = "templates/contracts/consultancy.docx"

TEMPLATE_NAME = "Consultancy Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "consultancy"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Consultancy "
            "Agreement between {{ party_a_name }} (the Consultant) and "
            "{{ party_b_name }} (the Client). Business context provided by "
            "the client: {{ purpose }}. Write 2-3 formal WHEREAS paragraphs "
            "establishing the engagement — that {{ party_b_name }} wishes "
            "to engage {{ party_a_name }} to provide consulting services "
            "and {{ party_a_name }} is willing to do so on the terms of "
            "this Agreement. Refer to the parties by their actual names "
            "given above — never a generic placeholder like 'Party A' or "
            "'Party B' — ending with 'NOW THEREFORE, in consideration of "
            "the mutual covenants contained herein, the Parties agree as "
            "follows:'. Do not invent facts beyond what is provided, and "
            "do not describe the specific scope of services or "
            "deliverables here — the Scope of Consulting Services clause "
            "covers that separately. Do not state or characterise the fee "
            "amount, payment schedule, or fee structure (e.g. fixed fee, "
            "hourly, milestone-based, retainer) here either, under any "
            "circumstances — the Payment Terms clause covers that "
            "separately and you have not been told which structure "
            "applies to this matter."
        ),
    },
    {
        "clause_key": "definitions",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Definitions",
        "source_text": (
            "(a) “Services” means the consulting services described in the "
            "Scope of Consulting Services clause below, together with any "
            "Deliverables.\n"
            "(b) “Deliverables” means any specific outputs listed in the "
            "Deliverables clause below, if applicable to this engagement.\n"
            "(c) “Fees” means the amounts payable by the Client to the "
            "Consultant as set out in the Payment Terms clause below.\n"
            "(d) “Confidential Information” has the meaning given in the "
            "Confidentiality clause below."
        ),
    },
    {
        "clause_key": "scope_of_consulting_services",
        "display_order": 3,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Scope of Consulting Services",
        "source_text": (
            "Draft the Scope of Consulting Services clause for this "
            "Consultancy Agreement (do not include a numbered heading — "
            "the caller adds one). Business context: {{ purpose }}. "
            "Additional scope detail, if provided: {{ scope_notes }}. "
            "Write a clause describing, in narrative terms, the consulting "
            "services {{ party_a_name }} will provide to {{ party_b_name }} "
            "under this Agreement, drawing only on the context given "
            "above. Refer to the parties as 'the Consultant' and 'the "
            "Client' throughout — never 'Party A', 'Party B', or any other "
            "generic label. Do not invent specific deliverables, "
            "quantities, or dates — if the client has listed itemized "
            "deliverables, those are set out separately in the "
            "Deliverables clause below and must not be repeated or "
            "paraphrased here; this clause covers only the general nature "
            "and manner of the engagement (e.g. advisory, ongoing, "
            "project-based). Do not state or characterise the fee amount, "
            "payment schedule, or fee structure — the Payment Terms clause "
            "covers that separately."
        ),
    },
    {
        "clause_key": "deliverables",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        # List-inequality condition — works with the existing generic
        # _clause_is_applicable (Python `!=` on a list is well-defined),
        # no code change needed. Renders only when the advocate actually
        # entered at least one itemized deliverable; an advisory/retainer
        # engagement with none simply omits this clause, relying on the
        # narrative Scope of Consulting Services clause above instead.
        "applicable_condition": {"field": "deliverables", "not_equals": []},
        "heading": "Deliverables",
        "source_text": (
            "In addition to the Services described above, the Consultant "
            "shall deliver the following specific Deliverables to the "
            "Client:\n"
            "{% for item in deliverables %}- {{ item.description }}"
            "{% if item.due_date %} (due {{ item.due_date }}){% endif %}\n"
            "{% endfor %}\n"
            "Time is not of the essence for the dates specified above "
            "unless expressly agreed in writing, save where a Deliverable "
            "is expressly designated as time-critical."
        ),
    },
    {
        "clause_key": "payment_terms",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Payment Terms",
        "source_text": (
            "{% if fee_structure == 'Fixed Fee' %}"
            "In consideration of the Services, the Client shall pay the "
            "Consultant a fixed fee of {{ fee_amount }}, payable "
            "{{ payment_frequency }}."
            "{% elif fee_structure == 'Hourly Rate' %}"
            "In consideration of the Services, the Client shall pay the "
            "Consultant at the rate of {{ fee_amount }}, invoiced "
            "{{ payment_frequency }} on the basis of time actually spent, "
            "with supporting records available to the Client on reasonable "
            "request."
            "{% elif fee_structure == 'Milestone-Based' %}"
            "In consideration of the Services, the Client shall pay the "
            "Consultant {{ fee_amount }} upon completion and Client "
            "acceptance of each Deliverable specified above, invoiced "
            "{{ payment_frequency }}."
            "{% elif fee_structure == 'Retainer' %}"
            "In consideration of the Services, the Client shall pay the "
            "Consultant a retainer fee of {{ retainer_fee_amount }}, "
            "billed {{ retainer_frequency }}, for the duration of this "
            "Agreement."
            "{% if retainer_scope_hours %} The retainer covers "
            "{{ retainer_scope_hours }} of the Consultant's time; services "
            "requested by the Client in excess of this shall be billed "
            "separately at the Consultant's then-prevailing rates, subject "
            "to the Client's prior written approval.{% endif %}"
            "{% endif %}\n"
            "Any amount not paid by its due date shall accrue interest at "
            "{{ late_payment_interest_rate }} from the due date until "
            "payment, without prejudice to the Consultant's other rights "
            "and remedies."
        ),
    },
    {
        "clause_key": "ip_assignment",
        "display_order": 6,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Intellectual Property",
        "source_text": (
            "Draft the Intellectual Property clause for this Consultancy "
            "Agreement (do not include a numbered heading — the caller "
            "adds one). IP ownership model selected by the client: "
            "{{ ip_ownership_model }}. Pre-existing IP / carve-out notes, "
            "if any: {{ ip_carveout_notes }}. If 'Full Assignment to "
            "Client' is selected, draft a clause assigning all right, "
            "title, and interest in the Deliverables and any work product "
            "created under this Agreement to the Client upon full payment, "
            "with the Consultant executing further assurances as "
            "reasonably required, subject to any stated carve-outs. If "
            "'License Grant to Client (Consultant Retains Ownership)' is "
            "selected, draft a clause under which the Consultant retains "
            "ownership of the Deliverables and grants the Client a "
            "perpetual, non-exclusive, royalty-free license to use them "
            "for the Client's internal business purposes, subject to any "
            "stated carve-outs. If 'Custom / Negotiated' is selected, "
            "draft a clause stating the ownership position is as "
            "separately negotiated between the Parties and summarised in "
            "the carve-out notes, and flag that this should be reviewed "
            "carefully by the advocate before use. In all cases, expressly "
            "preserve each Party's pre-existing intellectual property. "
            "Refer to the parties consistently as 'the Consultant' and "
            "'the Client' throughout every sub-clause — never 'Party A', "
            "'Party B', or any other generic label."
        ),
    },
    # Confidentiality direction as a real intake choice, three
    # applicable_condition-gated clause rows sharing one display_order/
    # heading — the now-standard mechanism for "same logical clause,
    # different content by variant" (see docs/lessons_learned.md), built
    # in from the start rather than discovered live as a design gap the
    # way Service Agreement's was.
    {
        "clause_key": "confidentiality_mutual",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "mutual"},
        "heading": "Confidentiality",
        "source_text": (
            "Each Party acknowledges that, in the course of this "
            "Agreement, it may receive confidential and proprietary "
            "information of the other Party (“Confidential Information”) "
            "— including, without limitation, the Consultant's "
            "methodologies, frameworks, and know-how, and the Client's "
            "business, technical, and commercial information. Each Party, "
            "when acting as the recipient of the other's Confidential "
            "Information, agrees that it shall: (a) hold such Confidential "
            "Information in strict confidence; (b) use it solely to "
            "perform or receive the Services, as applicable; (c) not "
            "disclose it to any third party except to its employees, "
            "officers, or professional advisors who have a genuine need to "
            "know and are bound by confidentiality obligations no less "
            "protective than those in this Agreement; and (d) protect it "
            "using at least the same degree of care it uses to protect its "
            "own confidential information of similar nature, and in no "
            "event less than reasonable care. This clause survives "
            "termination or expiry of this Agreement for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_client",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_client"},
        "heading": "Confidentiality",
        "source_text": (
            "The Consultant acknowledges that in the course of performing "
            "the Services it may receive confidential and proprietary "
            "information of the Client (“Confidential Information”). The "
            "Consultant agrees that it shall: (a) hold the Client's "
            "Confidential Information in strict confidence; (b) use it "
            "solely to perform the Services; (c) not disclose it to any "
            "third party except to its employees, officers, or "
            "professional advisors who have a genuine need to know and are "
            "bound by confidentiality obligations no less protective than "
            "those in this Agreement; and (d) protect it using at least "
            "the same degree of care it uses to protect its own "
            "confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination "
            "or expiry of this Agreement for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_consultant",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_consultant"},
        "heading": "Confidentiality",
        "source_text": (
            "The Client acknowledges that in the course of receiving the "
            "Services it may receive confidential and proprietary "
            "information of the Consultant, including without limitation "
            "the Consultant's methodologies, frameworks, and know-how "
            "(“Confidential Information”). The Client agrees that it "
            "shall: (a) hold the Consultant's Confidential Information in "
            "strict confidence; (b) use it solely for the purpose of "
            "receiving and utilising the Services; (c) not disclose it to "
            "any third party except to its employees, officers, or "
            "professional advisors who have a genuine need to know and are "
            "bound by confidentiality obligations no less protective than "
            "those in this Agreement; and (d) protect it using at least "
            "the same degree of care it uses to protect its own "
            "confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination "
            "or expiry of this Agreement for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "no_license_no_obligation",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "No License; No Obligation",
        "source_text": (
            "Except as expressly set out in the Intellectual Property "
            "clause above, nothing in this Agreement shall be construed as "
            "granting either Party any right or license under the other "
            "Party's intellectual property. Nothing in this Agreement "
            "obligates the Client to engage the Consultant for any "
            "services beyond those expressly agreed in the Scope of "
            "Consulting Services clause."
        ),
    },
    {
        "clause_key": "term_and_termination",
        "display_order": 9,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Term and Termination",
        "source_text": (
            "Draft the Term and Termination clause for this Consultancy "
            "Agreement (do not include a numbered heading — the caller "
            "adds one). Term/duration specified by the client: "
            "{{ term_duration }}. Termination-for-convenience notice "
            "period: {{ termination_notice_period }}. Fee structure: "
            "{{ fee_structure }}. Draft a clause stating the Agreement "
            "commences on the Effective Date and continues for the stated "
            "term, that either Party may terminate for convenience by "
            "giving the stated notice period in writing, and that either "
            "Party may terminate immediately on written notice for the "
            "other Party's uncured material breach (with a reasonable cure "
            "period of not less than 15 days) or insolvency. State that "
            "accrued payment obligations for Services rendered (or, for a "
            "Retainer engagement, fees accrued up to the effective date of "
            "termination) before termination survive termination. Refer to "
            "the parties as 'the Consultant' and 'the Client' throughout "
            "— never 'Party A', 'Party B', or any other generic label."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 10,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Governing Law and Jurisdiction",
        "source_text": (
            "Draft the Governing Law and Dispute Resolution clause for "
            "this Consultancy Agreement (do not include a numbered "
            "heading — the caller adds one). Governing state: {{ state }}. "
            "Arbitration requested: {{ arbitration }}. Arbitration seat "
            "(if requested): {{ arbitration_seat }}. If arbitration is "
            "requested, draft a clause providing that disputes shall be "
            "referred to arbitration under the Arbitration and "
            "Conciliation Act, 1996, seated at the specified city, before "
            "a sole arbitrator, in the English language, with the courts "
            "at the seat having exclusive supervisory jurisdiction, and "
            "end the clause with a bracketed note: '[ADVOCATE REVIEW: "
            "confirm the number of arbitrators, whether an institution and "
            "rules apply (ad hoc vs. institutional, e.g. MCIA, SIAC, "
            "DIAC), and the language of arbitration are appropriate for "
            "this specific matter before use.]'. If arbitration is not "
            "requested, draft a clause stating this Agreement is governed "
            "by the laws of India, with the courts at the principal city "
            "of the governing state having exclusive jurisdiction."
        ),
    },
    {
        "clause_key": "miscellaneous",
        "display_order": 11,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Miscellaneous",
        "source_text": (
            "(a) Entire Agreement: This Agreement constitutes the entire "
            "understanding between the Parties with respect to its subject "
            "matter and supersedes all prior discussions, negotiations, "
            "and agreements, whether oral or written, relating thereto.\n"
            "(b) Amendment: This Agreement may be amended only by a "
            "written instrument signed by authorised representatives of "
            "both Parties.\n"
            "(c) Severability: If any provision of this Agreement is held "
            "invalid or unenforceable, the remaining provisions shall "
            "continue in full force and effect, and the invalid provision "
            "shall be replaced by a valid provision that most closely "
            "approximates its intent.\n"
            "(d) No Waiver: No failure or delay by either Party in "
            "exercising any right under this Agreement shall operate as a "
            "waiver of that right.\n"
            "(e) Notices: All notices under this Agreement shall be in "
            "writing and delivered to the addresses of the Parties set out "
            "above, by hand, registered post, or electronic mail with "
            "confirmation of receipt.\n"
            "(f) Counterparts: This Agreement may be executed in "
            "counterparts, including by electronic signature, each of "
            "which shall be deemed an original."
        ),
    },
]

# --- State law notes (TRD §3.4) -----------------------------------------
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Consultancy Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 "
        "(as applicable to Delhi), Schedule 1A. Exact current figure pending confirmation.",
        "registration_req": "Not compulsorily registrable — a Consultancy Agreement is not ordinarily an "
        "instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://legislative.gov.in/sites/default/files/A1899-02.pdf",
    },
    {
        "state": "Maharashtra",
        "instrument": "Consultancy Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Maharashtra Stamp Act, 1958, "
        "Schedule I, Article 5. Exact current figure pending confirmation (this article is amended "
        "periodically).",
        "registration_req": "Not compulsorily registrable — a Consultancy Agreement is not ordinarily an "
        "instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Consultancy Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 as "
        "applicable to Uttar Pradesh. Exact current figure pending confirmation.",
        "registration_req": "Not compulsorily registrable — a Consultancy Agreement is not ordinarily an "
        "instrument listed under Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://igrsup.gov.in/",
    },
]


def _prune_orphaned_clauses(db, template_id: str, current_clause_keys: set[str]) -> None:
    """Delete template_clauses rows whose clause_key no longer appears in
    this script's CLAUSES list, so a rename/removal doesn't leave a
    landmine behind. See seed_service_agreement_template.py's identical
    helper for the full story (Sprint 2, 2026-08-02): renaming a
    clause_key leaves the old row in the DB under upsert semantics, and
    if its applicable_condition was None it silently re-renders as a
    duplicate clause in every new draft. Only deletes when safe (no
    draft_clause_fills or clause_reviews references — CLAUDE.md Hard
    Rule 4 auditability); otherwise warns loudly instead.
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
