"""Seed Lease Deed template and clauses into Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "lease-deed.schema.json"
DOCX_PATH = "templates/contracts/lease-deed.docx"

TEMPLATE_NAME = "Lease Deed"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "lease-deed"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft formal recitals for this Lease Deed between {{ party_a_name }} (Lessor) and {{ party_b_name }} (Lessee). "
            "State that Lessor is the lawful owner of property at {{ property_address }} and agrees to demise the premises "
            "by way of lease to Lessee for {{ property_type }} purposes. Refer to parties by real names. End with 'NOW THIS DEED WITNESSETH AS FOLLOWS:'."
        ),
    },
    {
        "clause_key": "demise_of_premises_and_term",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Demise of Premises and Lease Term",
        "source_text": (
            "1. In consideration of the rent hereinafter reserved and covenants herein contained, the Lessor hereby demises unto "
            "the Lessee all that property situated at {{ property_address }} ('Demised Premises') to hold for a period of "
            "{{ lease_term_years }} years commencing from {{ effective_date }}.\n"
            "2. The Demised Premises shall be used strictly for {{ property_type }} purposes."
        ),
    },
    {
        "clause_key": "rent_and_escalation",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Rent and Escalation",
        "source_text": (
            "1. The Lessee shall pay to the Lessor a monthly rent of ₹{{ monthly_rent }}, payable in advance on or before the 7th day of each month.\n"
            "2. The monthly rent shall escalate by {{ rent_escalation_pct }} annually upon completion of every 12 months of the lease term."
        ),
    },
    {
        "clause_key": "security_deposit",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Security Deposit",
        "source_text": (
            "The Lessee has paid an interest-free refundable security deposit of ₹{{ security_deposit }} to the Lessor. "
            "The security deposit shall be refunded upon vacant handover of Demised Premises, after deduction of unpaid utilities or damages."
        ),
    },
    {
        "clause_key": "registration_and_stamp_duty",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Stamp Duty and Compulsory Registration Notice",
        "source_text": (
            "Under Section 107 of the Transfer of Property Act, 1882 and Section 17(1)(d) of the Registration Act, 1908, a lease of "
            "immovable property from year to year, or for any term exceeding one year, or reserving a yearly rent, can be made only by "
            "a registered instrument. Stamp duty and registration charges shall be borne by the Lessee."
        ),
    },
    {
        "clause_key": "repairs_and_alterations",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Repairs, Maintenance and Alterations",
        "source_text": (
            "1. Structural repairs shall be carried out by the Lessor at its cost.\n"
            "2. Day-to-day minor maintenance shall be borne by the Lessee. The Lessee shall not make structural alterations without prior written consent."
        ),
    },
    {
        "clause_key": "subletting_prohibition",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Prohibition against Subletting",
        "source_text": (
            "The Lessee shall not assign, sublet, transfer, or part with possession of the Demised Premises or any portion thereof "
            "to any third party without express written permission of the Lessor."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Dispute Resolution",
        "source_text": (
            "{% if arbitration %}Disputes arising under this Lease Deed shall be settled by arbitration in {{ arbitration_seat }} "
            "under the Arbitration and Conciliation Act, 1996.{% else %}This Deed is governed by the laws of India, and courts at "
            "{{ state }} shall have exclusive jurisdiction.{% endif %}"
        ),
    },
]

STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Lease Deed",
        "stamp_duty": "2% of total average annual rent for leases up to 5 years under Indian Stamp Act (Delhi Amendment).",
        "registration_req": "Compulsory registration under Section 17(1)(d) of Registration Act, 1908 for leases > 11 months.",
        "notes": "Must be executed on non-judicial stamp paper and registered at Sub-Registrar Office.",
        "source_url": "https://delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Lease Deed",
        "stamp_duty": "Calculated under Article 36 of Maharashtra Stamp Act based on term and total consideration.",
        "registration_req": "Compulsory registration under Section 17 of Registration Act, 1908.",
        "notes": "Registered at Sub-Registrar of Assurances.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Lease Deed",
        "stamp_duty": "2% of total average annual rent + deposit under UP Stamp Act.",
        "registration_req": "Compulsory registration under Section 17 of Registration Act, 1908.",
        "notes": "Requires e-stamping and biometric registration.",
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
