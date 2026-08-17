#!/usr/bin/env python3
"""Seed the Sale Deed template + its clause library (RERA & Real Estate,
Phase 1 backend). Proves the existing Contracts template engine
(app/services/contracts.py::generate_draft, templates/template_clauses/
draft_versions) is reusable for RERA property deeds with zero new drafting
code — see docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md.

Run from /api:
    source .venv/bin/activate
    python scripts/seed_sale_deed_template.py

Idempotent — uses the shared scripts/template_seed_utils.py::seed_template_pipeline
helper (same one Employment/Lease Deed/etc. use), which preserves
already-reviewed clause content on re-seed and prunes orphaned rows safely.

Clause content is hand-authored from the Transfer of Property Act, 1882
(covenants of title, §55) and standard Indian conveyancing practice, per
this project's established "no gold-standard drafts — build from statute
plus public sources, then the advocate reviews clause by clause" posture
(same convention as every Contracts template — see seed_nda_template.py's
docstring). The template defaults to review_status='beta' (migration
0007) and every clause row is inserted 'unreviewed' — nothing here is
presented as final until Nitesh's clause-review loop runs. No state-specific
stamp duty/registration FIGURES are asserted as confirmed fact — STATE_RULES
below explicitly flags every figure as pending verification, exactly like
every other template's state_rules rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "rera" / "sale-deed.schema.json"
DOCX_PATH = "templates/rera/sale-deed.docx"

TEMPLATE_NAME = "Sale Deed"
TEMPLATE_CATEGORY = "rera"
TEMPLATE_KEY = "sale-deed"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,  # unnumbered WHEREAS paragraphs, same convention as NDA's recitals
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Sale Deed between "
            "{{ vendor_name }} (Vendor) and {{ purchaser_name }} (Purchaser) "
            "for the property described in the Schedule of Property. "
            "Background on how the Vendor acquired title, as provided by the "
            "client: {{ title_background }}. Write 1-3 formal WHEREAS "
            "paragraphs stating the Vendor's title background exactly as "
            "given above (do not invent any detail — a specific prior deed "
            "number, date, or registration office not given must not be "
            "fabricated; state only what is provided, in formal language) "
            "and that the Vendor has agreed to sell, and the Purchaser has "
            "agreed to purchase, the property for the consideration stated "
            "below, ending with 'NOW THIS DEED WITNESSETH as follows:'."
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
        "clause_key": "consideration_and_receipt",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Consideration and Receipt",
        "source_text": (
            "In consideration of the sum of {{ sale_consideration_amount }} "
            "(the “Sale Consideration”) paid by the Purchaser to the "
            "Vendor, receipt of which the Vendor hereby admits and "
            "acknowledges, particulars of payment being: "
            "{{ consideration_paid_details }}, the Vendor doth hereby "
            "convey, transfer, and assure unto the Purchaser, absolutely "
            "and forever, all the right, title, and interest of the Vendor "
            "in the Said Property, free from all encumbrances, charges, "
            "liens, and claims whatsoever, TO HAVE AND TO HOLD the Said "
            "Property unto the Purchaser absolutely."
        ),
    },
    {
        "clause_key": "covenants_of_title",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Covenants of Title",
        # Standard statutory covenants implied on a sale under the
        # Transfer of Property Act, 1882, Section 55(2) — restated here
        # expressly per Indian conveyancing practice, not an invented
        # obligation.
        "source_text": (
            "The Vendor hereby covenants with the Purchaser, in terms of "
            "Section 55(2) of the Transfer of Property Act, 1882, that: "
            "(a) the Vendor has good right, full power, and absolute "
            "authority to convey the Said Property to the Purchaser; (b) "
            "the Said Property is free from all encumbrances, save as may "
            "be expressly disclosed in this Deed; and (c) the Purchaser "
            "shall peaceably and quietly hold, possess, and enjoy the Said "
            "Property without any lawful interruption or disturbance from "
            "the Vendor or any person claiming through, under, or in trust "
            "for the Vendor."
        ),
    },
    {
        "clause_key": "delivery_of_possession",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Delivery of Possession",
        "source_text": (
            "The Vendor has delivered, and the Purchaser has taken, vacant "
            "physical possession of the Said Property on {{ possession_date }}, "
            "and the Purchaser shall henceforth be entitled to deal with "
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
            "The Vendor hereby agrees to indemnify and keep indemnified "
            "the Purchaser against any loss, claim, or demand arising out "
            "of any defect in the Vendor's title to the Said Property, or "
            "any encumbrance, charge, or claim existing on the Said "
            "Property as on the date of this Deed that was not disclosed "
            "to the Purchaser."
        ),
    },
    {
        "clause_key": "special_conditions",
        "display_order": 7,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Special Conditions",
        "source_text": (
            "Draft the Special Conditions clause for this Sale Deed (do "
            "not include a numbered heading — the caller adds one). "
            "Special conditions provided by the client, if any: "
            "{{ special_conditions }}. If none were provided, state "
            "exactly: 'No special conditions apply to this sale beyond "
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
        "source_text": (
            "This Deed is chargeable to stamp duty and compulsorily "
            "registrable under Section 17 of the Registration Act, 1908, "
            "the Said Property being immovable property of value exceeding "
            "one hundred rupees. The parties shall present this Deed for "
            "registration before the Sub-Registrar having jurisdiction "
            "over the Said Property, and shall bear stamp duty and "
            "registration charges as applicable under the stamp "
            "legislation in force in {{ property_state }} — see the "
            "state-specific note accompanying this template for indicative "
            "guidance, pending confirmation of the exact current rate."
        ),
    },
]

# Same "indicative only, pending verification" posture as every other
# template's STATE_RULES — no figure here is asserted as confirmed fact.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Sale Deed",
        "stamp_duty": "Indicative only — ad valorem rate on a Sale Deed (Conveyance) under the Indian "
        "Stamp Act, 1899 as applicable to Delhi, Schedule 1A. Exact current rate (and any "
        "gender-based concession) pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908 — "
        "conveyance of immovable property.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate and any applicable "
        "concession before relying on this note.",
        "source_url": "https://revenue.delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Sale Deed",
        "stamp_duty": "Indicative only — ad valorem rate under the Maharashtra Stamp Act, 1958, "
        "Schedule I, Article 25 (Conveyance). Exact current rate pending confirmation "
        "(this article is amended periodically and varies by local body/area).",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Sale Deed",
        "stamp_duty": "Indicative only — ad valorem rate under the Indian Stamp Act, 1899 as "
        "applicable to Uttar Pradesh. Exact current rate pending confirmation.",
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
    print(f"Sale Deed template ready: {template_id}")


if __name__ == "__main__":
    seed()
