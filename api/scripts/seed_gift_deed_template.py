#!/usr/bin/env python3
"""Seed the Gift Deed template + its clause library (RERA & Real Estate,
Phase 2B-1 backend). Follows the exact Sale Deed pattern (see
seed_sale_deed_template.py's own docstring for the full rationale — not
repeated here): proves the existing Contracts template engine
(app/services/contracts.py::generate_draft, templates/template_clauses/
draft_versions) is reusable for a Gift Deed with zero new drafting code.

Run from /api:
    source .venv/bin/activate
    python scripts/seed_gift_deed_template.py

Idempotent — uses the shared scripts/template_seed_utils.py::seed_template_pipeline
helper, same as every other template.

Clause content is hand-authored from the Transfer of Property Act, 1882
(Section 122 — definition of "gift"; Section 123 — a gift of immovable
property must be effected by a registered instrument) and standard Indian
conveyancing practice, per this project's established "no gold-standard
drafts — build from statute plus public sources, then the advocate
reviews clause by clause" posture. Deliberately does NOT cite Section
55(2) TPA (Sale Deed's covenants-of-title basis) here — that section
governs a SELLER's obligations on a SALE specifically and would be an
incorrect citation for a gift, so the covenants clause below uses general
conveyancing language instead of a statutory citation it cannot
accurately support. No state-specific stamp-duty FIGURE or concession is
asserted as confirmed fact — STATE_RULES below explicitly flags every
note as pending verification, exactly like Sale Deed's own STATE_RULES.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "rera" / "gift-deed.schema.json"
DOCX_PATH = "templates/rera/gift-deed.docx"

TEMPLATE_NAME = "Gift Deed"
TEMPLATE_CATEGORY = "rera"
TEMPLATE_KEY = "gift-deed"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,  # unnumbered WHEREAS paragraphs, same convention as Sale Deed's recitals
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Gift Deed between "
            "{{ donor_name }} (Donor) and {{ donee_name }} (Donee) for the "
            "property described in the Schedule of Property. Relationship "
            "between the parties, as provided by the client (state plainly "
            "if none was given): {{ relationship_with_donee }}. Background "
            "on how the Donor acquired title, as provided by the client: "
            "{{ title_background }}. Write 1-3 formal WHEREAS paragraphs "
            "stating the Donor's title background exactly as given above "
            "(do not invent any detail — a specific prior deed number, "
            "date, or registration office not given must not be "
            "fabricated; state only what is provided, in formal language) "
            "and that the Donor, out of natural love and affection and "
            "without any monetary consideration, is desirous of making a "
            "gift of the property to the Donee, and the Donee has accepted "
            "the gift, ending with 'NOW THIS DEED OF GIFT WITNESSETH as "
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
        "clause_key": "gift_and_transfer",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Gift and Transfer",
        # Transfer of Property Act, 1882, Section 122 defines a gift as a
        # transfer of existing property made voluntarily, without
        # consideration, by a donor to a donee, and accepted by the donee —
        # restated here expressly per Indian conveyancing practice.
        "source_text": (
            "The Donor, out of natural love and affection and without any "
            "monetary consideration whatsoever, being a gift within the "
            "meaning of Section 122 of the Transfer of Property Act, 1882, "
            "doth hereby transfer, convey, and gift unto the Donee, "
            "absolutely and forever, all the right, title, and interest of "
            "the Donor in the Said Property, free from all encumbrances, "
            "charges, liens, and claims whatsoever, TO HAVE AND TO HOLD the "
            "Said Property unto the Donee absolutely. The Donee hereby "
            "accepts the said gift."
        ),
    },
    {
        "clause_key": "covenants_of_title",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Covenants of Title",
        # General conveyancing covenants, not tied to a specific TPA
        # section -- Section 55(2) TPA (Sale Deed's citation for this same
        # clause position) governs a seller's obligations on a sale, not a
        # gift, so it is not cited here; these covenants are standard
        # conveyancing practice, not a statutory quotation.
        "source_text": (
            "The Donor hereby covenants with the Donee that: (a) the Donor "
            "has good right, full power, and absolute authority to gift "
            "the Said Property to the Donee; (b) the Said Property is free "
            "from all encumbrances, save as may be expressly disclosed in "
            "this Deed; and (c) the Donee shall peaceably and quietly "
            "hold, possess, and enjoy the Said Property without any "
            "lawful interruption or disturbance from the Donor or any "
            "person claiming through, under, or in trust for the Donor."
        ),
    },
    {
        "clause_key": "delivery_of_possession",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Delivery of Possession",
        "source_text": (
            "The Donor has delivered, and the Donee has taken, vacant "
            "physical possession of the Said Property on {{ possession_date }}, "
            "and the Donee shall henceforth be entitled to deal with "
            "the Said Property as the absolute owner thereof."
        ),
    },
    {
        "clause_key": "indemnity",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Indemnity",
        "source_text": (
            "The Donor hereby agrees to indemnify and keep indemnified "
            "the Donee against any loss, claim, or demand arising out "
            "of any defect in the Donor's title to the Said Property, or "
            "any encumbrance, charge, or claim existing on the Said "
            "Property as on the date of this Deed that was not disclosed "
            "to the Donee."
        ),
    },
    {
        "clause_key": "special_conditions",
        "display_order": 7,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Special Conditions",
        "source_text": (
            "Draft the Special Conditions clause for this Gift Deed (do "
            "not include a numbered heading — the caller adds one). "
            "Special conditions provided by the client, if any: "
            "{{ special_conditions }}. If none were provided, state "
            "exactly: 'No special conditions apply to this gift beyond "
            "what is stated elsewhere in this Deed.' Do not invent any "
            "condition not given above."
        ),
    },
    {
        "clause_key": "registration",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Stamp Duty and Registration",
        # Section 123 TPA requires a gift of immovable property to be
        # effected by a registered instrument; Registration Act, 1908,
        # Section 17(1)(a) separately and expressly lists "instruments of
        # gift of immovable property" as compulsorily registrable — both
        # well-known, undisputed statutory bases, restated here without
        # asserting any specific stamp-duty figure or concession.
        "source_text": (
            "This Deed of Gift is required to be effected by a registered "
            "instrument under Section 123 of the Transfer of Property Act, "
            "1882, and is compulsorily registrable under Section 17(1)(a) "
            "of the Registration Act, 1908. The parties shall present this "
            "Deed for registration before the Sub-Registrar having "
            "jurisdiction over the Said Property, and shall bear stamp "
            "duty and registration charges as applicable under the stamp "
            "legislation in force in {{ property_state }} — see the "
            "state-specific note accompanying this template for indicative "
            "guidance, pending confirmation of the exact current rate and "
            "of any concession applicable to gifts between specified "
            "relatives."
        ),
    },
]

# Same "indicative only, pending verification" posture as Sale Deed's
# STATE_RULES -- no figure or concession here is asserted as confirmed
# fact.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Gift Deed",
        "stamp_duty": "Indicative only — a Gift Deed is stamped as a conveyance under the Indian Stamp "
        "Act, 1899 as applicable to Delhi, Schedule 1A, subject to any concession for gifts "
        "between specified relatives. Exact current rate and eligibility for any concession "
        "pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17(1)(a), Registration Act, 1908, "
        "and Section 123, Transfer of Property Act, 1882.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and any relative-based "
        "concession before relying on this note.",
        "source_url": "https://revenue.delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Gift Deed",
        "stamp_duty": "Indicative only — the Maharashtra Stamp Act, 1958, Schedule I, Article 34 "
        "(Gift) applies, with a distinct concessional rate historically available for gifts "
        "to certain specified family members. Exact current rate and eligibility pending "
        "confirmation (this article is amended periodically).",
        "registration_req": "Compulsorily registrable under Section 17(1)(a), Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and relative-based "
        "concession eligibility before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Gift Deed",
        "stamp_duty": "Indicative only — a Gift Deed is stamped as a conveyance under the Indian "
        "Stamp Act, 1899 as applicable to Uttar Pradesh, subject to any concession for gifts "
        "between specified relatives. Exact current rate and eligibility pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17(1)(a), Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and any concession "
        "before relying on this note.",
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
    print(f"Gift Deed template ready: {template_id}")


if __name__ == "__main__":
    seed()
