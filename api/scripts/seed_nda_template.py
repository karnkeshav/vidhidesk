#!/usr/bin/env python3
"""Seed the NDA template + its clause library (Sprint 2, Deliverable 1).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_nda_template.py

Idempotent: upserts the templates row by (name, category), and
template_clauses rows by (template_id, clause_key) — safe to re-run after
editing clause text below.

Clause content is hand-authored from the Indian Contract Act 1872 and
standard NDA drafting practice, per Project_Plan §6 ("no gold-standard
drafts — build from statute plus public sources, then Nitesh reviews
clause by clause"). Every row is inserted with review_status='unreviewed'
and the template itself defaults to review_status='beta' (migration
0007) — nothing here should be treated as final until the clause-review
loop runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "nda.schema.json"
DOCX_PATH = "templates/contracts/nda.docx"

TEMPLATE_NAME = "Non-Disclosure Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "nda"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

# --- Clause library ----------------------------------------------------------
# clause_type='fixed_boilerplate': source_text IS the final clause text,
# subject only to Jinja field substitution already resolved before this
# point (none of these reference form fields directly — they're pure
# boilerplate). clause_type='llm_fillable': source_text is the *prompt* the
# gateway is called with per matter; current_text mirrors it at seed time
# since there's no per-matter output yet — reviewing an llm_fillable
# clause at the template level means reviewing/refining that prompt, not
# a specific generated instance.
CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,  # unnumbered WHEREAS paragraphs, per convention
        # Bug found live (2026-08-01, Sprint 2): the original prompt never
        # passed party_a_name/party_b_name at all, so the model had no way
        # to write anything but generic labels ("Party A", "the Disclosing
        # Party") — defeating the entire point of the intake form. Worse
        # for the mutual variant specifically: _variant_role_labels() gives
        # BOTH parties the identical label "Disclosing Party and Receiving
        # Party" in the preamble, so hardcoding "the Disclosing Party ...
        # the Receiving Party" language here doesn't just omit names, it's
        # legally incoherent for a mutual NDA (neither party is uniquely
        # "the" Disclosing Party). Fixed: pass both names explicitly, and
        # branch on nda_variant (+ party_a_role for one_way) so the
        # instruction matches what the preamble actually established.
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Non-Disclosure "
            "Agreement between {{ party_a_name }} and {{ party_b_name }}. "
            "{% if nda_variant == 'mutual' %}"
            "This is a MUTUAL NDA: both parties may disclose confidential "
            "information to one another, each acting as both Disclosing "
            "Party and Receiving Party depending on who is sharing at a "
            "given moment. Refer to the parties by their actual names "
            "throughout — do not describe one party as exclusively 'the "
            "Disclosing Party' or the other as exclusively 'the Receiving "
            "Party', since that would misstate a mutual arrangement."
            "{% elif party_a_role == 'disclosing' %}"
            "This is a ONE-WAY NDA: {{ party_a_name }} is the Disclosing "
            "Party and {{ party_b_name }} is the Receiving Party."
            "{% else %}"
            "This is a ONE-WAY NDA: {{ party_b_name }} is the Disclosing "
            "Party and {{ party_a_name }} is the Receiving Party."
            "{% endif %}"
            " Business context provided by the client: {{ purpose }}. "
            "Additional categories of confidential information, if "
            "provided: {{ confidential_items }}. Write 2-3 formal WHEREAS "
            "paragraphs establishing why the parties are entering into "
            "this Agreement for the stated purpose. Refer to the parties "
            "by their actual names given above — never a generic "
            "placeholder like 'Party A' or 'Party B' — ending with 'NOW "
            "THEREFORE, in consideration of the mutual covenants "
            "contained herein, the Parties agree as follows:'. Do not "
            "invent facts beyond what is provided."
        ),
    },
    {
        "clause_key": "definitions",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Definitions",
        # Sub-numbering (1.1, 1.2, 1.3) stays hand-authored against clause
        # number 1 — a known limitation (see docs/lessons_learned.md): only
        # safe because no conditional clause can ever precede Definitions
        # in this template. Re-check before assuming it elsewhere.
        "source_text": (
            "1.1 “Confidential Information” means any and all technical, "
            "commercial, financial, or business information disclosed by a "
            "Party (the “Disclosing Party”) to the other Party (the "
            "“Receiving Party”), whether in oral, written, electronic, or "
            "any other form, that is designated as confidential at the time of "
            "disclosure or that a reasonable person would understand to be "
            "confidential given the nature of the information and the "
            "circumstances of disclosure.\n"
            "1.2 “Purpose” means the purpose set out in the Recitals above, "
            "being the sole permitted purpose for which Confidential "
            "Information may be used by the Receiving Party.\n"
            "1.3 “Affiliate” means, in relation to a Party, any entity that "
            "directly or indirectly controls, is controlled by, or is under "
            "common control with that Party."
        ),
    },
    {
        "clause_key": "exclusions_from_confidential_info",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Exclusions",
        "source_text": (
            "Confidential Information does not include information that the "
            "Receiving Party can demonstrate: (a) was already lawfully in its "
            "possession without an obligation of confidentiality prior to "
            "disclosure by the Disclosing Party; (b) is or becomes publicly "
            "available through no breach of this Agreement by the Receiving "
            "Party; (c) is independently developed by the Receiving Party "
            "without use of or reference to the Confidential Information; or "
            "(d) is rightfully received from a third party without breach of "
            "any obligation of confidentiality owed to the Disclosing Party."
        ),
    },
    {
        "clause_key": "confidentiality_obligations_mutual",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "nda_variant", "equals": "mutual"},
        "heading": "Confidentiality Obligations",
        "source_text": (
            "Each Party, when acting as a Receiving Party, agrees that it "
            "shall: (a) hold the Confidential Information of the other Party "
            "in strict confidence; (b) use the Confidential Information "
            "solely for the Purpose; (c) not disclose the Confidential "
            "Information to any third party except as permitted under the "
            "Permitted Disclosures clause below; and (d) protect the "
            "Confidential Information using at least the same degree of care "
            "it uses to protect its own confidential information of similar "
            "nature, and in no event less than reasonable care."
        ),
    },
    {
        "clause_key": "confidentiality_obligations_one_way",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "nda_variant", "equals": "one_way"},
        "heading": "Confidentiality Obligations",
        "source_text": (
            "The Receiving Party agrees that it shall: (a) hold the "
            "Confidential Information in strict confidence; (b) use the "
            "Confidential Information solely for the Purpose; (c) not "
            "disclose the Confidential Information to any third party except "
            "as permitted under the Permitted Disclosures clause below; and "
            "(d) protect the Confidential Information using at least the same "
            "degree of care it uses to protect its own confidential "
            "information of similar nature, and in no event less than "
            "reasonable care. Nothing in this Agreement obligates the "
            "Disclosing Party to disclose any particular information, and the "
            "Disclosing Party may, at its sole discretion, determine what "
            "information (if any) to disclose."
        ),
    },
    {
        "clause_key": "permitted_disclosures",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Permitted Disclosures",
        "source_text": (
            "The Receiving Party may disclose Confidential Information: (a) "
            "to its employees, officers, directors, and professional "
            "advisors who have a genuine need to know such information for "
            "the Purpose and who are bound by confidentiality obligations no "
            "less protective than those in this Agreement; or (b) to the "
            "extent required by applicable law, regulation, or a valid order "
            "of a court or governmental authority of competent jurisdiction, "
            "provided that, where legally permissible, the Receiving Party "
            "gives the Disclosing Party prompt written notice of such "
            "requirement prior to disclosure so as to afford the Disclosing "
            "Party an opportunity to seek a protective order or other "
            "appropriate remedy."
        ),
    },
    {
        "clause_key": "return_or_destruction",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Return or Destruction of Confidential Information",
        "source_text": (
            "Upon the written request of the Disclosing Party, or upon "
            "termination or expiry of this Agreement, the Receiving Party "
            "shall promptly return or, at the Disclosing Party’s election, "
            "destroy all Confidential Information in its possession or "
            "control, including all copies, extracts, and summaries thereof, "
            "and shall certify such return or destruction in writing if "
            "requested; provided that the Receiving Party may retain one copy "
            "solely for legal compliance and record-keeping purposes, subject "
            "to the continuing confidentiality obligations of this "
            "Agreement."
        ),
    },
    {
        "clause_key": "no_license_no_obligation",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "No License; No Obligation",
        "source_text": (
            "Nothing in this Agreement shall be construed as granting any "
            "right or license, by implication, estoppel, or otherwise, under "
            "any patent, copyright, trademark, trade secret, or other "
            "intellectual property right, except the limited right to use "
            "the Confidential Information strictly for the Purpose. Nothing "
            "in this Agreement obligates either Party to proceed with any "
            "transaction or relationship contemplated by the Purpose, and "
            "either Party may terminate discussions at any time without "
            "liability, save for the obligations under this Agreement."
        ),
    },
    {
        "clause_key": "remedies",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Remedies",
        "source_text": (
            "Each Party acknowledges that unauthorised disclosure or use of "
            "Confidential Information may cause irreparable harm to the "
            "Disclosing Party for which monetary damages alone may not be an "
            "adequate remedy. Accordingly, in addition to any other rights "
            "and remedies available under the Indian Contract Act, 1872 and "
            "the Specific Relief Act, 1963 — including damages under "
            "Sections 73 and 74 of the Indian Contract Act, 1872 — the "
            "Disclosing Party shall be entitled to seek injunctive or other "
            "equitable relief to restrain any actual or threatened breach of "
            "this Agreement, without the necessity of proving actual damages "
            "or posting any bond."
        ),
    },
    {
        "clause_key": "term_and_survival",
        "display_order": 9,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Term and Survival",
        "source_text": (
            "Draft the Term and Survival clause for this Non-Disclosure "
            "Agreement (do not include a numbered heading — the caller adds "
            "one). The client has specified the following term/duration: "
            "{{ tenure }}. State the Effective Date, the term, and that the "
            "confidentiality obligations under this Agreement survive "
            "termination or expiry for a stated period. If the duration is "
            "expressed as 'during the subsistence of the underlying "
            "agreement' or similarly open-ended, still specify a concrete "
            "survival period (typically 3 years) for the confidentiality "
            "obligations after termination, and note in the drafted text that "
            "this default should be confirmed with the client."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 10,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Governing Law and Jurisdiction",
        # Same design gap as Service Agreement's identical clause,
        # flagged 2026-08-01: no intake field for arbitrator count,
        # institution/rules, or language, so every matter gets the same
        # minimal clause. Same decision — flag for Nitesh's per-matter
        # attention in the drafted text rather than growing the intake
        # form for something genuinely deal-specific.
        "source_text": (
            "Draft the Governing Law and Dispute Resolution clause for this "
            "Non-Disclosure Agreement (do not include a numbered heading — "
            "the caller adds one). Governing state: {{ state }}. Arbitration "
            "requested: {{ arbitration }}. Arbitration seat (if requested): "
            "{{ arbitration_seat }}. If arbitration is requested, draft a "
            "clause providing that disputes shall be referred to arbitration "
            "under the Arbitration and Conciliation Act, 1996, seated at the "
            "specified city, before a sole arbitrator, in the English "
            "language, with the courts at the seat having exclusive "
            "supervisory jurisdiction, and end the clause with a bracketed "
            "note: '[ADVOCATE REVIEW: confirm the number of arbitrators, "
            "whether an institution and rules apply (ad hoc vs. "
            "institutional, e.g. MCIA, SIAC, DIAC), and the language of "
            "arbitration are appropriate for this specific matter before "
            "use.]'. If arbitration is not requested, draft a clause "
            "stating this Agreement is governed by the laws of India, with "
            "the courts at the principal city of the governing state "
            "having exclusive jurisdiction."
        ),
    },
    {
        "clause_key": "miscellaneous",
        "display_order": 11,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Miscellaneous",
        # Sub-numbering (10.1-10.6) hand-authored against clause number 10
        # — safe only because Miscellaneous is always this template's last
        # clause. Same known limitation noted on Definitions above.
        "source_text": (
            "10.1 Entire Agreement: This Agreement constitutes the entire "
            "understanding between the Parties with respect to its subject "
            "matter and supersedes all prior discussions, negotiations, and "
            "agreements, whether oral or written, relating thereto.\n"
            "10.2 Amendment: This Agreement may be amended only by a written "
            "instrument signed by authorised representatives of both "
            "Parties.\n"
            "10.3 Severability: If any provision of this Agreement is held "
            "invalid or unenforceable, the remaining provisions shall "
            "continue in full force and effect, and the invalid provision "
            "shall be replaced by a valid provision that most closely "
            "approximates its intent.\n"
            "10.4 No Waiver: No failure or delay by either Party in "
            "exercising any right under this Agreement shall operate as a "
            "waiver of that right.\n"
            "10.5 Notices: All notices under this Agreement shall be in "
            "writing and delivered to the addresses of the Parties set out "
            "above, by hand, registered post, or electronic mail with "
            "confirmation of receipt.\n"
            "10.6 Counterparts: This Agreement may be executed in "
            "counterparts, including by electronic signature, each of which "
            "shall be deemed an original."
        ),
    },
]

# --- State law notes (TRD §3.4) -----------------------------------------
# Stamp duty figures are NOT asserted as confirmed fact here — CLAUDE.md's
# statute-grounding posture applies to this hand-authored content too.
# last_verified is left null and the notes flag the figure as pending
# Nitesh's confirmation, mirroring the RERA guides' "last verified" /
# re-verify pattern (TRD §3.6) rather than presenting an unconfirmed
# number as settled.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Non-Disclosure Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 "
        "(as applicable to Delhi), Schedule 1A. Exact current figure pending confirmation.",
        "registration_req": "Not compulsorily registrable — an NDA is not an instrument listed under "
        "Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://legislative.gov.in/sites/default/files/A1899-02.pdf",
    },
    {
        "state": "Maharashtra",
        "instrument": "Non-Disclosure Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Maharashtra Stamp Act, 1958, "
        "Schedule I, Article 5. Exact current figure pending confirmation (this article is amended "
        "periodically).",
        "registration_req": "Not compulsorily registrable — an NDA is not an instrument listed under "
        "Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Non-Disclosure Agreement",
        "stamp_duty": "Indicative only — general 'Agreement' rate under the Indian Stamp Act, 1899 as "
        "applicable to Uttar Pradesh. Exact current figure pending confirmation.",
        "registration_req": "Not compulsorily registrable — an NDA is not an instrument listed under "
        "Section 17 of the Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty figure before relying on this note.",
        "source_url": "https://igrsup.gov.in/",
    },
]


def _prune_orphaned_clauses(db, template_id: str, current_clause_keys: set[str]) -> None:
    """Delete template_clauses rows whose clause_key no longer appears in
    this script's CLAUSES list, so a rename/removal doesn't leave a
    landmine behind.

    Found live 2026-08-02 in Service Agreement's seed script (identical
    upsert pattern to this one): renaming a clause_key left the OLD row
    in the DB — upsert(on_conflict=...) only inserts/updates rows present
    in its payload, it never removes rows that fell out of it. If that
    old row's applicable_condition was None ("always applicable" per
    _clause_is_applicable), it kept rendering as an extra, stale clause
    in every new draft alongside the correctly-renamed replacement.
    Applied here too even though NDA hasn't hit this yet, since it's the
    identical seeding pattern and the same rename risk exists any time a
    clause_key changes.

    Only deletes a row when it's actually safe to: no draft_clause_fills
    reference it (only possible for llm_fillable clauses, per Hard Rule 4
    auditability — a fixed_boilerplate row can never have one) and no
    clause_reviews reference it (Nitesh may have reviewed it via the
    admin clause-review screen, which isn't restricted by clause_type).
    Either reference means real audit-trail data would be lost by
    deleting, which this project's auditability requirement (CLAUDE.md
    Hard Rule 4) doesn't allow — in that case, warn loudly instead of
    silently leaving the landmine in place, so a human notices and
    decides (e.g. by hand-neutralising its applicable_condition).
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
