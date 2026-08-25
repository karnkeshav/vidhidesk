#!/usr/bin/env python3
"""Seed curated RERA filing-walkthrough content into `rera_guides`.

Three real, source-cited project-registration procedures — Maharashtra,
Delhi, and Uttar Pradesh — all grounded in the Real Estate (Regulation and
Development) Act, 2016 (Central Act 16 of 2016 — applies uniformly across
every state; no state has modified Sections 3-4 themselves) — Sections 3
and 4. Re-verified 2026-08-25 by directly opening the official India Code
PDF in a live browser session:
https://www.indiacode.nic.in/bitstream/123456789/2158/1/A201616.pdf
(loaded successfully — confirmed live, not just cited from search).

Because Sections 3-4 are the same central law for all three states, steps
1-5 of every group below paraphrase the identical statutory text, only
the Authority name changes (MahaRERA / Delhi RERA / UP RERA). Step 6 (the
state's own online portal submission) is where the states genuinely
differ, and where verification_status differs per state:

  - Maharashtra: portal https://maharerait.mahaonline.gov.in could NOT be
    reached this session (WebFetch: ECONNREFUSED; browser navigation:
    connection error) — "pending_verification".
  - Delhi: portal https://rera.delhi.gov.in/ (its official .gov.in
    domain, corroborated by multiple independent sources for the
    registration flow and contact details) could NOT be reached this
    session either (WebFetch: ECONNREFUSED; browser navigation: connection
    error, both on 2026-08-25) — "pending_verification".
  - Uttar Pradesh: portal https://www.up-rera.in/ WAS successfully
    fetched this session (2026-08-25) and its live content directly
    confirmed the promoter-then-project registration flow described in
    step 6 — "verified".

A human must confirm a "pending_verification" portal loads before
promoting that row to "verified".

Why this exists / how to use it for additional states/procedures
(CLAUDE.md Hard Rule 3 + this module's own design, app/services/rera.py's
docstring: "Never fabricates legal/procedural content... every
walkthrough step is a row someone curated into `rera_guides` with a
source_url... never synthesizes a plausible-looking step"):

  1. Find the real, official source for the (state, procedure) — the
     state RERA authority's own portal, a public circular/notification,
     the Act/Rules themselves, or an official user manual.
  2. Add a WALKTHROUGH_GROUPS entry with the real steps, each with:
       - heading / instruction: paraphrased directly from the source —
         never invent a document/requirement/portal step it doesn't state.
       - required_documents: only documents the source actually lists.
       - portal_url: the real e-filing portal URL for that step, if any.
       - warnings: real cautions from the source, or an honest
         operational note (e.g. "could not confirm this URL loads") —
         omit (None) if there is nothing genuine to warn about.
       - source_url: the exact page/document you took this from. Required
         to ever set verification_status to "verified" — see below.
       - verification_status: "unverified" until a human has actually
         checked the step against the live source at seed time, then
         "verified" (only pair with a real, independently-confirmed-live
         source_url) or "pending_verification" if checked but not fully
         confirmed (e.g. the source exists per search but didn't load).
  3. Run: `python scripts/seed_rera_guides.py` from /api (idempotent —
     upserts on the (state, procedure, step_no) unique index, safe to
     re-run after edits).

Uses service_client() because rera_guides is shared reference data, not
user-owned — same as templates/state_rules (see
app/services/rera.py's module docstring for the RLS reasoning: reads are
open to any authenticated user via rera_guides_read_authenticated,
migration 0002_rls.sql; writes are service-role only, which this script
uses).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

RERA_ACT_PDF = "https://www.indiacode.nic.in/bitstream/123456789/2158/1/A201616.pdf"
MAHARERA_PORTAL = "https://maharerait.mahaonline.gov.in"
DELHI_RERA_PORTAL = "https://rera.delhi.gov.in/"
UP_RERA_PORTAL = "https://www.up-rera.in/"

WALKTHROUGH_GROUPS: list[dict[str, Any]] = [
    {
        "state": "Maharashtra",
        "procedure": "project-registration",
        "steps": [
            {
                "step_no": 1,
                "heading": "Confirm the project must be registered before you advertise, market, or book units",
                "instruction": (
                    "Under Section 3 of the Real Estate (Regulation and Development) Act, 2016, "
                    "a promoter must register the real estate project with MahaRERA before "
                    "advertising, marketing, booking, selling, offering for sale, or inviting "
                    "persons to purchase any plot, apartment, or building in it. Registration "
                    "applies where the proposed land area exceeds 500 square metres, or the "
                    "number of apartments proposed across all phases exceeds 8 — whichever "
                    "condition applies, check both before concluding registration is optional."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": (
                    "Advertising or accepting bookings before registration is itself a "
                    "contravention under the Act — confirm registration status before any "
                    "marketing activity begins, not just before signing agreements for sale."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 2,
                "heading": "File the registration application with the prescribed fee",
                "instruction": (
                    "Under Section 4(1), the promoter applies to the Authority (MahaRERA) for "
                    "registration of the project in the prescribed form and manner, within the "
                    "prescribed time, accompanied by the prescribed fee. The remaining steps in "
                    "this walkthrough cover what Section 4(2) requires to accompany that "
                    "application."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 3,
                "heading": "Assemble promoter details and past-project disclosure",
                "instruction": (
                    "Section 4(2)(a)-(b) requires the application to enclose brief details of "
                    "the promoter's enterprise (name, registered address, type of enterprise, "
                    "and the names and photographs of the promoter), plus a disclosure of every "
                    "project the promoter has launched in the preceding five years — its "
                    "completion status, any delays, pending litigation, the type of land "
                    "involved, and outstanding dues."
                ),
                "required_documents": [
                    "Enterprise/promoter details: name, registered address, type of enterprise, promoter photographs",
                    "Disclosure of projects launched in the preceding 5 years: completion status, delays, pending cases, land type, outstanding dues",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 4,
                "heading": "Assemble project approvals and technical documents",
                "instruction": (
                    "Section 4(2)(c)-(f) requires authenticated copies of every approval and "
                    "commencement certificate obtained from the competent authority (separately "
                    "for each phase, if the project is phased), the sanctioned layout plan and "
                    "specifications for the project or phase, the plan of development works "
                    "including firefighting, drinking water, emergency evacuation, and renewable "
                    "energy facilities, and the project's location details with clear "
                    "demarcation of the land, its boundaries, and latitude/longitude of the end "
                    "points."
                ),
                "required_documents": [
                    "Authenticated copies of approvals and commencement certificates (per phase, if phased)",
                    "Sanctioned layout plan and specifications for the project/phase",
                    "Development-work plan: firefighting, drinking water, emergency evacuation, renewable-energy facilities",
                    "Location details: land demarcation, boundaries, latitude/longitude of end points",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 5,
                "heading": "Assemble sale documents, unit/personnel particulars, and the statutory affidavit",
                "instruction": (
                    "Section 4(2)(g)-(l) requires proforma copies of the allotment letter, "
                    "agreement for sale, and conveyance deed the promoter proposes to use; the "
                    "number, type, and carpet area of apartments for sale (including exclusive "
                    "balcony/verandah area) and the number and area of garages for sale; names "
                    "and addresses of any real estate agents engaged; names and addresses of the "
                    "contractors, architect, and structural engineer; and a declaratory affidavit "
                    "covering the promoter's legal title and any encumbrances, the time period "
                    "for completion, an undertaking that 70% of amounts realised from allottees "
                    "will be deposited in a separate scheduled-bank account to cover construction "
                    "and land cost, and the status of any pending approvals."
                ),
                "required_documents": [
                    "Proforma allotment letter, agreement for sale, and conveyance deed",
                    "Number, type, and carpet area of apartments for sale (incl. balcony/verandah area)",
                    "Number and area of garages for sale",
                    "Names and addresses of real estate agents engaged (if any)",
                    "Names and addresses of contractors, architect, and structural engineer",
                    "Declaratory affidavit: legal title and encumbrances, completion timeline, 70% escrow undertaking, pending approvals",
                ],
                "portal_url": None,
                "warnings": (
                    "The 70% escrow undertaking (amounts realised from allottees deposited in a "
                    "separate scheduled-bank account for construction and land cost) is a common "
                    "post-registration compliance failure — confirm the promoter's banking "
                    "arrangement can actually meet this before the affidavit is filed, not after."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 6,
                "heading": "Submit the application and fee on the MahaRERA online portal",
                "instruction": (
                    "File the completed application, the documents from steps 3-5, and the "
                    "prescribed fee through MahaRERA's online project-registration portal."
                ),
                "required_documents": [],
                "portal_url": MAHARERA_PORTAL,
                "warnings": (
                    "This portal URL could not be independently confirmed reachable during "
                    "content verification on 2026-08-25 (connection failed both via automated "
                    "fetch and a live browser session) — confirm it loads before relying on it, "
                    "and check MahaRERA's own site (maharera.maharashtra.gov.in) for the current "
                    "portal link if it has changed."
                ),
                "source_url": MAHARERA_PORTAL,
                "last_verified": None,
                "verification_status": "pending_verification",
            },
        ],
    },
    {
        "state": "Delhi",
        "procedure": "project-registration",
        "steps": [
            {
                "step_no": 1,
                "heading": "Confirm the project must be registered before you advertise, market, or book units",
                "instruction": (
                    "Under Section 3 of the Real Estate (Regulation and Development) Act, 2016, "
                    "a promoter must register the real estate project with the Real Estate "
                    "Regulatory Authority, Delhi (Delhi RERA) before advertising, marketing, "
                    "booking, selling, offering for sale, or inviting persons to purchase any "
                    "plot, apartment, or building in it. Registration applies where the proposed "
                    "land area exceeds 500 square metres, or the number of apartments proposed "
                    "across all phases exceeds 8 — whichever condition applies, check both before "
                    "concluding registration is optional."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": (
                    "Advertising or accepting bookings before registration is itself a "
                    "contravention under the Act — confirm registration status before any "
                    "marketing activity begins, not just before signing agreements for sale."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 2,
                "heading": "File the registration application with the prescribed fee",
                "instruction": (
                    "Under Section 4(1), the promoter applies to the Authority (Delhi RERA) for "
                    "registration of the project in the prescribed form and manner, within the "
                    "prescribed time, accompanied by the prescribed fee. The remaining steps in "
                    "this walkthrough cover what Section 4(2) requires to accompany that "
                    "application."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 3,
                "heading": "Assemble promoter details and past-project disclosure",
                "instruction": (
                    "Section 4(2)(a)-(b) requires the application to enclose brief details of "
                    "the promoter's enterprise (name, registered address, type of enterprise, "
                    "and the names and photographs of the promoter), plus a disclosure of every "
                    "project the promoter has launched in the preceding five years — its "
                    "completion status, any delays, pending litigation, the type of land "
                    "involved, and outstanding dues."
                ),
                "required_documents": [
                    "Enterprise/promoter details: name, registered address, type of enterprise, promoter photographs",
                    "Disclosure of projects launched in the preceding 5 years: completion status, delays, pending cases, land type, outstanding dues",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 4,
                "heading": "Assemble project approvals and technical documents",
                "instruction": (
                    "Section 4(2)(c)-(f) requires authenticated copies of every approval and "
                    "commencement certificate obtained from the competent authority (separately "
                    "for each phase, if the project is phased), the sanctioned layout plan and "
                    "specifications for the project or phase, the plan of development works "
                    "including firefighting, drinking water, emergency evacuation, and renewable "
                    "energy facilities, and the project's location details with clear "
                    "demarcation of the land, its boundaries, and latitude/longitude of the end "
                    "points."
                ),
                "required_documents": [
                    "Authenticated copies of approvals and commencement certificates (per phase, if phased)",
                    "Sanctioned layout plan and specifications for the project/phase",
                    "Development-work plan: firefighting, drinking water, emergency evacuation, renewable-energy facilities",
                    "Location details: land demarcation, boundaries, latitude/longitude of end points",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 5,
                "heading": "Assemble sale documents, unit/personnel particulars, and the statutory affidavit",
                "instruction": (
                    "Section 4(2)(g)-(l) requires proforma copies of the allotment letter, "
                    "agreement for sale, and conveyance deed the promoter proposes to use; the "
                    "number, type, and carpet area of apartments for sale (including exclusive "
                    "balcony/verandah area) and the number and area of garages for sale; names "
                    "and addresses of any real estate agents engaged; names and addresses of the "
                    "contractors, architect, and structural engineer; and a declaratory affidavit "
                    "covering the promoter's legal title and any encumbrances, the time period "
                    "for completion, an undertaking that 70% of amounts realised from allottees "
                    "will be deposited in a separate scheduled-bank account to cover construction "
                    "and land cost, and the status of any pending approvals."
                ),
                "required_documents": [
                    "Proforma allotment letter, agreement for sale, and conveyance deed",
                    "Number, type, and carpet area of apartments for sale (incl. balcony/verandah area)",
                    "Number and area of garages for sale",
                    "Names and addresses of real estate agents engaged (if any)",
                    "Names and addresses of contractors, architect, and structural engineer",
                    "Declaratory affidavit: legal title and encumbrances, completion timeline, 70% escrow undertaking, pending approvals",
                ],
                "portal_url": None,
                "warnings": (
                    "The 70% escrow undertaking (amounts realised from allottees deposited in a "
                    "separate scheduled-bank account for construction and land cost) is a common "
                    "post-registration compliance failure — confirm the promoter's banking "
                    "arrangement can actually meet this before the affidavit is filed, not after."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 6,
                "heading": "Submit the application and fee on the Delhi RERA online portal",
                "instruction": (
                    "File the completed application, the documents from steps 3-5, and the "
                    "prescribed fee through Delhi RERA's online project-registration portal."
                ),
                "required_documents": [],
                "portal_url": DELHI_RERA_PORTAL,
                "warnings": (
                    "This portal URL could not be independently confirmed reachable during "
                    "content verification on 2026-08-25 (connection failed both via automated "
                    "fetch and a live browser session) — confirm it loads before relying on it."
                ),
                "source_url": DELHI_RERA_PORTAL,
                "last_verified": None,
                "verification_status": "pending_verification",
            },
        ],
    },
    {
        "state": "Uttar Pradesh",
        "procedure": "project-registration",
        "steps": [
            {
                "step_no": 1,
                "heading": "Confirm the project must be registered before you advertise, market, or book units",
                "instruction": (
                    "Under Section 3 of the Real Estate (Regulation and Development) Act, 2016, "
                    "a promoter must register the real estate project with the Real Estate "
                    "Regulatory Authority, Uttar Pradesh (UP RERA) before advertising, marketing, "
                    "booking, selling, offering for sale, or inviting persons to purchase any "
                    "plot, apartment, or building in it. Registration applies where the proposed "
                    "land area exceeds 500 square metres, or the number of apartments proposed "
                    "across all phases exceeds 8 — whichever condition applies, check both before "
                    "concluding registration is optional."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": (
                    "Advertising or accepting bookings before registration is itself a "
                    "contravention under the Act — confirm registration status before any "
                    "marketing activity begins, not just before signing agreements for sale."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 2,
                "heading": "Register as a promoter before registering the project",
                "instruction": (
                    "Under Section 4(1), the promoter applies to the Authority (UP RERA) for "
                    "registration of the project in the prescribed form and manner, within the "
                    "prescribed time, accompanied by the prescribed fee. On UP RERA's own online "
                    "portal specifically, project registration is only accessible after promoter "
                    "registration is completed first — a promoter account must exist before a "
                    "project can be submitted for registration. The remaining steps in this "
                    "walkthrough cover what Section 4(2) requires to accompany the project "
                    "application itself."
                ),
                "required_documents": [],
                "portal_url": None,
                "warnings": None,
                "source_url": UP_RERA_PORTAL,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 3,
                "heading": "Assemble promoter details and past-project disclosure",
                "instruction": (
                    "Section 4(2)(a)-(b) requires the application to enclose brief details of "
                    "the promoter's enterprise (name, registered address, type of enterprise, "
                    "and the names and photographs of the promoter), plus a disclosure of every "
                    "project the promoter has launched in the preceding five years — its "
                    "completion status, any delays, pending litigation, the type of land "
                    "involved, and outstanding dues."
                ),
                "required_documents": [
                    "Enterprise/promoter details: name, registered address, type of enterprise, promoter photographs",
                    "Disclosure of projects launched in the preceding 5 years: completion status, delays, pending cases, land type, outstanding dues",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 4,
                "heading": "Assemble project approvals and technical documents",
                "instruction": (
                    "Section 4(2)(c)-(f) requires authenticated copies of every approval and "
                    "commencement certificate obtained from the competent authority (separately "
                    "for each phase, if the project is phased), the sanctioned layout plan and "
                    "specifications for the project or phase, the plan of development works "
                    "including firefighting, drinking water, emergency evacuation, and renewable "
                    "energy facilities, and the project's location details with clear "
                    "demarcation of the land, its boundaries, and latitude/longitude of the end "
                    "points."
                ),
                "required_documents": [
                    "Authenticated copies of approvals and commencement certificates (per phase, if phased)",
                    "Sanctioned layout plan and specifications for the project/phase",
                    "Development-work plan: firefighting, drinking water, emergency evacuation, renewable-energy facilities",
                    "Location details: land demarcation, boundaries, latitude/longitude of end points",
                ],
                "portal_url": None,
                "warnings": None,
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 5,
                "heading": "Assemble sale documents, unit/personnel particulars, and the statutory affidavit",
                "instruction": (
                    "Section 4(2)(g)-(l) requires proforma copies of the allotment letter, "
                    "agreement for sale, and conveyance deed the promoter proposes to use; the "
                    "number, type, and carpet area of apartments for sale (including exclusive "
                    "balcony/verandah area) and the number and area of garages for sale; names "
                    "and addresses of any real estate agents engaged; names and addresses of the "
                    "contractors, architect, and structural engineer; and a declaratory affidavit "
                    "covering the promoter's legal title and any encumbrances, the time period "
                    "for completion, an undertaking that 70% of amounts realised from allottees "
                    "will be deposited in a separate scheduled-bank account to cover construction "
                    "and land cost, and the status of any pending approvals."
                ),
                "required_documents": [
                    "Proforma allotment letter, agreement for sale, and conveyance deed",
                    "Number, type, and carpet area of apartments for sale (incl. balcony/verandah area)",
                    "Number and area of garages for sale",
                    "Names and addresses of real estate agents engaged (if any)",
                    "Names and addresses of contractors, architect, and structural engineer",
                    "Declaratory affidavit: legal title and encumbrances, completion timeline, 70% escrow undertaking, pending approvals",
                ],
                "portal_url": None,
                "warnings": (
                    "The 70% escrow undertaking (amounts realised from allottees deposited in a "
                    "separate scheduled-bank account for construction and land cost) is a common "
                    "post-registration compliance failure — confirm the promoter's banking "
                    "arrangement can actually meet this before the affidavit is filed, not after."
                ),
                "source_url": RERA_ACT_PDF,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
            {
                "step_no": 6,
                "heading": "Submit the application and fee on the UP RERA online portal",
                "instruction": (
                    "File the completed application, the documents from steps 3-5, and the "
                    "prescribed fee through UP RERA's online project-registration portal."
                ),
                "required_documents": [],
                "portal_url": UP_RERA_PORTAL,
                "warnings": None,
                "source_url": UP_RERA_PORTAL,
                "last_verified": "2026-08-25",
                "verification_status": "verified",
            },
        ],
    },
]


def seed_rera_guides(groups: list[dict[str, Any]]) -> None:
    db = service_client()
    total = 0
    for group in groups:
        state = group["state"]
        procedure = group["procedure"]
        rows = [
            {
                "state": state,
                "procedure": procedure,
                "step_no": step["step_no"],
                "heading": step.get("heading"),
                "instruction": step["instruction"],
                "required_documents": step.get("required_documents", []),
                "portal_url": step.get("portal_url"),
                "warnings": step.get("warnings"),
                "source_url": step.get("source_url"),
                "last_verified": step.get("last_verified"),
                "verification_status": step.get("verification_status", "unverified"),
            }
            for step in group["steps"]
        ]
        if any(r["verification_status"] == "verified" and not r["source_url"] for r in rows):
            raise ValueError(
                f"{state}/{procedure}: verification_status='verified' requires a source_url — "
                "never mark a step verified without one."
            )
        db.table("rera_guides").upsert(rows, on_conflict="state,procedure,step_no").execute()
        print(f"Upserted {len(rows)} step(s) for {state} / {procedure}")
        total += len(rows)
    print(f"Done — {total} row(s) upserted across {len(groups)} group(s).")


if __name__ == "__main__":
    seed_rera_guides(WALKTHROUGH_GROUPS)
