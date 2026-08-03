"""Seed Joint Venture Agreement template and clauses into Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "joint-venture.schema.json"
DOCX_PATH = "templates/contracts/joint-venture.docx"

TEMPLATE_NAME = "Joint Venture Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "joint-venture"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        "source_text": (
            "Draft formal recitals for this Joint Venture Agreement between {{ party_a_name }} (Partner A) and {{ party_b_name }} (Partner B). "
            "State that the Parties desire to combine their expertise, capital, and resources to establish a joint venture for the purpose of "
            "{{ jv_purpose }}. Refer to parties by real names. End with 'NOW THEREFORE, the Parties agree as follows:'."
        ),
    },
    {
        "clause_key": "objective_and_scope",
        "display_order": 2,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Objective and Scope of Joint Venture",
        "source_text": (
            "Draft the Objective and Scope clause for this Joint Venture Agreement (do not include a numbered heading — the caller adds one). "
            "Scope details provided by client: {{ jv_purpose }}. Structure model: {{ jv_entity_type }}. "
            "Describe the business scope, target markets, operational milestones, and responsibilities assigned to Partner A and Partner B. "
            "Do not invent facts beyond what is provided."
        ),
    },
    {
        "clause_key": "equity_and_capital_structure",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Capital Structure and Equity Ratio",
        "source_text": (
            "1. The capital and equity ratio of the Joint Venture shall be divided as follows: Partner A: {{ party_a_equity_share_pct }}, "
            "Partner B: {{ party_b_equity_share_pct }}.\n"
            "2. Initial capital contributions: {{ capital_contribution_details }}.\n"
            "3. Any subsequent capital call shall require mutual written consent of both Parties in proportion to their equity ratio."
        ),
    },
    {
        "clause_key": "governance_and_board",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governance and Board Representation",
        "source_text": (
            "1. Management of the Joint Venture shall be governed by a Board of Directors / Management Committee comprising nominees from both Parties.\n"
            "2. Reserved matters requiring unanimous approval of both Parties shall include: amendment of constitutional documents, major capital expenditure, "
            "incurring debt above agreed thresholds, and change in core business scope."
        ),
    },
    {
        "clause_key": "transfer_restrictions",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Transfer of Interest and Pre-emptive Rights",
        "source_text": (
            "Neither Party shall sell, transfer, pledge, or encumber its equity interest or shareholding in the Joint Venture to any third party "
            "without first offering the same to the non-transferring Party under Right of First Refusal (ROFR) / Pre-emptive rights."
        ),
    },
    {
        "clause_key": "deadlock_resolution",
        "display_order": 6,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Deadlock Resolution",
        "source_text": (
            "In the event of a Board or shareholder deadlock on a Reserved Matter, senior executive officers of Partner A and Partner B shall "
            "meet within 15 days to resolve the deadlock amicably. If unresolved after 30 days, the Parties may agree to invoke buy-sell mechanisms or voluntary dissolution."
        ),
    },
    {
        "clause_key": "confidentiality_and_ip",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Confidentiality and Intellectual Property",
        "source_text": (
            "1. Each Party shall maintain strict confidentiality over proprietary technical know-how and business plans disclosed for the JV.\n"
            "2. Pre-existing IP owned by either Party prior to the JV shall remain the exclusive property of that contributing Party."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Governing Law and Arbitration",
        "source_text": (
            "{% if arbitration %}Disputes arising out of or in connection with this Joint Venture Agreement shall be finally settled by arbitration "
            "under the Arbitration and Conciliation Act, 1996, seated at {{ arbitration_seat }}, in the English language.{% else %}This Agreement "
            "is governed by Indian law, and courts at {{ state }} shall have exclusive jurisdiction.{% endif %}"
        ),
    },
]

STATE_RULES = [
    {
        "state": "Delhi",
        "instrument": "Joint Venture Agreement",
        "stamp_duty": "Indicative stamp duty under Indian Stamp Act (Delhi Schedule) Article 5 for commercial agreements.",
        "registration_req": "Not compulsorily registrable unless transferring immovable property under Companies Act / Registration Act.",
        "notes": "Verify Companies Act, 2013 filings for incorporated JVs.",
        "source_url": "https://mca.gov.in/",
    },
    {
        "state": "Maharashtra",
        "instrument": "Joint Venture Agreement",
        "stamp_duty": "Stamp duty under Article 5(h) of Maharashtra Stamp Act, 1958.",
        "registration_req": "Optional unless transferring real estate assets.",
        "notes": "Must comply with ROC Mumbai filings.",
        "source_url": "https://igrmaharashtra.gov.in/",
    },
    {
        "state": "Uttar Pradesh",
        "instrument": "Joint Venture Agreement",
        "stamp_duty": "General commercial agreement stamp duty under UP Stamp Rules.",
        "registration_req": "Optional unless real estate assets are conveyed.",
        "notes": "ROC Kanpur compliance for incorporated entities.",
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
