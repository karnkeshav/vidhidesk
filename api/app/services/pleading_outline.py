"""Pleading Outline (Sprint 3.6 Phase 1/3 — AI Pleading Generation
foundation, not the drafting layer itself).

Produces a STRUCTURED PLAN for a pleading — never drafted prose, never a
document — built strictly downstream of an already-generated, already
advocate-reviewable AI Case Analysis row (see app/services/case_analysis.py):

    Case Analysis (existing, reviewed, versioned)
       -> Legal Issues              (LLM-synthesized)
       -> Applicable Statutes       (passthrough from the case analysis — never re-retrieved independently)
       -> Applicable Case Law       (LLM-proposed, Citation-Verifier-gated, same as case analysis)
       -> Cause of Action           (LLM-refined from the case analysis's own causes, re-grounded)
       -> Reliefs Sought            (LLM-synthesized)
       -> Jurisdiction              (passthrough from the case analysis)
       -> Limitation                (passthrough from the case analysis)
       -> Evidence Mapping          (LLM-synthesized, from the case analysis's chronological_facts)
       -> Pleading Outline          (LLM-synthesized, fixed section list — see FIXED_PLEADING_SECTIONS)
       -> Versioning                (immutable, auto-incrementing per matter, same pattern as case analyses)

Why "downstream of the case analysis row" is a hard architectural choice,
not a convenience: pleading planning must never silently diverge from what
the advocate already reviewed and signed off on by re-deriving its own
independent reading of the raw facts. `case_analysis_id` is a required,
non-null foreign key (migration 0015) enforcing this at the schema level,
not just in this module's own logic.

Why the outline is a plan, not a document: per this sprint's explicit
brief ("Do NOT generate complete pleadings yet") and the same
never-invent-structure principle ADR-002 applies to drafted contracts
(Hard Rule 2), the LLM fills `content_plan` text for a FIXED set of
pleading sections — derived directly from CPC Order VII Rule 1's actual
statutory particulars for a plaint, now that the corpus has real CPC
content (TICKET-16) — and never invents its own section list.
_validate_outline_is_structured() enforces in code, not just by prompt
instruction, that content_plan stays plan-shaped rather than drifting into
drafted prose.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import service_client
from app.services.citations import CitationRecord, verify_citation
from app.services.llm_gateway import GenerationResult, generate
from app.services.pii_mask import SupabaseMaskStore

logger = logging.getLogger("vidhidesk.pleading_outline")

MAX_CASE_LAW_TO_VERIFY = 5  # same bound as case_analysis.py, same reason: cap external IK API calls
# Content-plan length ceiling past which text almost certainly isn't a
# planning note anymore but drafted prose — a code-level backstop for
# "Generate only structured pleading plans," not just a prompt instruction.
MAX_CONTENT_PLAN_CHARS = 600

# Derived directly from the Code of Civil Procedure, 1908, Order VII Rule 1
# ("Particulars to be contained in plaint") — real, ingested statutory text
# as of this sprint's corpus expansion (TICKET-16), not an invented list.
# Fixed and never LLM-extended: the model fills content_plan per section,
# it never adds, removes, or renames a section.
FIXED_PLEADING_SECTIONS: list[str] = [
    "Cause Title / Parties",
    "Jurisdiction",
    "Limitation",
    "Facts Constituting the Cause of Action",
    "Cause of Action",
    "Valuation and Court Fees",
    "Reliefs Sought",
    "Verification",
]


class PleadingOutlineError(ValueError):
    """Mirrors case_analysis.CaseAnalysisError's plain ValueError-on-bad-input convention."""


