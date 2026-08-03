#!/usr/bin/env python3
"""Seed the Service Agreement template + its clause library (Sprint 2
Deliverable 2, Batch 1).

Run from /api:
    source .venv/bin/activate
    python scripts/seed_service_agreement_template.py

Idempotent: upserts the templates row by (name, category), and
template_clauses rows by (template_id, clause_key).

Clause content hand-authored per Project_Plan §6 (no gold-standard
drafts). Every row is inserted with review_status='unreviewed' and the
template defaults to review_status='beta' (migration 0007) — nothing
here is final until Nitesh's clause-review loop runs.

Sub-numbering note (see docs/lessons_learned.md's "Clause numbers are
auto-assigned; sub-numbers inside a clause are not"): Definitions and
Miscellaneous use lettered sub-points ("(a)", "(b)") instead of NDA's
"N.1"/"N.2" style, specifically because this template has the SLA clause
— the first genuinely conditionally-excluded clause — sitting between
them. A hardcoded "11.1" inside Miscellaneous would go stale the moment
SLA is excluded and Miscellaneous becomes clause 10 instead of 11.
Letter sub-points have no outer-number dependency, so they're safe
regardless of which conditional clauses land before them. Recommended
default for every future template from here on, not just this one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "templates" / "contracts" / "service-agreement.schema.json"
DOCX_PATH = "templates/contracts/service-agreement.docx"

TEMPLATE_NAME = "Service Agreement"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_KEY = "service-agreement"
STATES_SUPPORTED = ["Delhi", "Maharashtra", "Uttar Pradesh"]

CLAUSES = [
    {
        "clause_key": "recitals",
        "display_order": 1,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": None,
        # Same bug as NDA's recitals, found live 2026-08-01: the original
        # prompt never passed party_a_name/party_b_name, so the model had
        # no way to write anything but "the Client"/"the Service Provider"
        # — confirmed in the Sprint 2 Deliverable 2 E2E's own recitals
        # output ("WHEREAS, the Client desires to engage the Service
        # Provider..."), which wasn't flagged as wrong at the time but is
        # the identical defect. Fixed: pass both names explicitly. No
        # variant branching needed here (unlike NDA) — Service Agreement
        # is always asymmetric Provider/Client, no mutual-role ambiguity.
        #
        # Second bug, also found live 2026-08-01: with the party-name fix
        # in place, the recitals started asserting "a fixed fee model" for
        # a matter the advocate had actually configured as Milestone-Based
        # — fee_structure/fee_amount are never even passed into this
        # prompt's context, so that clause was pure invention. Root cause,
        # by contrast with the deliverables guard directly below (which
        # *does* work — deliverables never leak into the recitals output):
        # there was no equivalent "don't describe this here" instruction
        # for fee/payment terms, so the model fell back on generic
        # consideration-recital boilerplate ("in consideration of a fixed
        # fee...") it's seen in training data, unprompted. Fixed by adding
        # the same explicit exclusion used for deliverables.
        "source_text": (
            "Draft the recitals (WHEREAS clauses) for this Service "
            "Agreement between {{ party_a_name }} (the Service Provider) "
            "and {{ party_b_name }} (the Client). Business context "
            "provided by the client: {{ purpose }}. Write 2-3 formal "
            "WHEREAS paragraphs establishing the engagement — that "
            "{{ party_b_name }} wishes to engage {{ party_a_name }} to "
            "render certain services and {{ party_a_name }} is willing to "
            "do so on the terms of this Agreement. Refer to the parties "
            "by their actual names given above — never a generic "
            "placeholder like 'Party A' or 'Party B' — ending with 'NOW "
            "THEREFORE, in consideration of the mutual covenants "
            "contained herein, the Parties agree as follows:'. Do not "
            "invent facts beyond what is provided, and do not describe "
            "specific deliverables here — the Scope of Services clause "
            "covers those separately. Do not state or characterise the "
            "fee amount, payment schedule, or fee structure (e.g. fixed "
            "fee, hourly, milestone-based) here either, under any "
            "circumstances — the Payment Terms clause covers that "
            "separately and you have not been told which structure "
            "applies to this matter."
        ),
    },
    {
        "clause_key": "definitions",
        "display_order": 2,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Definitions",
        "source_text": (
            "(a) “Services” means the services described in the Scope of "
            "Services clause below, together with the Deliverables.\n"
            "(b) “Deliverables” means the specific outputs listed in the "
            "Scope of Services clause below.\n"
            "(c) “Fees” means the amounts payable by the Client to the "
            "Service Provider as set out in the Payment Terms clause below.\n"
            "(d) “Confidential Information” has the meaning given in the "
            "Confidentiality clause below."
        ),
    },
    {
        "clause_key": "scope_of_services",
        "display_order": 3,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Scope of Services",
        "source_text": (
            "The Service Provider shall render the following Services to the "
            "Client:\n"
            "{% for item in deliverables %}- {{ item.description }}"
            "{% if item.due_date %} (due {{ item.due_date }}){% endif %}\n"
            "{% endfor %}\n"
            "Time is not of the essence for the dates specified above unless "
            "expressly agreed in writing, save where a Deliverable is "
            "expressly designated as time-critical."
        ),
    },
    {
        "clause_key": "payment_terms",
        "display_order": 4,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Payment Terms",
        "source_text": (
            "{% if fee_structure == 'Fixed Fee' %}"
            "In consideration of the Services, the Client shall pay the "
            "Service Provider a fixed fee of {{ fee_amount }}, payable "
            "{{ payment_frequency }}."
            "{% elif fee_structure == 'Hourly Rate' %}"
            "In consideration of the Services, the Client shall pay the "
            "Service Provider at the rate of {{ fee_amount }}, invoiced "
            "{{ payment_frequency }} on the basis of time actually spent, "
            "with supporting records available to the Client on reasonable "
            "request."
            "{% elif fee_structure == 'Milestone-Based' %}"
            "In consideration of the Services, the Client shall pay the "
            "Service Provider {{ fee_amount }} upon completion and Client "
            "acceptance of each Deliverable specified in the Scope of "
            "Services clause above, invoiced {{ payment_frequency }}."
            "{% endif %}\n"
            "Any amount not paid by its due date shall accrue interest at "
            "{{ late_payment_interest_rate }} from the due date until "
            "payment, without prejudice to the Service Provider's other "
            "rights and remedies."
        ),
    },
    {
        "clause_key": "sla",
        "display_order": 5,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "include_sla", "equals": True},
        "heading": "Service Levels",
        "source_text": (
            "The Service Provider shall use commercially reasonable efforts "
            "to: (a) respond to a Client-reported issue within "
            "{{ sla_response_time_hours }} hours; and (b) resolve such issue "
            "within {{ sla_resolution_time_hours }} hours, and shall use "
            "commercially reasonable efforts to maintain "
            "{{ sla_uptime_percentage }}% uptime for any Service made "
            "available on a continuous basis. {{ sla_credit_terms }}"
        ),
    },
    {
        "clause_key": "ip_assignment",
        "display_order": 6,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Intellectual Property",
        # Found live 2026-08-01: a drafted IP clause used "Client" in one
        # sub-clause and "Party B" in another — the model drifting to a
        # generic label mid-generation despite the rest of this prompt
        # consistently saying "the Client"/"the Service Provider". The
        # recitals prompt already had an explicit guard against this
        # ("never a generic placeholder like 'Party A' or 'Party B'");
        # this prompt didn't. Added the same guard here rather than
        # relying on the surrounding "the Client"/"the Service Provider"
        # wording alone to keep the model on-terminology.
        "source_text": (
            "Draft the Intellectual Property clause for this Service "
            "Agreement (do not include a numbered heading — the caller adds "
            "one). IP ownership model selected by the client: "
            "{{ ip_ownership_model }}. Pre-existing IP / carve-out notes, if "
            "any: {{ ip_carveout_notes }}. If 'Full Assignment to Client' is "
            "selected, draft a clause assigning all right, title, and "
            "interest in the Deliverables and any work product created under "
            "this Agreement to the Client upon full payment, with the "
            "Service Provider executing further assurances as reasonably "
            "required, subject to any stated carve-outs. If 'License Grant "
            "to Client (Provider Retains Ownership)' is selected, draft a "
            "clause under which the Service Provider retains ownership of "
            "the Deliverables and grants the Client a perpetual, "
            "non-exclusive, royalty-free license to use them for the "
            "Client's internal business purposes, subject to any stated "
            "carve-outs. If 'Custom / Negotiated' is selected, draft a "
            "clause stating the ownership position is as separately "
            "negotiated between the Parties and summarised in the carve-out "
            "notes, and flag that this should be reviewed carefully by the "
            "advocate before use. In all cases, expressly preserve each "
            "Party's pre-existing intellectual property. Refer to the "
            "parties consistently as 'the Service Provider' and 'the "
            "Client' throughout every sub-clause — never 'Party A', "
            "'Party B', or any other generic label."
        ),
    },
    # Design gap fixed 2026-08-02 (Sprint 2 review, gap 3): confidentiality
    # was hardcoded one-way (Client discloses to Provider only) with a
    # hardcoded 3-year survival, regardless of the matter — but Service
    # Agreements are commonly mutual (a consultant shares its own
    # methodology/tools while the client shares business information).
    # User's call: add real intake fields (confidentiality_direction,
    # confidentiality_survival_period) rather than defer to per-matter
    # clause review, since this clause is central to the deal, not a
    # peripheral mechanic like arbitration institution/rules. Same
    # applicable_condition mechanism NDA already uses to select between
    # its mutual/one_way confidentiality_obligations variants — one clause
    # row per direction, all sharing display_order/heading, selected by
    # exact match against the new select field's value.
    {
        "clause_key": "confidentiality_mutual",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "mutual"},
        "heading": "Confidentiality",
        "source_text": (
            "Each Party acknowledges that, in the course of this Agreement, "
            "it may receive confidential and proprietary information of the "
            "other Party (“Confidential Information”) — including, without "
            "limitation, the Service Provider's methodologies, tools, and "
            "know-how, and the Client's business, technical, and commercial "
            "information. Each Party, when acting as the recipient of the "
            "other's Confidential Information, agrees that it shall: (a) "
            "hold such Confidential Information in strict confidence; (b) "
            "use it solely to perform or receive the Services, as "
            "applicable; (c) not disclose it to any third party except to "
            "its employees, officers, or professional advisors who have a "
            "genuine need to know and are bound by confidentiality "
            "obligations no less protective than those in this Agreement; "
            "and (d) protect it using at least the same degree of care it "
            "uses to protect its own confidential information of similar "
            "nature, and in no event less than reasonable care. This clause "
            "survives termination or expiry of this Agreement for a period "
            "of {{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_client",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_client"},
        "heading": "Confidentiality",
        "source_text": (
            "The Service Provider acknowledges that in the course of "
            "performing the Services it may receive confidential and "
            "proprietary information of the Client (“Confidential "
            "Information”). The Service Provider agrees that it shall: (a) "
            "hold the Client's Confidential Information in strict "
            "confidence; (b) use it solely to perform the Services; (c) not "
            "disclose it to any third party except to its employees, "
            "officers, or professional advisors who have a genuine need to "
            "know and are bound by confidentiality obligations no less "
            "protective than those in this Agreement; and (d) protect it "
            "using at least the same degree of care it uses to protect its "
            "own confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination or "
            "expiry of this Agreement for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "confidentiality_one_way_from_provider",
        "display_order": 7,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": {"field": "confidentiality_direction", "equals": "one_way_from_provider"},
        "heading": "Confidentiality",
        "source_text": (
            "The Client acknowledges that in the course of receiving the "
            "Services it may receive confidential and proprietary "
            "information of the Service Provider, including without "
            "limitation the Service Provider's methodologies, tools, and "
            "know-how (“Confidential Information”). The Client agrees that "
            "it shall: (a) hold the Service Provider's Confidential "
            "Information in strict confidence; (b) use it solely for the "
            "purpose of receiving and utilising the Services; (c) not "
            "disclose it to any third party except to its employees, "
            "officers, or professional advisors who have a genuine need to "
            "know and are bound by confidentiality obligations no less "
            "protective than those in this Agreement; and (d) protect it "
            "using at least the same degree of care it uses to protect its "
            "own confidential information of similar nature, and in no event "
            "less than reasonable care. This clause survives termination or "
            "expiry of this Agreement for a period of "
            "{{ confidentiality_survival_period }}."
        ),
    },
    {
        "clause_key": "no_license_no_obligation",
        "display_order": 8,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "No License; No Obligation",
        "source_text": (
            "Except as expressly set out in the Intellectual Property clause "
            "above, nothing in this Agreement shall be construed as granting "
            "either Party any right or license under the other Party's "
            "intellectual property. Nothing in this Agreement obligates the "
            "Client to engage the Service Provider for any services beyond "
            "those expressly agreed in the Scope of Services clause."
        ),
    },
    {
        "clause_key": "term_and_termination",
        "display_order": 9,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Term and Termination",
        "source_text": (
            "Draft the Term and Termination clause for this Service "
            "Agreement (do not include a numbered heading — the caller adds "
            "one). Term/duration specified by the client: {{ term_duration }}. "
            "Termination-for-convenience notice period: "
            "{{ termination_notice_period }}. Draft a clause stating the "
            "Agreement commences on the Effective Date and continues for the "
            "stated term, that either Party may terminate for convenience by "
            "giving the stated notice period in writing, and that either "
            "Party may terminate immediately on written notice for the other "
            "Party's uncured material breach (with a reasonable cure period "
            "of not less than 15 days) or insolvency. State that accrued "
            "payment obligations for Services rendered before termination "
            "survive termination."
        ),
    },
    {
        "clause_key": "governing_law_jurisdiction",
        "display_order": 10,
        "clause_type": "llm_fillable",
        "applicable_condition": None,
        "heading": "Governing Law and Jurisdiction",
        # Design gap flagged 2026-08-01 (Sprint 2 review): the intake form
        # has no field for arbitrator count, institution/rules (ad hoc vs.
        # institutional — MCIA, SIAC, DIAC, etc.), or language, so every
        # matter gets the same minimal sole-arbitrator/English/Act-1996
        # clause regardless of what was actually negotiated. Decision:
        # flag it for Nitesh's per-matter attention in the drafted clause
        # itself, rather than adding 3-4 more intake fields for something
        # that's genuinely deal-specific — same pattern already used below
        # for ip_assignment's "Custom / Negotiated" branch. See the
        # clause-review UX; this is the mechanism, not a new one.
        "source_text": (
            "Draft the Governing Law and Dispute Resolution clause for this "
            "Service Agreement (do not include a numbered heading — the "
            "caller adds one). Governing state: {{ state }}. Arbitration "
            "requested: {{ arbitration }}. Arbitration seat (if requested): "
            "{{ arbitration_seat }}. If arbitration is requested, draft a "
            "clause providing that disputes shall be referred to arbitration "
            "under the Arbitration and Conciliation Act, 1996, seated at the "
            "specified city, before a sole arbitrator, in the English "
            "language, with the courts at the seat having exclusive "
            "supervisory jurisdiction, and end the clause with a bracketed "
            "note: '[ADVOCATE REVIEW: confirm the number of arbitrators, "
            "whether an institution and rules apply (ad hoc vs. "
            "institutional, e.g. MCIA, SIAC, DIAC), and the language of "
            "arbitration are appropriate for this specific matter before "
            "use.]'. If arbitration is not requested, draft a clause "
            "stating this Agreement is governed by the laws of India, with "
            "the courts at the principal city of the governing state "
            "having exclusive jurisdiction."
        ),
    },
    {
        "clause_key": "miscellaneous",
        "display_order": 11,
        "clause_type": "fixed_boilerplate",
        "applicable_condition": None,
        "heading": "Miscellaneous",
        "source_text": (
            "(a) Entire Agreement: This Agreement constitutes the entire "
            "understanding between the Parties with respect to its subject "
            "matter and supersedes all prior discussions, negotiations, and "
            "agreements, whether oral or written, relating thereto.\n"
            "(b) Amendment: This Agreement may be amended only by a written "
            "instrument signed by authorised representatives of both "
            "Parties.\n"
            "(c) Severability: If any provision of this Agreement is held "
            "invalid or unenforceable, the remaining provisions shall "
            "continue in full force and effect, and the invalid provision "
            "shall be replaced by a valid provision that most closely "
            "approximates its intent.\n"
            "(d) No Waiver: No failure or delay by either Party in "
            "exercising any right under this Agreement shall operate as a "
            "waiver of that right.\n"
            "(e) Notices: All notices under this Agreement shall be in "
            "writing and delivered to the addresses of the Parties set out "
            "above, by hand, registered post, or electronic mail with "
            "confirmation of receipt.\n"
            "(f) Counterparts: This Agreement may be executed in "
            "counterparts, including by electronic signature, each of which "
            "shall be deemed an original."
        ),
    },
]


def _prune_orphaned_clauses(db, template_id: str, current_clause_keys: set[str]) -> None:
    """Delete template_clauses rows whose clause_key no longer appears in
    this script's CLAUSES list, so a rename/removal doesn't leave a
    landmine behind.

    Found live 2026-08-02, Sprint 2: renaming the Service Agreement's
    single "confidentiality" clause_key into three condition-gated
    variants (confidentiality_mutual/one_way_from_client/
    one_way_from_provider) left the OLD "confidentiality" row sitting in
    the DB — upsert(on_conflict=...) only inserts/updates rows present in
    its payload, it never removes rows that fell out of it. That old
    row's applicable_condition was None ("always applicable" per
    _clause_is_applicable), so it kept rendering as an extra, stale
    "6. Confidentiality" clause in every new draft alongside the correct
    one — confirmed live via a fresh browser E2E immediately after this
    change, both clauses visible in the same generated docx.

    Only deletes a row when it's actually safe to: no draft_clause_fills
    reference it (only possible for llm_fillable clauses, per Hard Rule 4
    auditability — a fixed_boilerplate row can never have one) and no
    clause_reviews reference it (Nitesh may have reviewed it via the
    admin clause-review screen, which isn't restricted by clause_type).
    Either reference means real audit-trail data would be lost by
    deleting, which this project's auditability requirement (CLAUDE.md
    Hard Rule 4) doesn't allow — in that case, warn loudly instead of
    silently leaving the landmine in place, so a human notices and
    decides (e.g. by hand-neutralising its applicable_condition).
    """
    existing = (
        db.table("template_clauses")
        .select("id,clause_key")
        .eq("template_id", template_id)
        .execute()
        .data
        or []
    )
    for row in existing:
        if row["clause_key"] in current_clause_keys:
            continue
        clause_id = row["id"]
        has_fills = bool(
            db.table("draft_clause_fills").select("id").eq("template_clause_id", clause_id).limit(1).execute().data
        )
        has_reviews = bool(
            db.table("clause_reviews").select("id").eq("clause_id", clause_id).limit(1).execute().data
        )
        if has_fills or has_reviews:
            print(
                f"WARNING: orphaned template_clauses row {clause_id} "
                f"(clause_key={row['clause_key']!r}) is referenced by "
                f"{'draft_clause_fills' if has_fills else ''}"
                f"{' and ' if has_fills and has_reviews else ''}"
                f"{'clause_reviews' if has_reviews else ''} — not deleted. "
                f"It will keep rendering in new drafts if its "
                f"applicable_condition can still match; review manually."
            )
            continue
        db.table("template_clauses").delete().eq("id", clause_id).execute()
        print(f"Pruned orphaned template_clauses row {clause_id} (clause_key={row['clause_key']!r})")


class ReviewedClauseConflict(Exception):
    """A re-seed would silently change the baseline text under a clause
    Nitesh has already reviewed. See _write_clauses_preserving_review
    below for the full story."""


def _write_clauses_preserving_review(db, template_id: str, clauses: list[dict]) -> None:
    """Upsert template_clauses, but NEVER silently touch current_text or
    review_status for a clause that's already been reviewed
    (review_status in ('kept', 'redrafted')) — and HALT the whole run
    (raise, no upsert at all) if this seed's source_text for such a
    clause has actually changed, rather than deciding silently either
    way.

    Found live 2026-08-02, more urgent than a Sprint 3 ticket (Nitesh's
    real review pass is about to start): every seed script's upsert
    previously wrote `"current_text": c["source_text"]` unconditionally
    for every clause, every re-seed — including ones Nitesh has already
    reviewed. Two distinct failure modes this caused, both now closed:

    1. Even a plain re-run with NO content change at all would silently
       wipe out a redraft: a 'redrafted' clause's current_text is
       Nitesh's custom text (necessarily different from source_text —
       that's what redrafting means), but the old unconditional upsert
       reset current_text = source_text on every run regardless, with
       review_status still reading 'redrafted' as if nothing happened.
    2. A genuine content edit to a clause's source_text (fixing a typo,
       improving a prompt) would silently change what a 'kept' clause
       renders, even though "kept" specifically means the *previous*
       text was approved — the new text was never actually reviewed by
       anyone, badge or no badge.

    Fix, deliberately STRICT over lenient (explicit decision, 2026-08-02
    — a re-seed that silently drops an intended content change is worse
    than one that halts and forces a human decision, matching
    _prune_orphaned_clauses's "warn/skip, don't guess" posture one step
    further): clauses with an existing reviewed row are split out of the
    normal upsert batch entirely.
      - If none of them have a source_text delta vs. what's stored, they
        get ONLY their structural fields (display_order/clause_type/
        applicable_condition/heading) refreshed via a targeted update —
        current_text, source_text, and review_status are never touched,
        so a redraft survives an unlimited number of future re-seeds
        untouched, even ones that change nothing about that clause.
      - If ANY of them DO have a source_text delta, the entire seed run
        halts before writing anything — no partial application, no
        auto-decision. The error lists every affected clause so a human
        can decide per-clause whether to revert the source_text change
        or reset review_status to 'unreviewed' and let it go through
        review again.

    Structural fields (display_order, clause_type, applicable_condition,
    heading) are refreshed even for reviewed clauses — those are
    template mechanics the advocate doesn't review clause-by-clause
    (numbering, LLM-fillable-vs-not, condition gating), not the
    reviewed *content* itself, so keeping them in sync with the current
    CLAUSES definition is safe and expected.
    """
    existing_by_key = {
        row["clause_key"]: row
        for row in (
            db.table("template_clauses")
            .select("id,clause_key,source_text,review_status")
            .eq("template_id", template_id)
            .execute()
            .data
            or []
        )
    }

    protected_keys: set[str] = set()
    conflicts: list[tuple[str, str]] = []
    for clause in clauses:
        existing = existing_by_key.get(clause["clause_key"])
        if not existing or existing["review_status"] not in ("kept", "redrafted"):
            continue
        protected_keys.add(clause["clause_key"])
        if existing["source_text"] != clause["source_text"]:
            conflicts.append((clause["clause_key"], existing["review_status"]))

    if conflicts:
        lines = "\n".join(f"  - {key} (review_status={status!r})" for key, status in conflicts)
        raise ReviewedClauseConflict(
            "Re-seed HALTED — the following clauses have already been reviewed, "
            "but this seed script's source_text for them no longer matches what's "
            "stored. Re-seeding would silently change the baseline text under an "
            "already-reviewed clause. Resolve manually before re-running: either "
            "revert the source_text change for these clauses, or explicitly reset "
            "their review_status to 'unreviewed' (they will then need review again) "
            "if the content change is intentional.\n" + lines
        )

    normal_rows = []
    for c in clauses:
        if c["clause_key"] in protected_keys:
            continue
        row = {
            "template_id": template_id,
            "clause_key": c["clause_key"],
            "display_order": c["display_order"],
            "clause_type": c["clause_type"],
            "applicable_condition": c["applicable_condition"],
            "heading": c["heading"],
            "source_text": c["source_text"],
            "current_text": c["source_text"],
        }
        # review_status is deliberately omitted for a clause that
        # already has a DB row (even a non-protected one, i.e.
        # 'unreviewed' or 'deleted') — same as the original pre-fix
        # payload, relying on Postgres upsert leaving an omitted column
        # untouched on conflict, not resetting it. Only a genuinely new
        # clause (no existing row at all) needs it explicit here, since
        # there's no column DEFAULT to fall back on when we're the ones
        # constructing the row.
        if c["clause_key"] not in existing_by_key:
            row["review_status"] = "unreviewed"
        normal_rows.append(row)
    if normal_rows:
        db.table("template_clauses").upsert(normal_rows, on_conflict="template_id,clause_key").execute()

    for c in clauses:
        if c["clause_key"] not in protected_keys:
            continue
        db.table("template_clauses").update(
            {
                "display_order": c["display_order"],
                "clause_type": c["clause_type"],
                "applicable_condition": c["applicable_condition"],
                "heading": c["heading"],
            }
        ).eq("id", existing_by_key[c["clause_key"]]["id"]).execute()

    print(
        f"Upserted {len(normal_rows)} template_clauses rows; "
        f"preserved {len(protected_keys)} already-reviewed clause(s) untouched "
        f"(current_text/review_status kept, only structural fields refreshed)"
    )


def seed() -> None:
    db = service_client()
    schema_json = json.loads(SCHEMA_PATH.read_text())

    existing = (
        db.table("templates")
        .select("id")
        .eq("name", TEMPLATE_NAME)
        .eq("category", TEMPLATE_CATEGORY)
        .execute()
        .data
    )
    if existing:
        template_id = existing[0]["id"]
        db.table("templates").update(
            {
                "schema_json": schema_json,
                "docx_path": DOCX_PATH,
                "states_supported": STATES_SUPPORTED,
                "template_key": TEMPLATE_KEY,
            }
        ).eq("id", template_id).execute()
        print(f"Updated existing template row {template_id}")
    else:
        result = (
            db.table("templates")
            .insert(
                {
                    "name": TEMPLATE_NAME,
                    "category": TEMPLATE_CATEGORY,
                    "schema_json": schema_json,
                    "docx_path": DOCX_PATH,
                    "states_supported": STATES_SUPPORTED,
                    "template_key": TEMPLATE_KEY,
                }
            )
            .execute()
        )
        template_id = result.data[0]["id"]
        print(f"Inserted template row {template_id}")

    _write_clauses_preserving_review(db, template_id, CLAUSES)
    _prune_orphaned_clauses(db, template_id, {c["clause_key"] for c in CLAUSES})


if __name__ == "__main__":
    seed()
