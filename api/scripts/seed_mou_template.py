#!/usr/bin/env python3
"""Seed the Memorandum of Understanding template + its clause library
(Sprint 2 Deliverable 2, Batch 3).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_mou_template.py

Idempotent: upserts the templates row by (name, category), and
template_clauses rows by (template_id, clause_key); prunes any orphaned
clause row via _prune_orphaned_clauses (same mechanism as
seed_nda_template.py / seed_service_agreement_template.py /
seed_consultancy_template.py — see docs/lessons_learned.md).

This is the simplest template in the Contracts rollout so far — a
deliberate validation of Sprint 2's abstractions (list repeater,
applicable_condition, an_or_a filter, schema-type-aware PII masking) on
a minimal template, not an exercise in adding new mechanisms. Deviations
from Consultancy's shape, approved 2026-08-02:

  - No IP, deliverables, or fee/payment fields at all — an MoU is a
    preliminary, largely non-binding record of intent, not a definitive
    agreement. The IP position (nothing transferred/licensed here) is
    folded into the Nature of this Memorandum clause instead of a
    dedicated IP clause.
  - New clause content, not a new mechanism: "Nature of this Memorandum"
    — states the MoU is non-binding except for Confidentiality, Costs
    and Expenses, and Governing Law and Jurisdiction, which bind
    immediately. This is the load-bearing clause in any MoU.
  - Term and Termination is fixed_boilerplate here, not llm_fillable
    like Consultancy/Service Agreement — MoU term logic is simple
    substitution (fixed term or until superseded by a definitive
    agreement + notice-based termination), with none of the material-
    breach/insolvency/cure-period narrative complexity that justified
    LLM drafting elsewhere.
  - Confidentiality reuses the applicable_condition-per-variant pattern
    (mutual / one-way-from-A / one-way-from-B) with direct
    {{ party_a_name }}/{{ party_b_name }} substitution — the same
    mechanism Consultancy/Service Agreement use, not NDA's
    _variant_role_labels() helper (that's hardcoded to variant_field ==
    "nda_variant" specifically and isn't reusable here).

Only 2 of 7 logical clauses are llm_fillable (Recitals, Governing Law
and Jurisdiction) — the rest is fixed boilerplate, exactly the
"mostly-boilerplate" shape the batch was meant to validate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "mou.schema.json"
DOCX_PATH = "templates/contracts/mou.docx"

TEMPLATE_NAME = "Memorandum of Understanding"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "mou"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Memorandum of "
            "Understanding between {{ party_a_name }} (Party A) and "
            "{{ party_b_name }} (Party B). Background provided by the "
            "client: {{ purpose }}. Write 2-3 formal WHEREAS paragraphs "
            "establishing the background and the objective of this "
            "understanding — why the Parties wish to record their mutual "
            "understanding on this matter, and what they intend to "
            "explore or work toward together. Refer to the parties by "
            "their actual names given above — never a generic placeholder "
            "like 'Party A' or 'Party B' — ending with 'NOW THEREFORE, the "
            "Parties record their mutual understanding as follows:'. Do "
            "not invent facts beyond what is provided, and do not state "
            "whether this Memorandum is binding or non-binding — the "
            "Nature of this Memorandum clause covers that separately."
        ),
    },
    {
        "clause_key": "nature_of_memorandum",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Nature of this Memorandum",
        "source_text": (
            "This Memorandum of Understanding records the mutual "
            "understanding and good-faith intent of the Parties in "
            "relation to the matters described herein and does not "
            "constitute a legally binding or enforceable contract between "
            "the Parties, save and except for the provisions of the "
            "Confidentiality, Costs and Expenses, and Governing Law and "
            "Jurisdiction clauses of this Memorandum, which shall be "
            "binding on the Parties with immediate effect notwithstanding "
            "the non-binding nature of the remainder of this Memorandum. "
            "Nothing in this Memorandum shall be construed as creating "
            "any obligation on either Party to enter into any definitive "
            "agreement, and any definitive agreement between the Parties, "
            "if executed, shall be a separate document containing its own "
            "binding terms, superseding this Memorandum to the extent of "
            "any inconsistency. Nothing in this Memorandum shall be "
            "construed as transferring, assigning, or licensing any "
            "intellectual property rights between the Parties; any such "
            "arrangement, if agreed, shall be recorded separately in a "
            "definitive agreement."
        ),
    },
    # Confidentiality direction as a real intake choice, three
    # applicable_condition-gated clause rows sharing one display_order/
    # heading — the standard mechanism for "same logical clause,
    # different content by variant" (see docs/lessons_learned.md).
    {
        "clause_key": "confidentiality_mutual",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "mutual"},
        "heading": "Confidentiality",
        "source_text": (
            "Each Party acknowledges that, in the course of the "
            "discussions and activities contemplated under this "
            "Memorandum, it may receive confidential and proprietary "
            "information of the other Party (“Confidential Information”). "
            "Each Party, when acting as the recipient of the other's "
            "Confidential Information, agrees that it shall: (a) hold such "
            "Confidential Information in strict confidence; (b) use it "
            "solely for the purpose of evaluating and pursuing the "
            "matters contemplated under this Memorandum; (c) not disclose "
            "it to any third party except to its employees, officers, or "
            "professional advisors who have a genuine need to know and "
            "are bound by confidentiality obligations no less protective "
            "than those in this Memorandum; and (d) protect it using at "
            "least the same degree of care it uses to protect its own "
            "confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination "
            "or expiry of this Memorandum for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_a",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_a"},
        "heading": "Confidentiality",
        "source_text": (
            "{{ party_b_name }} (Party B) acknowledges that in the course "
            "of the discussions and activities contemplated under this "
            "Memorandum it may receive confidential and proprietary "
            "information of {{ party_a_name }} (Party A) (“Confidential "
            "Information”). Party B agrees that it shall: (a) hold Party "
            "A's Confidential Information in strict confidence; (b) use "
            "it solely for the purpose of evaluating and pursuing the "
            "matters contemplated under this Memorandum; (c) not disclose "
            "it to any third party except to its employees, officers, or "
            "professional advisors who have a genuine need to know and "
            "are bound by confidentiality obligations no less protective "
            "than those in this Memorandum; and (d) protect it using at "
            "least the same degree of care it uses to protect its own "
            "confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination "
            "or expiry of this Memorandum for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_b",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_b"},
        "heading": "Confidentiality",
        "source_text": (
            "{{ party_a_name }} (Party A) acknowledges that in the course "
            "of the discussions and activities contemplated under this "
            "Memorandum it may receive confidential and proprietary "
            "information of {{ party_b_name }} (Party B) (“Confidential "
            "Information”). Party A agrees that it shall: (a) hold Party "
            "B's Confidential Information in strict confidence; (b) use "
            "it solely for the purpose of evaluating and pursuing the "
            "matters contemplated under this Memorandum; (c) not disclose "
            "it to any third party except to its employees, officers, or "
            "professional advisors who have a genuine need to know and "
            "are bound by confidentiality obligations no less protective "
            "than those in this Memorandum; and (d) protect it using at "
            "least the same degree of care it uses to protect its own "
            "confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination "
            "or expiry of this Memorandum for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "term_and_termination",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Term and Termination",
        "source_text": (
            "This Memorandum shall commence on the Effective Date and "
            "continue for {{ term_duration }}. Either Party may terminate "
            "this Memorandum for convenience at any time by giving the "
            "other Party {{ termination_notice_period }} written notice. "
            "Termination of this Memorandum shall not affect the "
            "Confidentiality clause, which shall survive as provided "
            "therein."
        ),
    },
    {
        "clause_key": "costs_and_expenses",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Costs and Expenses",
        "source_text": (
            "Each Party shall bear its own costs, charges, and expenses "
            "incurred in connection with the discussions, negotiations, "
            "and activities contemplated under this Memorandum, including "
            "without limitation legal, professional, travel, and "
            "administrative expenses, unless the Parties expressly agree "
            "otherwise in writing."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 6,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Governing Law and Jurisdiction",
        "source_text": (
            "Draft the Governing Law and Dispute Resolution clause for "
            "this Memorandum of Understanding (do not include a numbered "
            "heading — the caller adds one). Governing state: "
            "{{ state }}. Arbitration requested: {{ arbitration }}. "
            "Arbitration seat (if requested): {{ arbitration_seat }}. If "
            "arbitration is requested, draft a clause providing that "
            "disputes shall be referred to arbitration under the "
            "Arbitration and Conciliation Act, 1996, seated at the "
            "specified city, before a sole arbitrator, in the English "
            "language, with the courts at the seat having exclusive "
            "supervisory jurisdiction, and end the clause with a "
            "bracketed note: '[ADVOCATE REVIEW: confirm the number of "
            "arbitrators, whether an institution and rules apply (ad hoc "
            "vs. institutional, e.g. MCIA, SIAC, DIAC), and the language "
            "of arbitration are appropriate for this specific matter "
            "before use.]'. If arbitration is not requested, draft a "
            "clause stating this Memorandum is governed by the laws of "
            "India, with the courts at the principal city of the "
            "governing state having exclusive jurisdiction. Note that per "
            "the Nature of this Memorandum clause, this Governing Law "
            "clause is binding regardless of the non-binding status of "
            "the rest of this Memorandum."
        ),
    },
    {
        "clause_key": "miscellaneous",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Miscellaneous",
        "source_text": (
            "(a) Entire Understanding: This Memorandum constitutes the "
            "entire understanding between the Parties with respect to its "
            "subject matter and supersedes all prior discussions, "
            "negotiations, and understandings, whether oral or written, "
            "relating thereto.\n"
            "(b) Amendment: This Memorandum may be amended only by a "
            "written instrument signed by authorised representatives of "
            "both Parties.\n"
            "(c) Severability: If any provision of this Memorandum is "
            "held invalid or unenforceable, the remaining provisions "
            "shall continue in full force and effect, and the invalid "
            "provision shall be replaced by a valid provision that most "
            "closely approximates its intent.\n"
            "(d) No Waiver: No failure or delay by either Party in "
            "exercising any right under this Memorandum shall operate as "
            "a waiver of that right.\n"
            "(e) Notices: All notices under this Memorandum shall be in "
            "writing and delivered to the addresses of the Parties set "
            "out above, by hand, registered post, or electronic mail with "
            "confirmation of receipt.\n"
            "(f) Counterparts: This Memorandum may be executed in "
            "counterparts, including by electronic signature, each of "
            "which shall be deemed an original."
        ),
    },
]

# --- State law notes (TRD §3.4) -----------------------------------------
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Memorandum of Understanding",
        "stamp_duty": "Indicative only — an MoU that creates no binding legal obligations (other than "
        "the carve-outs noted in the Nature of this Memorandum clause) is generally treated as an "
        "unstamped record of intent, not a chargeable 'Agreement' under the Indian Stamp Act, 1899. "
        "This depends heavily on the actual substance of the document. Exact position pending confirmation.",
        "registration_req": "Not compulsorily registrable — not an instrument listed under Section 17 of "
        "the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm the stamp-duty position before relying on this note, "
        "especially if the MoU's carve-outs make any part of it substantively binding.",
        "source_url": "https://legislative.gov.in/sites/default/files/A1899-02.pdf",
    },
    {
        "state": "Maharashtra",
        "instrument": "Memorandum of Understanding",
        "stamp_duty": "Indicative only — see the Delhi note above on the general non-binding-MoU "
        "position; the Maharashtra Stamp Act, 1958 has its own specific treatment of MoUs in some "
        "contexts (e.g. real estate) that may not apply here. Exact position pending confirmation.",
        "registration_req": "Not compulsorily registrable — not an instrument listed under Section 17 of "
        "the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm the stamp-duty position before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Memorandum of Understanding",
        "stamp_duty": "Indicative only — see the Delhi note above on the general non-binding-MoU "
        "position. Exact position pending confirmation.",
        "registration_req": "Not compulsorily registrable — not an instrument listed under Section 17 of "
        "the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm the stamp-duty position before relying on this note.",
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