def _next_version_no(matter_id: str, db) -> int:
    rows = (
        db.table("litigation_pleading_outlines")
        .select("version_no")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version_no"] + 1) if rows else 1


def _validate_outline_is_structured(outline: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Enforce "plan, not prose" in code. A content_plan that blows past a
    reasonable planning-note length is truncated with an explicit marker
    rather than silently accepted as a de facto drafted paragraph — same
    "degraded but real, never silently wrong" convention case_analysis.py
    uses for a malformed LLM response."""
    warning: str | None = None
    cleaned: list[dict[str, Any]] = []
    for item in outline:
        section = str(item.get("section", "")).strip()
        content = str(item.get("content_plan", "")).strip()
        if section not in FIXED_PLEADING_SECTIONS:
            continue  # never accept an invented section name
        if len(content) > MAX_CONTENT_PLAN_CHARS:
            content = content[:MAX_CONTENT_PLAN_CHARS].rstrip() + " […truncated — exceeded plan-length ceiling]"
            warning = (
                "One or more outline sections exceeded the planning-note length ceiling and were "
                "truncated — review manually; this may indicate the model drifted from a plan toward "
                "drafted prose."
            )
        cleaned.append({"section": section, "content_plan": content})

    # Guarantee every fixed section is present, even if the model omitted
    # one — an advocate should see "not planned yet", never a silently
    # missing section.
    present = {c["section"] for c in cleaned}
    for section in FIXED_PLEADING_SECTIONS:
        if section not in present:
            cleaned.append({"section": section, "content_plan": "(not yet planned by the model)"})
    cleaned.sort(key=lambda c: FIXED_PLEADING_SECTIONS.index(c["section"]))
    return cleaned, warning


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    """Same defensive markdown-fence stripping as case_analysis.py's
    _extract_json — kept as a separate copy rather than a shared import
    to avoid coupling this module's parsing behavior to case_analysis.py's
    (Sprint 3.6's "do not redesign architecture" instruction reads more
    safely as "don't go rewire an already-certified module's internals
    for a new caller" than as "share this one helper")."""
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


def _ground_cause_of_action_statutes(
    causes: list[dict[str, Any]], grounded_acts: set[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Same cross-check convention as case_analysis.py's
    _ground_statutes_relied_upon: never trust the model's claim that a
    cause of action relies on a given statute — only accept it if it
    matches the case analysis's own already-grounded applicable_statutes
    (never re-retrieved independently, per this module's docstring)."""
    out = []
    for cause in causes:
        refs = []
        for ref in cause.get("statutes_relied_upon", []) or []:
            act = str(ref.get("act", "")).strip()
            section_no = str(ref.get("section_no", "")).strip()
            if not act or not section_no:
                continue
            refs.append({
                "act": act,
                "section_no": section_no,
                "grounded": (act.lower(), section_no.lower()) in grounded_acts,
            })
        out.append({
            "title": cause.get("title", "Untitled"),
            "description": cause.get("description", ""),
            "supporting_facts": cause.get("supporting_facts", []) or [],
            "statutes_relied_upon": refs,
        })
    return out


def _verify_case_law(raw_precedents: list[dict[str, Any]], db) -> list[dict[str, Any]]:
    """Same Citation Verifier gate as case_analysis.py's
    _verify_precedents — CLAUDE.md Hard Rule 1, no exception for a plan
    rather than a finished document."""
    out: list[dict[str, Any]] = []
    for item in raw_precedents[:MAX_CASE_LAW_TO_VERIFY]:
        case_name = str(item.get("case_name", "")).strip()
        if not case_name:
            continue
        try:
            record: CitationRecord = verify_citation(case_name, db=db)
            out.append({
                "case_name": case_name,
                "note": str(item.get("note", "")),
                "status": record.status,
                "ik_url": record.ik_url,
                "court": record.court,
            })
        except Exception as exc:  # noqa: BLE001 — a verification failure must not fail the whole outline
            logger.warning("pleading_outline._verify_case_law verify_citation failed for %r: %s", case_name, exc)
            out.append({"case_name": case_name, "note": str(item.get("note", "")), "status": "unverified", "ik_url": None, "court": None})
    return out


def generate_pleading_outline(matter_id: str, case_analysis_id: str, db) -> dict[str, Any]:
    """Generate and persist a new Pleading Outline version for
    `matter_id`, built strictly from the referenced, already-generated
    litigation_case_analyses row. Always creates a new row — regeneration
    is an amendment, never an overwrite, same convention as
    litigation_case_analyses / draft_versions."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise PleadingOutlineError(f"Matter {matter_id} not found")
    matter = matter_rows[0]
    if matter.get("module") != "litigation":
        raise PleadingOutlineError("Pleading Outline is only available for litigation matters")

    ca_rows = (
        db.table("litigation_case_analyses")
        .select("*")
        .eq("id", case_analysis_id)
        .eq("matter_id", matter_id)
        .execute()
        .data
    )
    if not ca_rows:
        raise PleadingOutlineError(
            f"Case analysis {case_analysis_id} not found for matter {matter_id} — "
            "generate and review an AI Case Analysis before planning a pleading outline."
        )
    case_analysis = ca_rows[0]
    parties = db.table("litigation_parties").select("*").eq("matter_id", matter_id).execute().data or []

    applicable_statutes = case_analysis.get("applicable_statutes") or []
    grounded_acts = {
        (s["act"].strip().lower(), s["section_no"].strip().lower())
        for s in applicable_statutes
        if s.get("act") and s.get("section_no")
    }
    chronological_facts = case_analysis.get("chronological_facts") or []
    source_causes = case_analysis.get("possible_causes_of_action") or []

    statute_context = "\n".join(
        f"- {s['act']} Section {s['section_no']}: {s.get('chunk_excerpt', '')[:400]}"
        for s in applicable_statutes
    ) or "No statutory provisions were retrieved for this matter."

    causes_context = "\n".join(
        f"- {c.get('title')}: {c.get('description', '')}" for c in source_causes
    ) or "No causes of action were identified in the source case analysis."

    facts_context = "\n".join(
        f"- [{f.get('event_date') or 'undated'}] {f.get('fact_summary')}"
        + (f" (Exhibit {f['exhibit_number']})" if f.get("exhibit_number") else "")
        for f in chronological_facts
    ) or "No chronological facts were recorded."

    fixed_sections_list = ", ".join(f'"{s}"' for s in FIXED_PLEADING_SECTIONS)
    prompt = (
        f"Matter: {matter.get('title', 'Untitled matter')}\n\n"
        f"Reviewed AI Case Analysis — matter summary:\n{case_analysis.get('matter_summary', '')}\n\n"
        f"Reviewed causes of action:\n{causes_context}\n\n"
        f"Retrieved statutory context (do not cite anything outside this list):\n{statute_context}\n\n"
        f"Chronological facts / evidence on record:\n{facts_context}\n\n"
        "Produce a structured PLEADING PLAN per your instructed JSON shape. "
        f"pleading_outline entries must use ONLY these exact section names, one entry per section: {fixed_sections_list}. "
        "Do NOT draft the pleading itself — every content_plan value is a short planning note "
        "(what this section will need to cover and why), never drafted prose paragraphs."
    )

    # CLAUDE.md Decision 4: PII masking is mandatory before any external
    # LLM call, no exception for a downstream artifact — this prompt
    # embeds the case analysis's own (already-unmasked, human-readable)
    # matter_summary and facts, so it must be re-masked here exactly like
    # case_analysis.py does, not assumed already-safe. pii_masks has no
    # RLS policies (migrations/0002_rls.sql) — reachable only via the
    # service-role client, same convention as case_analysis.py. Reusing
    # the SAME per-matter mask_map keeps placeholders consistent with
    # whatever case_analysis.py already assigned for this matter.
    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    entities: list[tuple[str, str]] = [("PARTY", p["party_name"]) for p in parties]
    if p_addr := [p["address"] for p in parties if p.get("address")]:
        entities += [("ADDR", a) for a in p_addr]
    if matter.get("client_name"):
        entities.append(("PARTY", matter["client_name"]))

    result: GenerationResult = generate(
        prompt,
        task_type="pleading_planner",
        mask_map=mask_map,
        entities=entities,
        auto_detect_names=True,
    )
    mask_store.save(mask_map)
    model_used = f"{result.provider}/{result.model}"
    model_routing = {
        "requested_model": result.requested_model,
        "actual_provider": result.provider,
        "actual_model": result.model,
        "degraded": result.degraded,
        "fallback_chain": result.fallback_chain,
    }

    generation_warning: str | None = None
    parsed = _extract_json(result.text)
    if parsed is None:
        generation_warning = (
            "The AI response could not be parsed as a structured pleading plan. "
            "No outline sections were generated this run — review manually and regenerate."
        )
        legal_issues, cause_of_action, reliefs_sought = [], [], []
        evidence_mapping, pleading_outline_raw, case_law_raw = [], [], []
    else:
        legal_issues = [
            {"issue": str(i.get("issue", "")), "related_cause_of_action": i.get("related_cause_of_action")}
            for i in (parsed.get("legal_issues", []) or [])
        ]
        cause_of_action = _ground_cause_of_action_statutes(parsed.get("cause_of_action", []) or [], grounded_acts)
        reliefs_sought = [
            {"relief": str(r.get("relief", "")), "basis": str(r.get("basis", ""))}
            for r in (parsed.get("reliefs_sought", []) or [])
        ]
        evidence_mapping = [
            {
                "exhibit_number": e.get("exhibit_number"),
                "fact_summary": str(e.get("fact_summary", "")),
                "supports": [str(x) for x in e.get("supports", []) or []],
                "has_evidence_file": bool(e.get("has_evidence_file", False)),
            }
            for e in (parsed.get("evidence_mapping", []) or [])
        ]
        pleading_outline_raw = parsed.get("pleading_outline", []) or []
        case_law_raw = parsed.get("applicable_case_law", []) or []

    pleading_outline, structure_warning = _validate_outline_is_structured(pleading_outline_raw)
    if structure_warning:
        generation_warning = f"{generation_warning} {structure_warning}".strip() if generation_warning else structure_warning

    applicable_case_law = _verify_case_law(case_law_raw, db)

    row = {
        "matter_id": matter_id,
        "case_analysis_id": case_analysis_id,
        "version_no": _next_version_no(matter_id, db),
        "jurisdiction_summary": case_analysis.get("jurisdiction_summary"),
        "limitation_summary": case_analysis.get("limitation_summary"),
        "applicable_statutes": applicable_statutes,
        "legal_issues": legal_issues,
        "cause_of_action": cause_of_action,
        "reliefs_sought": reliefs_sought,
        "evidence_mapping": evidence_mapping,
        "pleading_outline": pleading_outline,
        "applicable_case_law": applicable_case_law,
        "model_used": model_used,
        "model_routing": model_routing,
        "masked_prompt": result.masked_prompt,
        "retrieval_sources": applicable_statutes,
        "generation_warning": generation_warning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    inserted = db.table("litigation_pleading_outlines").insert(row).execute()
    return inserted.data[0] if inserted.data else row


def list_pleading_outlines(matter_id: str, db) -> list[dict[str, Any]]:
    res = (
        db.table("litigation_pleading_outlines")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .execute()
    )
    return res.data or []
