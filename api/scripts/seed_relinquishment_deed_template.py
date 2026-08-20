#!/usr/bin/env python3
"""Seed the Relinquishment Deed template + its clause library (RERA & Real
Estate, Phase 2B-1 backend). Follows the exact Sale Deed pattern (see
seed_sale_deed_template.py's own docstring for the full rationale — not
repeated here): proves the existing Contracts template engine
(app/services/contracts.py::generate_draft, templates/template_clauses/
draft_versions) is reusable for a Relinquishment Deed with zero new
drafting code.

Run from /api:
    source .venv/bin/activate
    python scripts/seed_relinquishment_deed_template.py

Idempotent — uses the shared scripts/template_seed_utils.py::seed_template_pipeline
helper, same as every other template.

Unlike Sale Deed (Section 55(2) TPA) and Gift Deed (Sections 122/123
TPA), Indian law has no single TPA section that specifically defines a
"relinquishment"/"release" deed among co-owners — it is a conveyancing-
practice instrument governed by general transfer-of-property principles
and case law, not one codified provision. Per this project's "do not
fabricate legal authority" rule, the release/relinquishment clause below
therefore uses general conveyancing language without inventing a
specific statutory citation for the act of relinquishment itself. The
one statutory citation used — Registration Act, 1908, Section 17 (a
non-testamentary instrument that extinguishes a right, title, or interest
in immovable property is compulsorily registrable) — is well-known,
undisputed, and squarely applicable to a release/relinquishment deed.
No state-specific stamp-duty FIGURE is asserted as confirmed fact —
STATE_RULES below explicitly flags every note as pending verification,
exactly like Sale Deed's own STATE_RULES.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "rera" / "relinquishment-deed.schema.json"
DOCX_PATH = "templates/rera/relinquishment-deed.docx"

TEMPLATE_NAME = "Relinquishment Deed"
TEMPLATE_CATEGORY = "rera"
TEMPLATE_KEY = "relinquishment-deed"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,  # unnumbered WHEREAS paragraphs, same convention as Sale Deed's recitals
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Relinquishment "
            "Deed between {{ releasor_name }} (Releasor) and "
            "{{ releasee_name }} (Releasee) for the property described in "
            "the Schedule of Property. Co-ownership/relationship context, "
            "as provided by the client: {{ relationship_context }}. "
            "Background on how the joint ownership arose, as provided by "
            "the client: {{ title_background }}. Write 1-3 formal WHEREAS "
            "paragraphs stating the co-ownership background exactly as "
            "given above (do not invent any detail — a specific prior "
            "deed number, date, or registration office not given must not "
            "be fabricated; state only what is provided, in formal "
            "language) and that the Releasor is desirous of relinquishing "
            "the share described below in favour of the Releasee, ending "
            "with 'NOW THIS DEED OF RELINQUISHMENT WITNESSETH as "
            "follows:'."
        ),
    },
    {
        "clause_key": "property_schedule",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Schedule of Property",
        "source_text": (
            "ALL THAT piece and parcel of property described as follows:\n"
            "{{ property_description }}\n"
            "(hereinafter referred to as the “Said Property”)."
        ),
    },
    {
        "clause_key": "release_and_relinquishment",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Release and Relinquishment",
        "source_text": (
            "The Releasor doth hereby release, relinquish, and transfer "
            "unto the Releasee, absolutely and forever, all the right, "
            "title, and interest of the Releasor comprised in "
            "{{ share_relinquished }} in the Said Property, free from all "
            "encumbrances, charges, liens, and claims created by the "
            "Releasor, TO HAVE AND TO HOLD the same unto the Releasee "
            "absolutely, in consideration of {{ consideration_amount }} "
            "(state as 'Nil consideration' where no amount is given). "
            "Upon execution and registration of this Deed, the Releasor "
            "shall cease to have any right, title, claim, or interest "
            "whatsoever in the share so relinquished."
        ),
    },
    {
        "clause_key": "covenants",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Covenants",
        "source_text": (
            "The Releasor hereby covenants with the Releasee that: (a) "
            "the Releasor has good right and full power to relinquish the "
            "share described above; (b) the Releasor's share, so far as "
            "known to the Releasor, is free from encumbrances created by "
            "the Releasor, save as may be expressly disclosed in this "
            "Deed; and (c) the Releasee shall peaceably and quietly hold, "
            "possess, and enjoy the relinquished share without any lawful "
            "interruption or disturbance from the Releasor or any person "
            "claiming through, under, or in trust for the Releasor."
        ),
    },
    {
        "clause_key": "delivery_of_possession",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Possession",
        "source_text": (
            "Insofar as the Releasor was in joint possession of the Said "
            "Property, the Releasor hereby relinquishes such possession to "
            "the extent of the share released, and the Releasee shall "
            "henceforth be entitled to hold and deal with that share as "
            "its absolute owner, together with the remaining co-owners (if "
            "any) of the Said Property."
        ),
    },
    {
        "clause_key": "indemnity",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Indemnity",
        "source_text": (
            "The Releasor hereby agrees to indemnify and keep indemnified "
            "the Releasee against any loss, claim, or demand arising out "
            "of any encumbrance or claim created by the Releasor over the "
            "relinquished share that was not disclosed to the Releasee."
        ),
    },
    {
        "clause_key": "special_conditions",
        "display_order": 7,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Special Conditions",
        "source_text": (
            "Draft the Special Conditions clause for this Relinquishment "
            "Deed (do not include a numbered heading — the caller adds "
            "one). Special conditions provided by the client, if any: "
            "{{ special_conditions }}. If none were provided, state "
            "exactly: 'No special conditions apply to this relinquishment "
            "beyond what is stated elsewhere in this Deed.' Do not invent "
            "any condition not given above."
        ),
    },
    {
        "clause_key": "registration",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Stamp Duty and Registration",
        # Registration Act, 1908, Section 17 covers non-testamentary
        # instruments that extinguish a right, title, or interest in
        # immovable property -- a release/relinquishment deed falls
        # squarely within this, well-known and undisputed. No specific TPA
        # section is cited for the act of relinquishment itself (see
        # module docstring).
        "source_text": (
            "This Deed of Relinquishment is compulsorily registrable "
            "under Section 17 of the Registration Act, 1908, as an "
            "instrument extinguishing the Releasor's right, title, and "
            "interest in the share of the Said Property described above. "
            "The parties shall present this Deed for registration before "
            "the Sub-Registrar having jurisdiction over the Said Property, "
            "and shall bear stamp duty and registration charges as "
            "applicable under the stamp legislation in force in "
            "{{ property_state }} — see the state-specific note "
            "accompanying this template for indicative guidance, pending "
            "confirmation of the exact current rate and of any "
            "concessional treatment that may apply between specified "
            "co-owners/relatives."
        ),
    },
]

# Same "indicative only, pending verification" posture as Sale Deed's
# STATE_RULES -- no figure or concession here is asserted as confirmed
# fact.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Relinquishment Deed",
        "stamp_duty": "Indicative only — a Release/Relinquishment Deed is stamped under the Indian "
        "Stamp Act, 1899 as applicable to Delhi, Schedule 1A, subject to any concessional "
        "treatment between specified co-owners/relatives. Exact current rate and eligibility "
        "pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and any relative-based "
        "concession before relying on this note.",
        "source_url": "https://revenue.delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Relinquishment Deed",
        "stamp_duty": "Indicative only — the Maharashtra Stamp Act, 1958, Schedule I, Article 55 "
        "(Release) applies, with a distinct concessional rate historically available for "
        "releases between certain specified family members. Exact current rate and "
        "eligibility pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and relative-based "
        "concession eligibility before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Relinquishment Deed",
        "stamp_duty": "Indicative only — a Release/Relinquishment Deed is stamped under the Indian "
        "Stamp Act, 1899 as applicable to Uttar Pradesh. Exact current rate pending "
        "confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate before relying on this note.",
        "source_url": "https://igrsup.gov.in/",
    },
]


def seed() -> None:
    template_id = seed_template_pipeline(
        template_name=TEMPLATE_NAME,
        template_category=TEMPLATE_CATEGORY,
        template_key=TEMPLATE_KEY,
        schema_path=SCHEMA_PATH,
        docx_path=DOCX_PATH,
        states_supported=STATES_SUPPORTED,
        clauses=CLAUSES,
        state_rules=STATE_RULES,
    )
    print(f"Relinquishment Deed template ready: {template_id}")


if __name__ == "__main__":
    seed()
