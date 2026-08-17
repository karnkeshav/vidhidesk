#!/usr/bin/env python3
"""Seed the RERA Complaint (Delay in Possession) template + its clause
library. Proves the RERA complaint workflow reuses the existing generic
drafting engine (app/services/contracts.py::generate_draft) with zero new
drafting code — the same reuse decision as the Sale Deed template (see
seed_sale_deed_template.py and
docs/30_Implementation/RERA_BACKEND_INTEGRATION_CONTRACT.md).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_rera_complaint_template.py

Idempotent — uses the shared scripts/template_seed_utils.py::seed_template_pipeline
helper. Grounds clause cites only Section 18 of the Real Estate (Regulation
and Development) Act, 2016 — the well-known, undisputed statutory basis for
a delay-in-possession complaint (return of amount with interest, or
possession with delay compensation) — never a state-specific rule, never a
case citation. No STATE_RULES rows are seeded for this template: RERA
complaint procedure is forum/authority-specific, not a stamp-duty/
registration instrument the existing state_rules shape (stamp_duty,
registration_req) actually models — see rera-guides-based walkthrough
(app/services/rera.py) for the actual state-specific *procedural* content
model, kept separate per this sprint's "do not force everything into one
shape" instruction.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.template_seed_utils import seed_template_pipeline  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "rera" / "rera-complaint.schema.json"
DOCX_PATH = "templates/rera/rera-complaint.docx"

TEMPLATE_NAME = "RERA Complaint — Delay in Possession"
TEMPLATE_CATEGORY = "rera"
TEMPLATE_KEY = "rera-complaint"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "project_particulars",
        "display_order": 1,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Particulars of the Project and the Allotment",
        "source_text": (
            "1.1 The Respondent is the promoter of the real estate project "
            "known as “{{ project_name }}”, registered with the Real Estate "
            "Regulatory Authority under Registration No. "
            "{{ project_rera_registration_no }}.\n"
            "1.2 The Complainant booked Unit No. {{ unit_number }} in the "
            "said project and entered into an Agreement for Sale/Allotment "
            "with the Respondent dated {{ agreement_date }}, for a total "
            "sale consideration of {{ consideration_amount }}.\n"
            "1.3 The Complainant has, to date, paid a sum of "
            "{{ amount_paid }} towards the said total consideration of "
            "{{ consideration_amount }}."
        ),
    },
    {
        "clause_key": "facts",
        "display_order": 2,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Facts",
        "source_text": (
            "Draft the FACTS clause of a RERA complaint (do not include a "
            "numbered heading — the caller adds one). State the following "
            "facts, as provided by the client, as formal numbered "
            "paragraphs in chronological order, in the register 'That the "
            "Complainant states as follows:' — do not add, infer, or "
            "invent any fact not given below:\n"
            "{{ facts_narrative }}\n"
            "Promised date of possession per the agreement: "
            "{{ promised_possession_date }}. Actual date of possession "
            "given (if any — state 'possession has not yet been handed "
            "over as on the date of this complaint' if this is blank): "
            "{{ actual_possession_date }}."
        ),
    },
    {
        "clause_key": "grounds",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Grounds",
        # The ONLY statutory ground asserted here is Section 18 of the
        # RERA Act, 2016 itself — its text is well-known and undisputed
        # (not a state-specific rule, not a citation requiring
        # verification), so this is safe as fixed_boilerplate rather than
        # an LLM call that could invent additional grounds/sections.
        "source_text": (
            "The Respondent has failed to complete construction of, and "
            "hand over possession of, Unit No. {{ unit_number }} by the "
            "date specified in the Agreement for Sale, namely "
            "{{ promised_possession_date }}, in breach of the terms of the "
            "said Agreement and of Section 11(4)(a) of the Real Estate "
            "(Regulation and Development) Act, 2016 (\"the Act\"). By "
            "reason of the aforesaid delay, the Complainant is entitled to "
            "relief under Section 18 of the Act, which entitles an "
            "allottee, where the promoter fails to complete or is unable "
            "to give possession of an apartment in accordance with the "
            "terms of the agreement for sale, to either: (a) withdraw from "
            "the project and claim return of the amount paid together with "
            "interest at the prescribed rate and compensation, or (b) "
            "continue with the project and claim interest for every month "
            "of delay, till the handing over of possession, at the "
            "prescribed rate."
        ),
    },
    {
        "clause_key": "relief_sought",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Relief Sought",
        "source_text": (
            "In the premises aforesaid, the Complainant most respectfully "
            "prays that this Hon'ble Authority may be pleased to grant the "
            "following relief:\n{{ relief_sought }}\n"
            "and to pass such further or other order(s) as this Hon'ble "
            "Authority may deem fit and proper in the facts and "
            "circumstances of the case, in the interest of justice."
        ),
    },
    {
        "clause_key": "verification",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Verification",
        "source_text": (
            "I, {{ complainant_name }}, the Complainant above named, do "
            "hereby verify that the contents of the foregoing complaint "
            "are true and correct to my knowledge and belief, that no part "
            "of it is false, and that nothing material has been concealed "
            "therefrom. Verified at {{ jurisdiction_state }} on this "
            "{{ agreement_date }}."
        ),
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
        state_rules=[],
    )
    print(f"RERA Complaint template ready: {template_id}")


if __name__ == "__main__":
    seed()
