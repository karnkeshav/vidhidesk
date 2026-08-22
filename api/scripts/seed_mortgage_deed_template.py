#!/usr/bin/env python3
"""Seed the Mortgage Deed template + its clause library (RERA & Real
Estate, Phase 2B-1 backend). Follows the exact Sale Deed pattern (see
seed_sale_deed_template.py's own docstring for the full rationale — not
repeated here): proves the existing Contracts template engine
(app/services/contracts.py::generate_draft, templates/template_clauses/
draft_versions) is reusable for a Mortgage Deed with zero new drafting
code.

Run from /api:
    source .venv/bin/activate
    python scripts/seed_mortgage_deed_template.py

Idempotent — uses the shared scripts/template_seed_utils.py::seed_template_pipeline
helper, same as every other template.

Models a SIMPLE MORTGAGE specifically (Transfer of Property Act, 1882,
Section 58(b) — mortgagor does not deliver possession, binds personally
to repay, and the mortgagee's remedy on default is to have the property
sold through a court, never to sell it directly) — the standard,
most-common registered-instrument mortgage, and the one form the
project's own drafting posture can support without asserting anything
about the several OTHER statutorily distinct mortgage types TPA Section
58 defines (usufructuary, English, mortgage by conditional sale, mortgage
by deposit of title-deeds — the last of which needs no registered
instrument at all under TPA and would be a materially different, and
therefore not interchangeable, template). Section 59 TPA (registration
requirement) and Section 60 TPA (mortgagor's right of redemption) are
both well-known, undisputed statutory bases, cited exactly where they
apply. No state-specific stamp-duty FIGURE is asserted as confirmed
fact — STATE_RULES below explicitly flags every note as pending
verification, exactly like Sale Deed's own STATE_RULES.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "rera" / "mortgage-deed.schema.json"
DOCX_PATH = "templates/rera/mortgage-deed.docx"

TEMPLATE_NAME = "Mortgage Deed"
TEMPLATE_CATEGORY = "rera"
TEMPLATE_KEY = "mortgage-deed"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,  # unnumbered WHEREAS paragraphs, same convention as Sale Deed's recitals
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Mortgage Deed "
            "between {{ mortgagor_name }} (Mortgagor) and {{ mortgagee_name }} "
            "(Mortgagee) for the property described in the Schedule of "
            "Property. Background on how the Mortgagor acquired title, as "
            "provided by the client: {{ title_background }}. Purpose of "
            "the loan, if provided (state plainly if none was given): "
            "{{ loan_purpose }}. Write 1-3 formal WHEREAS paragraphs "
            "stating the Mortgagor's title background exactly as given "
            "above (do not invent any detail — a specific prior deed "
            "number, date, or registration office not given must not be "
            "fabricated; state only what is provided, in formal language) "
            "and that the Mortgagee has agreed to lend, and the Mortgagor "
            "has agreed to borrow, the principal amount stated below "
            "against the security of the property, ending with 'NOW THIS "
            "DEED OF MORTGAGE WITNESSETH as follows:'."
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
        "clause_key": "mortgage_and_security",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Mortgage and Security",
        # Transfer of Property Act, 1882, Section 58(b) defines a simple
        # mortgage: the mortgagor does not deliver possession, binds
        # himself personally to pay the mortgage-money, and agrees,
        # expressly or impliedly, that the mortgagee may — in the event of
        # the mortgagor failing to pay — have the mortgaged property sold
        # through the intervention of a court (never a private sale by the
        # mortgagee). This template models a simple mortgage only.
        "source_text": (
            "By way of simple mortgage within the meaning of Section 58(b) "
            "of the Transfer of Property Act, 1882, the Mortgagor doth "
            "hereby mortgage the Said Property to the Mortgagee as "
            "security for repayment of the principal sum of "
            "{{ principal_amount }} (the “Secured Amount”) advanced by the "
            "Mortgagee to the Mortgagor. The Mortgagor shall remain in "
            "possession of the Said Property; no possession is delivered "
            "to the Mortgagee under this Deed. The Mortgagor binds "
            "himself/herself personally to repay the Secured Amount "
            "together with interest as stated below, and agrees that, in "
            "the event of default, the Mortgagee shall be entitled to have "
            "the Said Property sold through the intervention of a "
            "competent court, and to apply the sale proceeds towards the "
            "amount then due."
        ),
    },
    {
        "clause_key": "repayment_and_interest",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Repayment and Interest",
        "source_text": (
            "The Secured Amount shall carry interest at the rate of "
            "{{ interest_rate }} from the date of this Deed until "
            "repayment in full. The Mortgagor shall repay the Secured "
            "Amount together with such interest in accordance with the "
            "following terms: {{ repayment_terms }}."
        ),
    },
    {
        "clause_key": "mortgagor_covenants",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Mortgagor's Covenants",
        "source_text": (
            "The Mortgagor hereby covenants with the Mortgagee that: (a) "
            "the Mortgagor has good right, full power, and absolute "
            "authority to mortgage the Said Property; (b) the Said "
            "Property is free from all prior encumbrances, save as may be "
            "expressly disclosed in this Deed; (c) the Mortgagor shall not, "
            "without the prior written consent of the Mortgagee, create "
            "any further charge, mortgage, or encumbrance over the Said "
            "Property while the Secured Amount remains outstanding; and "
            "(d) the Mortgagor shall keep the Said Property insured and "
            "shall pay all taxes, rates, and outgoings in respect of it as "
            "they fall due."
        ),
    },
    {
        "clause_key": "default_and_redemption",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Default and Redemption",
        # Section 60 TPA is the well-known, undisputed statutory basis for
        # a mortgagor's right of redemption -- restated here, not invented.
        "source_text": (
            "Upon the Mortgagor repaying the Secured Amount together with "
            "all interest and other sums due under this Deed in full, the "
            "Mortgagee shall, at the Mortgagor's cost, execute a "
            "reconveyance or such other instrument as may be necessary to "
            "release the Said Property from this mortgage, in accordance "
            "with the Mortgagor's right of redemption under Section 60 of "
            "the Transfer of Property Act, 1882. In the event of default "
            "by the Mortgagor in repayment, the Mortgagee's remedies shall "
            "be as stated in the Mortgage and Security clause above."
        ),
    },
    {
        "clause_key": "special_conditions",
        "display_order": 7,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Special Conditions",
        "source_text": (
            "Draft the Special Conditions clause for this Mortgage Deed "
            "(do not include a numbered heading — the caller adds one). "
            "Special conditions provided by the client, if any: "
            "{{ special_conditions }}. If none were provided, state "
            "exactly: 'No special conditions apply to this mortgage "
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
        # Section 59 TPA requires a mortgage (other than by deposit of
        # title-deeds) securing Rs. 100 or more to be effected by a
        # registered instrument; Registration Act, 1908, Section 17
        # separately requires registration of instruments creating an
        # interest in immovable property of that value -- both well-known,
        # undisputed statutory bases, restated here without asserting any
        # specific stamp-duty figure.
        "source_text": (
            "This Mortgage Deed is required to be effected by a registered "
            "instrument under Section 59 of the Transfer of Property Act, "
            "1882, and is compulsorily registrable under Section 17 of the "
            "Registration Act, 1908, the Secured Amount exceeding one "
            "hundred rupees. The parties shall present this Deed for "
            "registration before the Sub-Registrar having jurisdiction "
            "over the Said Property, and shall bear stamp duty and "
            "registration charges as applicable under the stamp "
            "legislation in force in {{ property_state }} — see the "
            "state-specific note accompanying this template for indicative "
            "guidance, pending confirmation of the exact current rate."
        ),
    },
]

# Same "indicative only, pending verification" posture as Sale Deed's
# STATE_RULES -- no figure here is asserted as confirmed fact.
STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Mortgage Deed",
        "stamp_duty": "Indicative only — a Mortgage Deed (simple mortgage) is stamped under the "
        "Indian Stamp Act, 1899 as applicable to Delhi, Schedule 1A, typically at a rate "
        "distinct from a conveyance. Exact current rate pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908, and "
        "Section 59, Transfer of Property Act, 1882 (simple mortgage securing Rs. 100 or more).",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate before relying on this note.",
        "source_url": "https://revenue.delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Mortgage Deed",
        "stamp_duty": "Indicative only — the Maharashtra Stamp Act, 1958, Schedule I, Article 40 "
        "(Mortgage-deed) applies; the rate varies by mortgage sub-type and amount secured. "
        "Exact current rate pending confirmation.",
        "registration_req": "Compulsorily registrable under Section 17, Registration Act, 1908.",
        "notes": "PENDING VERIFICATION — confirm current stamp duty rate before relying on this note.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Mortgage Deed",
        "stamp_duty": "Indicative only — a Mortgage Deed is stamped under the Indian Stamp Act, "
        "1899 as applicable to Uttar Pradesh. Exact current rate pending confirmation.",
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
    print(f"Mortgage Deed template ready: {template_id}")


if __name__ == "__main__":
    seed()
