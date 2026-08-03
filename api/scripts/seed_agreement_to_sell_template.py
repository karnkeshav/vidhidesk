"""Seed Agreement to Sell template and clauses into Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "agreement-to-sell.schema.json"
DOCX_PATH = "templates/contracts/agreement-to-sell.docx"

TEMPLATE_NAME = "Agreement to Sell"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "agreement-to-sell"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft formal recitals for this Agreement to Sell between {{ party_a_name }} (Vendor) and {{ party_b_name }} (Purchaser). "
            "State that Vendor is the absolute legal owner of property at {{ property_address }} and agrees to sell the property to Purchaser. "
            "Refer to parties by real names. End with 'NOW THEREFORE, the Parties agree as follows:'."
        ),
    },
    {
        "clause_key": "agreement_to_transfer",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Agreement for Sale of Property",
        "source_text": (
            "The Vendor hereby agrees to sell, convey, and transfer, and the Purchaser hereby agrees to purchase, all that immovable property "
            "situated at {{ property_address }} ('Scheduled Property'), together with all rights, title, interest, passages, and easements appurtenant thereto."
        ),
    },
    {
        "clause_key": "sale_consideration_and_earnest_money",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Sale Consideration and Payment Schedule",
        "source_text": (
            "1. The total sale consideration agreed between the Parties for the Scheduled Property is ₹{{ total_sale_consideration }}.\n"
            "2. The Purchaser has paid an advance / earnest money of ₹{{ earnest_money }} to the Vendor upon execution of this Agreement.\n"
            "3. The balance sale consideration of ₹{{ total_sale_consideration }} less ₹{{ earnest_money }} shall be paid by the Purchaser at the time of execution and registration of the final Sale Deed."
        ),
    },
    {
        "clause_key": "title_warranty_and_encumbrance",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Vendor's Title Warranty and Encumbrances",
        "source_text": (
            "The Vendor warrants that the Scheduled Property is free from all encumbrances, mortgages, charges, liens, litigations, attachments, and "
            "claims of any third party. The Vendor agrees to indemnify the Purchaser against any loss suffered due to defect in title."
        ),
    },
    {
        "clause_key": "execution_of_sale_deed_and_possession",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Execution of Sale Deed and Vacant Possession",
        "source_text": (
            "1. The final Sale Deed shall be executed and registered within {{ completion_period_months }} months from the date of this Agreement, "
            "upon receipt of the full sale consideration.\n"
            "2. Vacant, peaceful physical possession of the Scheduled Property shall be handed over by the Vendor to the Purchaser upon registration of the Sale Deed."
        ),
    },
    {
        "clause_key": "default_and_forfeiture",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Default and Consequences",
        "source_text": (
            "1. If the Purchaser fails to pay the balance sale consideration within the stipulated time, the Vendor shall be entitled to forfeit the earnest money.\n"
            "2. If the Vendor fails or refuses to execute the Sale Deed despite receipt of balance payment, the Purchaser shall be entitled to seek specific performance under the Specific Relief Act, 1963."
        ),
    },
    {
        "clause_key": "section_53a_notice",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Part Performance Notice (Section 53A Transfer of Property Act)",
        "source_text": (
            "[ADVOCATE REVIEW: Under Section 53A of the Transfer of Property Act, 1882 as amended by Act 48 of 2001, an Agreement to Sell "
            "involving part performance and delivery of possession must be compulsorily registered and stamped at full conveyance rates to claim Section 53A protection.]"
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Dispute Resolution",
        "source_text": (
            "{% if arbitration %}Disputes arising under this Agreement to Sell shall be settled by arbitration in {{ arbitration_seat }} "
            "under the Arbitration and Conciliation Act, 1996.{% else %}This Agreement shall be governed by Indian law and the courts at "
            "{{ state }} shall have exclusive jurisdiction.{% endif %}"
        ),
    },
]

STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Agreement to Sell",
        "stamp_duty": "5% (for men) / 3% (for women) stamp duty applicable on conveyance/sale deed in Delhi.",
        "registration_req": "Compulsory registration if possession is delivered under Section 17(1A) of Registration Act, 1908.",
        "notes": "E-stamping required via SHCIL.",
        "source_url": "https://delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Agreement to Sell",
        "stamp_duty": "5% to 7% stamp duty under Article 25 of Maharashtra Stamp Act based on local ready reckoner rates.",
        "registration_req": "Compulsory registration at Sub-Registrar Office under Section 17.",
        "notes": "Ready reckoner valuation applies.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Agreement to Sell",
        "stamp_duty": "7% stamp duty on sale consideration / circle rate.",
        "registration_req": "Compulsory registration under Section 17 of Registration Act, 1908.",
        "notes": "Circle rate valuation mandatory.",
        "source_url": "https://igrsup.gov.in/",
    },
]


def seed() -> None:
    seed_template_pipeline(
        TEMPLATE_NAME,
        TEMPLATE_CATEGORY,
        TEMPLATE_KEY,
        SCHEMA_PATH,
        DOCX_PATH,
        STATES_SUPPORTED,
        CLAUSES,
        STATE_RULES,
    )


if __name__ == "__main__":
    seed()
