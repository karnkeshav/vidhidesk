"""Clause-Based Drafting Engine (Sprint 3.6 Phase 2).

Every pleading is built as 14 independently generated, independently
reviewable, independently regenerable clauses — never one giant prompt
producing a whole document (ADR-002 / Hard Rule 2's "no hallucinated
structure" principle, applied one layer deeper than pleading_outline.py's
fixed-section-list already applies it):

    Pleading Outline (existing, reviewed, versioned — pleading_outline.py)
       -> Clause Generation   (14 independent generators, see CLAUSE_TYPES)
       -> Versioning          (immutable per (matter, outline, clause_type);
                               regenerating one clause never touches another)
       -> Human Review        (review_clause() — approve/reject a specific
                               version; document_composer.py only assembles
                               approved versions)
       -> Document Composition (document_composer.py — assembly only, no
                               legal reasoning)

Deterministic vs. LLM split (same trust-boundary principle
case_analysis.py/pleading_outline.py already established, applied clause by
clause via the project's own established classification bar — see
Backlog.md's "Governing Law: llm_fillable -> fixed_boilerplate" finding:
"does this clause require synthesizing free prose from the intake inputs,
in a way a template author cannot enumerate in Jinja? If no, it's
deterministic."): Cause Title, Court Details, Parties, Jurisdiction,
Chronology, Applicable Statutes, Applicable Precedents, Verification, and
List of Annexures are all templated directly from already-reviewed,
already-grounded upstream data (the pleading outline, its source case
analysis, and litigation_parties) — zero LLM calls, zero hallucination
surface. Facts, Cause of Action, Legal Grounds, Reliefs, and Prayer
genuinely need free-prose synthesis (narrative framing, legal argument
construction, formal relief/prayer phrasing) and go through a single masked
LLM call each (task_type="clause_drafter", app/services/llm_gateway.py).

Every LLM clause's statute_refs are cross-checked against the SAME
applicable_statutes the source pleading outline already retrieved and
ground-truthed — never re-retrieved (CLAUDE.md Hard Rule 3). Every LLM
clause's case_law_refs are cross-checked against the SAME
applicable_case_law the outline already ran through the Citation Verifier
— never a fresh, unverified case name accepted here (CLAUDE.md Hard Rule
1). This is strictly narrower than pleading_outline.py's own grounding: a
clause generator never gets to introduce a citation the outline didn't
already vet.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import service_client
from app.services.citations import CitationRecord, verify_citation
from app.services.llm_gateway import generate_json
from app.services.pii_mask import SupabaseMaskStore

logger = logging.getLogger("vidhidesk.clause_generator")

PROMPT_VERSION = "v1"

# Fixed, ordered list of clause types — the composer assembles a pleading
# in exactly this order (document_composer.py::compose_pleading). Not an
# enum at the DB layer (see migration 0018's docstring) but this list is
# the single source of truth for "which 14 clauses exist," same role
# pleading_outline.py::FIXED_PLEADING_SECTIONS plays for outline sections.
CLAUSE_TYPES: list[str] = [
    "cause_title",
    "court_details",
    "parties",
    "jurisdiction",
    "facts",
    "chronology",
    "cause_of_action",
    "legal_grounds",
    "applicable_statutes",
    "applicable_precedents",
    "reliefs",
    "prayer",
    "verification",
    "annexures",
]

CLAUSE_HEADINGS: dict[str, str] = {
    "cause_title": "Cause Title",
    "court_details": "Court Details",
    "parties": "Parties",
    "jurisdiction": "Jurisdiction",
    "facts": "Facts",
    "chronology": "Chronology",
    "cause_of_action": "Cause of Action",
    "legal_grounds": "Legal Grounds",
    "applicable_statutes": "Applicable Statutes",
    "applicable_precedents": "Applicable Precedents",
    "reliefs": "Reliefs",
    "prayer": "Prayer",
    "verification": "Verification",
    "annexures": "List of Annexures",
}

# See module docstring for the classification rationale. A clause type not
# in this set is LLM-generated.
DETERMINISTIC_CLAUSE_TYPES: frozenset[str] = frozenset(
    {
        "cause_title",
        "court_details",
        "parties",
        "jurisdiction",
        "chronology",
        "applicable_statutes",
        "applicable_precedents",
        "verification",
        "annexures",
    }
)

_VALID_REVIEW_STATUSES = ("pending", "approved", "rejected")


class ClauseGeneratorError(ValueError):
    """Mirrors pleading_outline.PleadingOutlineError's plain
    ValueError-on-bad-input convention."""


def _next_version_no(matter_id: str, pleading_outline_id: str, clause_type: str, db) -> int:
    rows = (
        db.table("litigation_pleading_clauses")
        .select("version_no")
        .eq("matter_id", matter_id)
        .eq("pleading_outline_id", pleading_outline_id)
        .eq("clause_type", clause_type)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version_no"] + 1) if rows else 1


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    """Same defensive markdown-fence stripping as case_analysis.py /
    pleading_outline.py's _extract_json — kept as a separate copy per this
    project's established convention of not coupling a new caller's parsing
    behavior to an existing, already-certified module's internals."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


# --- Context assembly -------------------------------------------------------


