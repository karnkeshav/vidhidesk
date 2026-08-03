"""Seed Leave & Licence Agreement template and clauses into Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "leave-licence.schema.json"
DOCX_PATH = "templates/contracts/leave-licence.docx"

TEMPLATE_NAME = "Leave and Licence Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "leave-licence"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft the recitals for this Leave and Licence Agreement between {{ party_a_name }} (Licensor) "
            "and {{ party_b_name }} (Licensee). State that Licensor is the sole legal owner of property at "
            "{{ property_address }} and agrees to grant a revocable leave and licence to Licensee for {{ purpose_of_use }}. "
            "Refer to parties by actual names. End with 'NOW THEREFORE, the Parties agree as follows:'."
        ),
    },
    {
        "clause_key": "grant_of_licence_and_term",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Grant of Licence and Period",
        "source_text": (
            "1. The Licensor hereby grants to the Licensee a temporary, personal, non-transferable, and revocable licence "
            "to occupy and use the licensed premises situated at {{ property_address }} for {{ purpose_of_use }} only.\n"
            "2. The period of this Licence shall be {{ licence_period_months }} months commencing from {{ effective_date }}."
        ),
    },
    {
        "clause_key": "licence_fee_and_deposit",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Licence Fee and Security Deposit",
        "source_text": (
            "1. The Licensee shall pay to the Licensor a monthly licence fee of ₹{{ licence_fee_monthly }}, payable on or before "
            "the 5th day of each calendar month.\n"
            "2. The Licensee has deposited an interest-free security deposit of ₹{{ security_deposit }} with the Licensor upon execution "
            "of this Agreement, refundable upon vacant peaceful handover of the premises."
        ),
    },
    {
        "clause_key": "lock_in_and_termination",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Lock-in Period and Termination",
        "source_text": (
            "1. Both Parties agree to a mandatory lock-in period of {{ lock_in_period_months }} months from the commencement date. "
            "Neither Party may terminate this Agreement during the lock-in period.\n"
            "2. Post the lock-in period, either Party may terminate this Agreement by giving 1 month prior written notice."
        ),
    },
    {
        "clause_key": "use_and_maintenance",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Use of Premises and Maintenance",
        "source_text": (
            "1. The Licensee shall use the premises exclusively for {{ purpose_of_use }} and shall not carry out any unlawful activities.\n"
            "2. Electricity, water, and utility charges shall be borne directly by the Licensee as per actual meter readings."
        ),
    },
    {
        "clause_key": "no_tenancy_created",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Pure Licence — No Tenancy Created",
        "source_text": (
            "The Licensee explicitly agrees that this Agreement constitutes a pure leave and licence granted under Section 52 of the "
            "Indian Easements Act, 1882 (and Section 24 of the Maharashtra Rent Control Act, 1999 where applicable). This instrument "
            "does not create any leasehold interest, tenancy, or estate in favor of the Licensee."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Dispute Resolution",
        "source_text": (
            "{% if arbitration %}Any dispute arising out of this Agreement shall be referred to sole arbitration in {{ arbitration_seat }} "
            "under the Arbitration and Conciliation Act, 1996.{% else %}This Agreement shall be governed by the laws of India, "
            "and courts at {{ state }} shall have jurisdiction.[ADVOCATE REVIEW: In Maharashtra, disputes under Leave & Licence fall under Competent Authority under Section 24 of Maharashtra Rent Control Act, 1999.]{% endif %}"
        ),
    },
]

STATE_RULES = [
    {
        "state": "Maharashtra",
        "instrument": "Leave and Licence Agreement",
        "stamp_duty": "0.25% of total licence fee + non-refundable deposit for the period under Article 36A of Maharashtra Stamp Act.",
        "registration_req": "Compulsory registration required under Section 55 of the Maharashtra Rent Control Act, 1999.",
        "notes": "Must be registered online via IGR Maharashtra portal.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Delhi",
        "instrument": "Leave and Licence Agreement",
        "stamp_duty": "2% of total average annual rent/fee under Indian Stamp Act (Delhi Schedule).",
        "registration_req": "Compulsory if period exceeds 11 months under Section 17 of Registration Act, 1908.",
        "notes": "11-month agreements customary to avoid compulsory registration fee.",
        "source_url": "https://delhi.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Leave and Licence Agreement",
        "stamp_duty": "2% of total rent + deposit under UP Stamp Rules.",
        "registration_req": "Compulsory if period exceeds 11 months under Section 17 of Registration Act, 1908.",
        "notes": "Verify local sub-registrar office jurisdiction.",
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
