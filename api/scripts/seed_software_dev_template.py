"""Seed Software Development & Maintenance Agreement template and clauses into Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "software-dev.schema.json"
DOCX_PATH = "templates/contracts/software-dev.docx"

TEMPLATE_NAME = "Software Development Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "software-dev"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft formal recitals for this Software Development and Maintenance Agreement between {{ party_a_name }} (Developer) and {{ party_b_name }} (Client). "
            "State that Developer possesses software engineering expertise and Client wishes to engage Developer to design, develop, and maintain "
            "software titled '{{ software_name }}'. Refer to parties by real names. End with 'NOW THEREFORE, the Parties agree as follows:'."
        ),
    },
    {
        "clause_key": "scope_of_development_and_milestones",
        "display_order": 2,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Scope of Development and Acceptance Criteria",
        "source_text": (
            "Draft the Scope of Development clause for this Software Development Agreement (do not include a numbered heading — the caller adds one). "
            "Software name: {{ software_name }}. Development specifications provided by client: {{ scope_of_development }}. "
            "Describe the core modules, tech stack, testing procedure, and User Acceptance Testing (UAT) sign-off process. "
            "Do not invent facts beyond what is provided."
        ),
    },
    {
        "clause_key": "fees_and_payment_terms",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Fees and Payment Terms",
        "source_text": (
            "1. Client shall pay Developer a total project fee of ₹{{ total_project_fee }}, payable in milestone instalments tied to UAT sign-off.\n"
            "2. Invoices shall be payable within 15 days of receipt. Overdue invoices shall attract late interest of 12% per annum."
        ),
    },
    {
        "clause_key": "maintenance_and_sla_support",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "maintenance_support_included", "equals": True},
        "heading": "Maintenance and SLA Support",
        "source_text": (
            "Developer shall provide annual maintenance, bug fixes, and level-2 support for {{ software_name }} following UAT deployment. "
            "Critical Severity 1 defects shall be addressed within 4 hours; non-critical enhancements shall be scheduled in routine releases."
        ),
    },
    {
        "clause_key": "ip_full_client_ownership",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "ip_ownership_model", "equals": "Full Client Ownership"},
        "heading": "Intellectual Property Rights — Client Ownership",
        "source_text": (
            "Upon full payment of the project fee, all source code, object code, documentation, algorithms, and intellectual property in "
            "{{ software_name }} ('Work Product') shall belong exclusively to the Client. Developer hereby assigns all right, title, and interest "
            "in the Work Product to the Client, provided Developer retains ownership of pre-existing background tools and libraries."
        ),
    },
    {
        "clause_key": "ip_developer_license_model",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "ip_ownership_model", "equals": "Developer License Model"},
        "heading": "Intellectual Property Rights — License Model",
        "source_text": (
            "Developer retains sole ownership of all intellectual property, source code, and underlying architecture in {{ software_name }}. "
            "Subject to payment of fees, Developer grants Client a perpetual, non-exclusive, non-transferable license to use the software for internal business operations."
        ),
    },
    {
        "clause_key": "confidentiality_and_data_security",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Confidentiality and Data Protection",
        "source_text": (
            "1. Each Party shall maintain strict confidentiality over proprietary technical data, customer records, and source code.\n"
            "2. Developer agrees to comply with applicable Indian data security regulations (including Digital Personal Data Protection Act, 2023)."
        ),
    },
    {
        "clause_key": "warranty_and_limitation_of_liability",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Warranty and Limitation of Liability",
        "source_text": (
            "1. Developer warrants that for a period of {{ warranty_period_months }} months post-launch, {{ software_name }} shall operate substantially "
            "in accordance with functional specifications.\n"
            "2. Developer's aggregate financial liability under this Agreement shall not exceed the total fees paid by Client."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Arbitration",
        "source_text": (
            "{% if arbitration %}Disputes arising out of or in connection with this Agreement shall be settled by arbitration in {{ arbitration_seat }} "
            "under the Arbitration and Conciliation Act, 1996.{% else %}This Agreement is governed by Indian law, and courts at {{ state }} "
            "shall have exclusive jurisdiction.{% endif %}"
        ),
    },
]

STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Software Development Agreement",
        "stamp_duty": "Indicative stamp duty under Indian Stamp Act (Delhi Schedule) for IT/software service contracts.",
        "registration_req": "Not compulsorily registrable.",
        "notes": "DPDP Act 2023 compliance recommended for customer data processing.",
        "source_url": "https://delhi.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Software Development Agreement",
        "stamp_duty": "Stamp duty under Article 5(h) of Maharashtra Stamp Act, 1958.",
        "registration_req": "Not compulsorily registrable.",
        "notes": "Governed by Information Technology Act, 2000.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Software Development Agreement",
        "stamp_duty": "General commercial agreement stamp duty under UP Stamp Rules.",
        "registration_req": "Not compulsorily registrable.",
        "notes": "Verify IT policy incentives for Noida IT units.",
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