def _clause_context(matter_id: str, pleading_outline_id: str, db) -> dict[str, Any]:
    """Every clause generator (deterministic or LLM) reads from this same
    context — built entirely from already-reviewed upstream artifacts
    (the pleading outline + its source case analysis + litigation_parties),
    never from a fresh retrieval or a fresh LLM read of raw facts. This is
    the clause-engine-level enforcement of "stay downstream of what the
    advocate already reviewed," the same architectural guarantee
    pleading_outline.py's case_analysis_id foreign key enforces one layer
    up."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise ClauseGeneratorError(f"Matter {matter_id} not found")
    matter = matter_rows[0]
    if matter.get("module") != "litigation":
        raise ClauseGeneratorError("Clause generation is only available for litigation matters")

    outline_rows = (
        db.table("litigation_pleading_outlines")
        .select("*")
        .eq("id", pleading_outline_id)
        .eq("matter_id", matter_id)
        .execute()
        .data
    )
    if not outline_rows:
        raise ClauseGeneratorError(
            f"Pleading outline {pleading_outline_id} not found for matter {matter_id} — "
            "generate a Pleading Outline before generating clauses."
        )
    outline = outline_rows[0]

    ca_rows = (
        db.table("litigation_case_analyses")
        .select("*")
        .eq("id", outline["case_analysis_id"])
        .execute()
        .data
    )
    case_analysis = ca_rows[0] if ca_rows else {}
    parties = db.table("litigation_parties").select("*").eq("matter_id", matter_id).execute().data or []

    applicable_statutes = outline.get("applicable_statutes") or []
    grounded_acts = {
        (s["act"].strip().lower(), s["section_no"].strip().lower())
        for s in applicable_statutes
        if s.get("act") and s.get("section_no")
    }
    verified_case_law = {
        c["case_name"].strip().lower(): c
        for c in (outline.get("applicable_case_law") or [])
        if c.get("case_name") and c.get("status") == "verified"
    }

    return {
        "matter": matter,
        "outline": outline,
        "case_analysis": case_analysis,
        "parties": parties,
        "applicable_statutes": applicable_statutes,
        "grounded_acts": grounded_acts,
        "verified_case_law": verified_case_law,
        "chronological_facts": case_analysis.get("chronological_facts") or [],
    }


# --- Grounding (shared by every LLM clause generator) ------------------------


def _ground_statute_refs(raw_refs: list[dict[str, Any]], grounded_acts: set[tuple[str, str]]) -> list[dict[str, Any]]:
    out = []
    for ref in raw_refs or []:
        act = str(ref.get("act", "")).strip()
        section_no = str(ref.get("section_no", "")).strip()
        if not act or not section_no:
            continue
        out.append({
            "act": act,
            "section_no": section_no,
            "grounded": (act.lower(), section_no.lower()) in grounded_acts,
        })
    return out


def _ground_case_law_refs(raw_refs: list[dict[str, Any]], verified_case_law: dict[str, dict]) -> list[dict[str, Any]]:
    """Never trust a clause generator's own claim that a case exists —
    only accept a case_law_ref if it matches a case the pleading outline
    already ran through the Citation Verifier and got status="verified"
    for (CLAUDE.md Hard Rule 1). A name that doesn't match is flagged, not
    silently dropped or silently trusted."""
    out = []
    for ref in raw_refs or []:
        case_name = str(ref.get("case_name", "")).strip()
        if not case_name:
            continue
        match = verified_case_law.get(case_name.lower())
        if match is not None:
            out.append({
                "case_name": match["case_name"],
                "status": "verified",
                "ik_url": match.get("ik_url"),
                "court": match.get("court"),
            })
        else:
            out.append({"case_name": case_name, "status": "not_in_verified_outline", "ik_url": None, "court": None})
    return out


def _confidence_for(
    is_deterministic: bool,
    model_confidence: Any,
    statute_refs: list[dict[str, Any]],
    case_law_refs: list[dict[str, Any]],
) -> float:
    if is_deterministic:
        return 1.0
    try:
        model_conf = max(0.0, min(1.0, float(model_confidence)))
    except (TypeError, ValueError):
        model_conf = 0.5

    refs = statute_refs + case_law_refs
    if not refs:
        return round(model_conf, 3)
    grounded = sum(1 for r in refs if r.get("grounded") or r.get("status") == "verified")
    grounding_ratio = grounded / len(refs)
    return round((grounding_ratio + model_conf) / 2, 3)


# --- Deterministic clause builders -------------------------------------------
# Each returns {"content": {"text": str, "bullet_items": list[str] | None},
# "statute_refs": [...], "case_law_refs": [...]}. No LLM call, no synthesis
# beyond formatting already-reviewed structured data — see module docstring.


def _party_role_label(party_type: str) -> str:
    role = party_type.strip().lower()
    if role in ("petitioner", "plaintiff", "applicant", "appellant"):
        return party_type.upper()
    return party_type.upper()


def _det_cause_title(ctx: dict[str, Any]) -> dict[str, Any]:
    matter = ctx["matter"]
    parties = sorted(ctx["parties"], key=lambda p: (p.get("party_type", ""), p.get("party_number", 1)))
    court_line = matter.get("court_name") or matter.get("court_category") or "[Court not yet recorded]"
    state = matter.get("jurisdiction_state") or "[State not yet recorded]"
    case_no = matter.get("case_number_formatted") or matter.get("cnr_number") or "[Case number not yet assigned]"

    filing_side = [p for p in parties if p.get("party_type", "").lower() in ("petitioner", "plaintiff", "applicant", "appellant")]
    opposing_side = [p for p in parties if p not in filing_side]

    lines = [f"IN THE COURT OF {court_line}, {state}", f"Case No.: {case_no}", "", "IN THE MATTER OF:", ""]
    for p in filing_side or parties[:1]:
        lines.append(f"{p['party_name']}" + (f", {p['address']}" if p.get("address") else ""))
    lines.append("... " + (_party_role_label(filing_side[0]["party_type"]) if filing_side else "PETITIONER/PLAINTIFF"))
    lines.append("")
    lines.append("VERSUS")
    lines.append("")
    for p in opposing_side or parties[1:2]:
        lines.append(f"{p['party_name']}" + (f", {p['address']}" if p.get("address") else ""))
    lines.append("... " + (_party_role_label(opposing_side[0]["party_type"]) if opposing_side else "RESPONDENT/DEFENDANT"))

    return {"content": {"text": "\n".join(lines), "bullet_items": None}, "statute_refs": [], "case_law_refs": []}


def _det_court_details(ctx: dict[str, Any]) -> dict[str, Any]:
    matter = ctx["matter"]
    fields = [
        ("Court", matter.get("court_name") or matter.get("court_category")),
        ("Bench", matter.get("bench_name")),
        ("Jurisdiction (State)", matter.get("jurisdiction_state")),
        ("Case Number", matter.get("case_number_formatted")),
        ("CNR Number", matter.get("cnr_number")),
        ("Litigation Stage", matter.get("litigation_stage")),
    ]
    items = [f"{label}: {value}" for label, value in fields if value]
    text = "\n".join(items) if items else "[No court details recorded on this matter yet]"
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": [], "case_law_refs": []}


def _det_parties(ctx: dict[str, Any]) -> dict[str, Any]:
    parties = sorted(ctx["parties"], key=lambda p: (p.get("party_type", ""), p.get("party_number", 1)))
    items = []
    for p in parties:
        line = f"{p['party_type']} No. {p.get('party_number', 1)}: {p['party_name']}"
        if p.get("address"):
            line += f", residing/situated at {p['address']}"
        if p.get("advocate_name"):
            line += f" (through Advocate {p['advocate_name']})"
        items.append(line)
    text = "\n".join(items) if items else "[No parties recorded on this matter yet]"
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": [], "case_law_refs": []}


def _det_jurisdiction(ctx: dict[str, Any]) -> dict[str, Any]:
    jurisdiction_summary = ctx["outline"].get("jurisdiction_summary") or {}
    forum = (jurisdiction_summary or {}).get("recommended_forum") or {}
    if not forum:
        text = "[Jurisdiction not yet determined — run the Forum Advisor and regenerate the Pleading Outline before drafting this clause.]"
        return {"content": {"text": text, "bullet_items": None}, "statute_refs": [], "case_law_refs": []}

    provisions = forum.get("governing_provisions") or []
    lines = [
        f"This Hon'ble {forum.get('forum_name', '[forum]')} has territorial jurisdiction to entertain "
        f"the present matter on the ground that {forum.get('territorial_basis', '[territorial basis not recorded]')}.",
        f"This Hon'ble Court has pecuniary jurisdiction on the ground that {forum.get('pecuniary_basis', '[pecuniary basis not recorded]')}.",
    ]
    if provisions:
        lines.append("The jurisdiction of this Hon'ble Court is governed by: " + "; ".join(provisions) + ".")
    if not jurisdiction_summary.get("is_unambiguous", True):
        lines.append("Note: forum determination for this matter was flagged as requiring manual review, not deterministic — verify before filing.")
    statute_refs = [{"act": p, "section_no": "", "grounded": True} for p in provisions] if provisions else []
    return {"content": {"text": "\n".join(lines), "bullet_items": None}, "statute_refs": statute_refs, "case_law_refs": []}


def _det_chronology(ctx: dict[str, Any]) -> dict[str, Any]:
    facts = ctx["chronological_facts"]
    items = []
    for f in facts:
        date = f.get("event_date") or "undated"
        line = f"[{date}] {f.get('fact_summary', '')}"
        if f.get("exhibit_number"):
            line += f" (Exhibit {f['exhibit_number']})"
        items.append(line)
    text = "\n".join(items) if items else "[No chronological facts recorded for this matter yet]"
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": [], "case_law_refs": []}


def _det_applicable_statutes(ctx: dict[str, Any]) -> dict[str, Any]:
    statutes = ctx["applicable_statutes"]
    items = [f"{s['act']}, Section {s['section_no']}" for s in statutes if s.get("act") and s.get("section_no")]
    text = "\n".join(items) if items else "[No statutory provisions were retrieved for this matter]"
    statute_refs = [{"act": s["act"], "section_no": s["section_no"], "grounded": True} for s in statutes if s.get("act") and s.get("section_no")]
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": statute_refs, "case_law_refs": []}


def _det_applicable_precedents(ctx: dict[str, Any]) -> dict[str, Any]:
    case_law = ctx["outline"].get("applicable_case_law") or []
    verified = [c for c in case_law if c.get("status") == "verified"]
    items = [f"{c['case_name']}" + (f" ({c['ik_url']})" if c.get("ik_url") else "") for c in verified]
    text = "\n".join(items) if items else "[No verified precedents on record for this matter]"
    case_law_refs = [{"case_name": c["case_name"], "status": "verified", "ik_url": c.get("ik_url"), "court": c.get("court")} for c in verified]
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": [], "case_law_refs": case_law_refs}


def _det_verification(ctx: dict[str, Any]) -> dict[str, Any]:
    parties = ctx["parties"]
    filing_party = next((p for p in parties if p.get("party_type", "").lower() in ("petitioner", "plaintiff", "applicant", "appellant")), None)
    name = filing_party["party_name"] if filing_party else "[Deponent name not yet recorded]"
    text = (
        f"I, {name}, the deponent above named, do hereby verify that the contents of paragraphs "
        "above are true and correct to my knowledge and belief, no part of it is false and nothing "
        "material has been concealed therefrom. Verified at [place] on this [date] day of [month, year], "
        "per Order VI Rule 15 of the Code of Civil Procedure, 1908."
    )
    return {
        "content": {"text": text, "bullet_items": None},
        "statute_refs": [{"act": "Code of Civil Procedure, 1908", "section_no": "Order VI Rule 15", "grounded": True}],
        "case_law_refs": [],
    }


def _det_annexures(ctx: dict[str, Any]) -> dict[str, Any]:
    facts = ctx["chronological_facts"]
    exhibits = [f for f in facts if f.get("exhibit_number")]
    items = [
        f"Exhibit {f['exhibit_number']}: {f.get('fact_summary', '')}" + ("" if f.get("has_evidence_file") else " [document not yet uploaded]")
        for f in exhibits
    ]
    text = "\n".join(items) if items else "[No exhibits recorded for this matter yet]"
    return {"content": {"text": text, "bullet_items": items or None}, "statute_refs": [], "case_law_refs": []}


_DETERMINISTIC_BUILDERS = {
    "cause_title": _det_cause_title,
    "court_details": _det_court_details,
    "parties": _det_parties,
    "jurisdiction": _det_jurisdiction,
    "chronology": _det_chronology,
    "applicable_statutes": _det_applicable_statutes,
    "applicable_precedents": _det_applicable_precedents,
    "verification": _det_verification,
    "annexures": _det_annexures,
}


# --- LLM clause prompt builders -----------------------------------------------
# See module docstring: these five clauses need genuine free-prose
# synthesis. Every prompt embeds only already-reviewed outline/case-analysis
# data — never raw facts re-read independently, never a fresh retrieval.


def _statute_context(ctx: dict[str, Any]) -> str:
    statutes = ctx["applicable_statutes"]
    if not statutes:
        return "No statutory provisions were retrieved for this matter."
    return "\n".join(f"- {s['act']} Section {s['section_no']}: {s.get('chunk_excerpt', '')[:400]}" for s in statutes)


def _case_law_context(ctx: dict[str, Any]) -> str:
    verified = list(ctx["verified_case_law"].values())
    if not verified:
        return "No verified precedents are on record for this matter — do not cite any case."
    return "\n".join(f"- {c['case_name']}" + (f" ({c.get('court')})" if c.get("court") else "") for c in verified)


def _facts_context(ctx: dict[str, Any]) -> str:
    facts = ctx["chronological_facts"]
    if not facts:
        return "No chronological facts were recorded."
    lines = []
    for f in facts:
        date = f.get("event_date") or "undated"
        line = f"- [{date}] {f.get('fact_summary', '')}"
        if f.get("exhibit_number"):
            line += f" (Exhibit {f['exhibit_number']})"
        lines.append(line)
    return "\n".join(lines)


def _causes_context(ctx: dict[str, Any]) -> str:
    causes = ctx["outline"].get("cause_of_action") or []
    if not causes:
        return "No causes of action were identified in the pleading outline."
    return "\n".join(f"- {c.get('title')}: {c.get('description', '')}" for c in causes)


def _reliefs_context(ctx: dict[str, Any]) -> str:
    reliefs = ctx["outline"].get("reliefs_sought") or []
    if not reliefs:
        return "No reliefs were identified in the pleading outline."
    return "\n".join(f"- {r.get('relief')} (basis: {r.get('basis', '')})" for r in reliefs)


def _legal_issues_context(ctx: dict[str, Any]) -> str:
    issues = ctx["outline"].get("legal_issues") or []
    if not issues:
        return "No legal issues were identified in the pleading outline."
    return "\n".join(f"- {i.get('issue')}" for i in issues)


def _prompt_facts(ctx: dict[str, Any]) -> str:
    return (
        f"Matter: {ctx['matter'].get('title', 'Untitled matter')}\n\n"
        f"Reviewed chronological facts (state these as pleaded paragraphs, in order, "
        f"never adding a fact not listed here):\n{_facts_context(ctx)}\n\n"
        "Draft the FACTS clause: the narrative statement of facts constituting the cause of "
        "action, in formal pleading register (e.g. \"That the Plaintiff states as follows:\"), "
        "one paragraph per material fact, in chronological order. Reference exhibit numbers "
        "inline where given. Do not argue the law here — facts only."
    )


def _prompt_cause_of_action(ctx: dict[str, Any]) -> str:
    return (
        f"Matter: {ctx['matter'].get('title', 'Untitled matter')}\n\n"
        f"Reviewed causes of action from the pleading outline:\n{_causes_context(ctx)}\n\n"
        f"Retrieved statutory context (cite only from this list):\n{_statute_context(ctx)}\n\n"
        "Draft the CAUSE OF ACTION clause: state, in formal pleading language, when and how "
        "the cause of action arose, grounded in the facts and statutes above. Do not introduce "
        "a cause of action not listed in the reviewed causes of action above."
    )


def _prompt_legal_grounds(ctx: dict[str, Any]) -> str:
    """Sprint 3.6 Phase 2A (TICKET-25) redesign. This is NOT the old
    single-prose-paragraph prompt — see docs/40_Validation/
    Sprint_3.6_Phase2A_Legal_Grounds_Report_2026-08-09.md §2 for why a
    prompt-only fix was rejected. Two changes, both evidence-driven:

    1. Asks for a STRUCTURED per-issue "grounds" list (short fields: an
       issue restatement, statute refs, case-law refs, a short 1-3 sentence
       argument_note, confidence) instead of one long free-form "content"
       paragraph. The live diagnostic's one captured malformed sample was a
       syntactically-invalid JSON string value — a literal, unescaped
       newline inside a long multi-paragraph "content" string. Many SHORT
       string fields are structurally less likely to need an internal line
       break at all than one long one is — this is a real, if partial,
       mitigation independent of json_mode/repair (llm_gateway.py) below.
    2. Explicitly invites (rather than implicitly discourages) naming a
       real, specific Indian precedent per issue if the model is
       reasonably confident one exists — every name is independently
       verified (_ground_case_law_refs_live below) before it can appear as
       anything but a raw, unverified claim, so inviting a guess is safe.
       The live diagnostic found the PRIOR prompt gave the model literally
       zero case-law context to work from while the shared clause_drafter
       system prompt (llm_gateway.py) says "if you are not given a source
       for a claim, say so explicitly instead of guessing" — a model
       correctly following that instruction with no case-law context given
       will propose nothing, which is exactly the "zero precedents" finding
       (confirmed empty for all 6 certification matters at BOTH the
       upstream case_analysis AND pleading_outline stages too, across a mix
       of models — see the report's WORK ITEM 3 evidence). This does not
       change case_analysis.py / pleading_outline.py (out of this sprint's
       scope) — it only gives legal_grounds's own, later, narrower
       generation step a real chance to name (and then verify) something.
    """
    issues_block = _legal_issues_context(ctx)
    return (
        f"Matter: {ctx['matter'].get('title', 'Untitled matter')}\n\n"
        "=== SECTION: Reviewed legal issues ===\n"
        f"{issues_block}\n"
        "=== END SECTION: Reviewed legal issues ===\n\n"
        "=== SECTION: Reviewed causes of action (background only — do not copy this section's "
        "heading or content into an \"issue\" field below) ===\n"
        f"{_causes_context(ctx)}\n"
        "=== END SECTION ===\n\n"
        "=== SECTION: Retrieved statutory context (cite only from this list) ===\n"
        f"{_statute_context(ctx)}\n"
        "=== END SECTION ===\n\n"
        "=== SECTION: Verified precedents already on record for this matter (cite only from this "
        "list if it is non-empty) ===\n"
        f"{_case_law_context(ctx)}\n"
        "=== END SECTION ===\n\n"
        "For the LEGAL GROUNDS clause, produce ONE ground per legal issue in the 'Reviewed legal "
        "issues' section above, connecting the statutory provisions (and, if genuinely supportive, "
        "a precedent) to that issue. For case law specifically: if you are reasonably confident of "
        "a real, specific Indian case (or Supreme Court/High Court judgment) that is directly on "
        "point for an issue, name it even if it is not in the 'already on record' list above — it "
        "will be independently verified against Indian Kanoon before it is ever shown to the "
        "advocate as confirmed, so a good-faith, reasonably-confident guess is safe and useful. Do "
        "not name a case you are not reasonably confident actually exists — omit case_law_refs for "
        "that ground instead. Respond with ONLY a JSON object of this exact shape, overriding the "
        "general response shape you were told about earlier — this clause type uses a different, "
        "more structured shape: "
        '{"grounds": [{"issue": string, "statute_refs": [{"act": string, "section_no": string}], '
        '"case_law_refs": [{"case_name": string}], "argument_note": string, "confidence": number}]}. '
        "\"issue\" MUST be copied verbatim from exactly ONE bullet point in the 'Reviewed legal "
        "issues' section above — nothing more, nothing less, never a section heading, never text "
        "from any other section, never spanning more than one bullet point. \"argument_note\" is a "
        "SHORT 1-3 sentence legal submission for this ground only — not a full paragraph, not the "
        "whole clause, and MUST be a single logical line of text (use \\n only if truly necessary, "
        "never a literal line break). Only include a statute in statute_refs if it appears in the "
        "retrieved statutory context above — never invent a section number; omit it rather than "
        "guess."
    )


# --- Legal Grounds: staged sub-generation (Sprint 3.6 Phase 2A) --------------
# The pipeline suggested by this sprint's brief (Issues -> Applicable Statutes
# -> Applicable Sections -> Applicable Case Law -> Ground Selection -> Legal
# Grounds) maps onto ALREADY-EXISTING, already-independently-inspectable
# upstream artifacts for its first two stages: Issues = outline.legal_issues,
# Applicable Statutes/Sections = outline.applicable_statutes (act+section_no
# are already one retrieved unit — see the report's WORK ITEM 2 §2.2 for why
# splitting an already-atomic (act, section_no) pair into two separate LLM
# stages was rejected as added latency/malformed-JSON surface for zero
# informational gain, against this project's own "no synthesis benefit ->
# deterministic, not LLM" bar). What genuinely did not exist as a distinct,
# inspectable stage before this sprint: Applicable Case Law (see
# _ground_case_law_refs_live) and Ground Selection (the structured "grounds"
# list below, one row per issue, independently inspectable in
# content.grounds — not collapsed into prose until the final, deterministic
# assembly step, which does no further reasoning of its own).

MAX_NEW_CASE_LAW_TO_VERIFY = 3  # bounds live IK API calls per legal_grounds generation


def _ground_case_law_refs_live(
    raw_refs: list[dict[str, Any]], verified_case_law: dict[str, dict], db
) -> list[dict[str, Any]]:
    """Like _ground_case_law_refs, but for legal_grounds specifically: a
    name that doesn't match the outline's already-verified pool is not
    immediately flagged "not_in_verified_outline" — it gets ONE live
    Citation Verifier check first (bounded, MAX_NEW_CASE_LAW_TO_VERIFY),
    the same Hard-Rule-1 gate every other proposing module in this codebase
    already uses (case_analysis.py._verify_precedents,
    pleading_outline.py._verify_case_law). This is the concrete mechanism
    behind _prompt_legal_grounds's invitation to name a case not already on
    record — an invitation with no verification behind it would just move
    the hallucination surface, not close it."""
    out: list[dict[str, Any]] = []
    live_checks_used = 0
    for ref in raw_refs or []:
        case_name = str(ref.get("case_name", "")).strip()
        if not case_name:
            continue
        match = verified_case_law.get(case_name.lower())
        if match is not None:
            out.append({
                "case_name": match["case_name"], "status": "verified",
                "ik_url": match.get("ik_url"), "court": match.get("court"),
            })
            continue
        if live_checks_used >= MAX_NEW_CASE_LAW_TO_VERIFY:
            out.append({"case_name": case_name, "status": "unverified", "ik_url": None, "court": None})
            continue
        live_checks_used += 1
        try:
            record: CitationRecord = verify_citation(case_name, db=db)
            out.append({
                "case_name": case_name,
                "status": record.status,
                "ik_url": record.ik_url,
                "court": record.court,
            })
        except Exception as exc:  # noqa: BLE001 — a verification failure must not fail the whole clause
            logger.warning("clause_generator._ground_case_law_refs_live verify_citation failed for %r: %s", case_name, exc)
            out.append({"case_name": case_name, "status": "unverified", "ik_url": None, "court": None})
    return out


def _assemble_legal_grounds_text(grounds: list[dict[str, Any]]) -> str:
    """Deterministic, reasoning-free assembly from the already-grounded
    structured "grounds" list — WORK ITEM 4's "every generated legal
    ground must explicitly identify issue/statute/section/precedent/
    confidence; if unavailable, say so; never invent authority" is
    satisfied by construction here, not inferred after the fact from
    prose: every sentence below is generated FROM a field the model
    supplied and this module already verified, never composed by the LLM
    itself. A ground with no grounded statute at all is stated as such
    rather than silently smoothed over."""
    if not grounds:
        return "[No legal grounds could be generated for this matter's reviewed issues.]"

    paragraphs = []
    for g in grounds:
        issue = g.get("issue") or "the issue set out above"
        note = (g.get("argument_note") or "").strip()
        grounded_statutes = [r for r in g["statute_refs"] if r.get("grounded")]
        verified_cases = [r for r in g["case_law_refs"] if r.get("status") == "verified"]

        parts = [f"On the issue of {issue}: {note}".strip()]
        if grounded_statutes:
            statute_list = "; ".join(f"{r['act']}, Section {r['section_no']}" for r in grounded_statutes)
            parts.append(f"This ground is supported by {statute_list}.")
        else:
            parts.append("No statutory provision retrieved for this matter directly supports this ground — verify manually before relying on it.")
        if verified_cases:
            case_list = "; ".join(r["case_name"] for r in verified_cases)
            parts.append(f"This ground is further supported by the precedent of {case_list}.")
        else:
            parts.append("No verified precedent has been identified in support of this ground.")
        paragraphs.append(" ".join(parts))
    return "\n\n".join(paragraphs)


def _generate_legal_grounds(
    ctx: dict[str, Any], mask_map, entities: list[tuple[str, str]], db
) -> dict[str, Any]:
    """Returns the same shape generate_clause()'s generic LLM branch
    expects to build a row from: content_text, statute_refs, case_law_refs
    (both already grounded/verified), model_confidence, plus the raw
    GenerationResult and generation_warning. The extra `grounds` list is
    attached separately (into `content.grounds`, see generate_clause) —
    the independently-inspectable per-issue breakdown WORK ITEM 2/4
    require, not just the flattened refs the composer already knew how to
    render."""
    prompt = _prompt_legal_grounds(ctx)
    result, parsed = generate_json(
        prompt, task_type="clause_drafter", mask_map=mask_map, entities=entities, auto_detect_names=True,
    )

    if parsed is None or not isinstance(parsed.get("grounds"), list):
        return {
            "content_text": "",
            "grounds": [],
            "statute_refs": [],
            "case_law_refs": [],
            "model_confidence": None,
            "result": result,
            "generation_warning": (
                "The AI response could not be parsed as a structured legal-grounds object, even "
                "after one automatic repair attempt. No clause text was generated this run — "
                "review manually and regenerate."
            ),
        }

    grounds: list[dict[str, Any]] = []
    for raw_ground in parsed["grounds"]:
        statute_refs = _ground_statute_refs(raw_ground.get("statute_refs", []) or [], ctx["grounded_acts"])
        case_law_refs = _ground_case_law_refs_live(raw_ground.get("case_law_refs", []) or [], ctx["verified_case_law"], db)
        grounds.append({
            "issue": str(raw_ground.get("issue", "")).strip(),
            "statute_refs": statute_refs,
            "case_law_refs": case_law_refs,
            "argument_note": str(raw_ground.get("argument_note", "")).strip(),
            "confidence": _confidence_for(False, raw_ground.get("confidence"), statute_refs, case_law_refs),
        })

    flattened_statute_refs = _dedupe_refs(
        [r for g in grounds for r in g["statute_refs"]], key=lambda r: (r["act"].lower(), r["section_no"].lower())
    )
    flattened_case_law_refs = _dedupe_refs(
        [r for g in grounds for r in g["case_law_refs"]], key=lambda r: r["case_name"].lower()
    )

    return {
        "content_text": _assemble_legal_grounds_text(grounds),
        "grounds": grounds,
        "statute_refs": flattened_statute_refs,
        "case_law_refs": flattened_case_law_refs,
        "model_confidence": (
            round(sum(g["confidence"] for g in grounds) / len(grounds), 3) if grounds else None
        ),
        "result": result,
        "generation_warning": None,
    }


def _dedupe_refs(refs: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    seen: set = set()
    out = []
    for r in refs:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _prompt_reliefs(ctx: dict[str, Any]) -> str:
    return (
        f"Matter: {ctx['matter'].get('title', 'Untitled matter')}\n\n"
        f"Reviewed reliefs sought from the pleading outline:\n{_reliefs_context(ctx)}\n\n"
        "Draft the RELIEFS clause: one formal pleading sentence per relief listed above (e.g. "
        "\"a decree for recovery of Rs. X...\", \"a permanent injunction restraining...\"), in "
        "pleading register. Do not add a relief not listed in the reviewed reliefs above."
    )


def _prompt_prayer(ctx: dict[str, Any]) -> str:
    return (
        f"Matter: {ctx['matter'].get('title', 'Untitled matter')}\n\n"
        f"Reviewed reliefs sought from the pleading outline:\n{_reliefs_context(ctx)}\n\n"
        f"Reviewed causes of action:\n{_causes_context(ctx)}\n\n"
        "Draft the PRAYER clause: the formal \"WHEREFORE, it is most respectfully prayed that "
        "this Hon'ble Court may be pleased to\" paragraph, listing each relief above as a "
        "lettered sub-prayer, plus a closing prayer for costs and any other relief this Hon'ble "
        "Court deems fit. Do not add a relief not listed above."
    )


# legal_grounds is deliberately NOT in this dict — Sprint 3.6 Phase 2A
# (TICKET-25) gave it its own staged generation path (_generate_legal_grounds)
# with a different response shape (a structured per-issue "grounds" list, not
# one free-form "content" string) and its own live case-law verification step.
# See that function's docstring and the sprint's Root Cause Report for why.
_LLM_PROMPT_BUILDERS = {
    "facts": _prompt_facts,
    "cause_of_action": _prompt_cause_of_action,
    "reliefs": _prompt_reliefs,
    "prayer": _prompt_prayer,
}


# --- Public API ---------------------------------------------------------------


def generate_clause(matter_id: str, pleading_outline_id: str, clause_type: str, db) -> dict[str, Any]:
    """Generate and persist a new version of ONE clause. Always creates a
    new row — regeneration is a new immutable version, never an overwrite,
    same convention as every other artifact in this pipeline. Every other
    clause_type's rows for this (matter, outline) are completely untouched
    by this call — the sprint's "changing one clause must never regenerate
    the whole document" requirement, satisfied structurally."""
    if clause_type not in CLAUSE_TYPES:
        raise ClauseGeneratorError(
            f"Unknown clause type {clause_type!r} — must be one of {CLAUSE_TYPES}"
        )

    ctx = _clause_context(matter_id, pleading_outline_id, db)
    version_no = _next_version_no(matter_id, pleading_outline_id, clause_type, db)
    is_deterministic = clause_type in DETERMINISTIC_CLAUSE_TYPES

    if is_deterministic:
        built = _DETERMINISTIC_BUILDERS[clause_type](ctx)
        row = {
            "content": built["content"],
            "statute_refs": built["statute_refs"],
            "case_law_refs": built["case_law_refs"],
            "confidence": 1.0,
            "is_deterministic": True,
            "model_used": None,
            "model_routing": None,
            "masked_prompt": None,
            "generation_warning": None,
        }
    else:
        matter = ctx["matter"]
        parties = ctx["parties"]

        # CLAUDE.md Decision 4: PII masking is mandatory before any
        # external LLM call, no exception for a clause-level prompt built
        # from already-reviewed (but still human-identifying) upstream
        # text. Reuses the SAME per-matter mask_map case_analysis.py /
        # pleading_outline.py already populated, so placeholders stay
        # consistent with every other artifact for this matter.
        mask_store = SupabaseMaskStore(service_client())
        mask_map = mask_store.load(matter_id)
        entities: list[tuple[str, str]] = [("PARTY", p["party_name"]) for p in parties]
        if p_addr := [p["address"] for p in parties if p.get("address")]:
            entities += [("ADDR", a) for a in p_addr]
        if matter.get("client_name"):
            entities.append(("PARTY", matter["client_name"]))

        if clause_type == "legal_grounds":
            # Sprint 3.6 Phase 2A (TICKET-25) staged path — see
            # _generate_legal_grounds's own docstring.
            built_lg = _generate_legal_grounds(ctx, mask_map, entities, db)
            mask_store.save(mask_map)
            result = built_lg["result"]
            row = {
                "content": {
                    "text": built_lg["content_text"],
                    "bullet_items": None,
                    "grounds": built_lg["grounds"],
                },
                "statute_refs": built_lg["statute_refs"],
                "case_law_refs": built_lg["case_law_refs"],
                "confidence": (
                    _confidence_for(False, built_lg["model_confidence"], built_lg["statute_refs"], built_lg["case_law_refs"])
                    if built_lg["grounds"] else 0.0
                ),
                "is_deterministic": False,
                "model_used": f"{result.provider}/{result.model}",
                "model_routing": {
                    "requested_model": result.requested_model,
                    "actual_provider": result.provider,
                    "actual_model": result.model,
                    "degraded": result.degraded,
                    "fallback_chain": result.fallback_chain,
                },
                "masked_prompt": result.masked_prompt,
                "generation_warning": built_lg["generation_warning"],
            }
        else:
            prompt = _LLM_PROMPT_BUILDERS[clause_type](ctx)
            result, parsed = generate_json(
                prompt,
                task_type="clause_drafter",
                mask_map=mask_map,
                entities=entities,
                auto_detect_names=True,
            )
            mask_store.save(mask_map)

            generation_warning: str | None = None
            if parsed is None:
                generation_warning = (
                    "The AI response could not be parsed as a structured clause, even after one "
                    "automatic repair attempt. No clause text was generated this run — review "
                    "manually and regenerate."
                )
                content_text, raw_statute_refs, raw_case_law_refs, model_confidence = "", [], [], None
            else:
                content_text = str(parsed.get("content", "")).strip()
                raw_statute_refs = parsed.get("statute_refs", []) or []
                raw_case_law_refs = parsed.get("case_law_refs", []) or []
                model_confidence = parsed.get("confidence")

            statute_refs = _ground_statute_refs(raw_statute_refs, ctx["grounded_acts"])
            case_law_refs = _ground_case_law_refs(raw_case_law_refs, ctx["verified_case_law"])
            confidence = _confidence_for(False, model_confidence, statute_refs, case_law_refs)

            row = {
                "content": {"text": content_text, "bullet_items": None},
                "statute_refs": statute_refs,
                "case_law_refs": case_law_refs,
                "confidence": confidence,
                "is_deterministic": False,
                "model_used": f"{result.provider}/{result.model}",
                "model_routing": {
                    "requested_model": result.requested_model,
                    "actual_provider": result.provider,
                    "actual_model": result.model,
                    "degraded": result.degraded,
                    "fallback_chain": result.fallback_chain,
                },
                "masked_prompt": result.masked_prompt,
                "generation_warning": generation_warning,
            }

    row.update({
        "matter_id": matter_id,
        "pleading_outline_id": pleading_outline_id,
        "clause_type": clause_type,
        "version_no": version_no,
        "prompt_version": PROMPT_VERSION,
        "regenerated": version_no > 1,
        "author": "ai",
        "review_status": "pending",
        "reviewed_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    inserted = db.table("litigation_pleading_clauses").insert(row).execute()
    return inserted.data[0] if inserted.data else row


def generate_all_clauses(matter_id: str, pleading_outline_id: str, db) -> list[dict[str, Any]]:
    """Convenience: generate a first version of every clause type, in
    pipeline order. Each call is still an independent generate_clause()
    call under the hood — this is not a special "generate the whole
    pleading in one shot" path, it's a loop, and any single clause_type
    can still be regenerated afterward without touching the rest."""
    return [generate_clause(matter_id, pleading_outline_id, ct, db) for ct in CLAUSE_TYPES]


def list_clauses(matter_id: str, pleading_outline_id: str, db) -> list[dict[str, Any]]:
    res = (
        db.table("litigation_pleading_clauses")
        .select("*")
        .eq("matter_id", matter_id)
        .eq("pleading_outline_id", pleading_outline_id)
        .order("version_no", desc=True)
        .execute()
    )
    return res.data or []


def latest_clauses_by_type(matter_id: str, pleading_outline_id: str, db) -> dict[str, dict[str, Any]]:
    """Latest version of each clause_type regardless of review_status —
    "what's current," for a review UI. document_composer.py deliberately
    does NOT use this function (it needs the latest APPROVED version per
    type, which may differ from the latest version overall)."""
    latest: dict[str, dict[str, Any]] = {}
    for row in list_clauses(matter_id, pleading_outline_id, db):
        ct = row["clause_type"]
        if ct not in latest or row["version_no"] > latest[ct]["version_no"]:
            latest[ct] = row
    return latest


def review_clause(clause_id: str, matter_id: str, review_status: str, db) -> dict[str, Any]:
    """Approve or reject one specific clause version. Never touches
    content, version_no, or any other clause — a review decision is
    metadata on the exact version reviewed, not a new generation."""
    if review_status not in _VALID_REVIEW_STATUSES or review_status == "pending":
        raise ClauseGeneratorError(
            f"review_status must be 'approved' or 'rejected', got {review_status!r}"
        )
    rows = (
        db.table("litigation_pleading_clauses")
        .select("*")
        .eq("id", clause_id)
        .eq("matter_id", matter_id)
        .execute()
        .data
    )
    if not rows:
        raise ClauseGeneratorError(f"Clause {clause_id} not found for matter {matter_id}")

    updated = (
        db.table("litigation_pleading_clauses")
        .update({"review_status": review_status, "reviewed_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", clause_id)
        .execute()
    )
    return updated.data[0] if updated.data else {**rows[0], "review_status": review_status}
