"""AI Hearing / Argument Brief generation (Litigation Intelligence +
eCourts, 27 Aug 2026). Reuses every existing subsystem the same way
case_analysis.py does -- no new AI infrastructure introduced:

    Matter Bundle  -> app/services/matter_bundle.py (pure DB reads)
    LLM Gateway    -> generate(task_type="hearing_analyst"), PII-masked
    PII Masker     -> same SupabaseMaskStore(service_client()) pattern

Structure enforced in code (CLAUDE.md Hard Rule 2 applied to briefs, not
just contracts: the LLM fills content, it never invents the document's
shape): every persisted brief has exactly six sections --
case_record, supported_arguments, risk_highlights, ai_suggested_points,
checklist, information_gaps -- and the first three are checked for a
source_refs citation on every entry (a missing one is dropped, not
silently kept, so a brief can never present an unsourced claim as record
fact).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import service_client
from app.services.llm_gateway import GenerationResult, generate
from app.services.matter_bundle import MatterBundle, MatterBundleError, assemble_matter_bundle
from app.services.notifications import notify_brief_ready
from app.services.pii_mask import SupabaseMaskStore

logger = logging.getLogger("vidhidesk.hearing_brief")

REQUIRED_SECTIONS = ("case_record", "supported_arguments", "risk_highlights", "ai_suggested_points", "checklist", "information_gaps")


class HearingBriefError(ValueError):
    """Mirrors case_analysis.py's CaseAnalysisError convention -- the
    router translates this to HTTP 400."""


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    """Identical defensive parsing to case_analysis.py::_extract_json --
    duplicated rather than imported to keep each module's trust boundary
    self-contained and independently readable; both are 8-line, unlikely-
    to-drift utility functions, not a shared abstraction worth the
    cross-module coupling."""
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


def _validate_brief_sections(parsed: dict[str, Any]) -> dict[str, Any]:
    """Enforces the six-section structure and drops any case_record/
    supported_arguments/risk_highlights entry missing a source_refs
    citation -- an unsourced entry in those three sections would be
    indistinguishable from a grounded one to a reader, which is exactly
    the failure mode Hard Rule 1/3 exist to prevent elsewhere in this
    codebase."""
    out: dict[str, Any] = {s: [] for s in REQUIRED_SECTIONS}

    for entry in parsed.get("case_record", []) or []:
        refs = [str(r) for r in (entry.get("source_refs") or []) if str(r).strip()]
        if not refs:
            continue
        out["case_record"].append(
            {"heading": str(entry.get("heading", "")), "content": str(entry.get("content", "")), "source_refs": refs}
        )

    for entry in parsed.get("supported_arguments", []) or []:
        refs = [str(r) for r in (entry.get("source_refs") or []) if str(r).strip()]
        if not refs:
            continue
        out["supported_arguments"].append({"argument": str(entry.get("argument", "")), "source_refs": refs})

    # Same provenance gate as case_record/supported_arguments above -- a
    # risk claim with no source_refs is dropped, never persisted as if it
    # were grounded (this is the Iter 5 fix for the Iter 4 finding that
    # "Risk Highlights" had no backing field at all).
    for entry in parsed.get("risk_highlights", []) or []:
        refs = [str(r) for r in (entry.get("source_refs") or []) if str(r).strip()]
        if not refs:
            continue
        out["risk_highlights"].append({"text": str(entry.get("text", "")), "source_refs": refs})

    out["ai_suggested_points"] = [str(x) for x in (parsed.get("ai_suggested_points") or [])]
    out["checklist"] = [str(x) for x in (parsed.get("checklist") or [])]
    out["information_gaps"] = [str(x) for x in (parsed.get("information_gaps") or [])]

    return out


def _next_version_no(hearing_id: str, db) -> int:
    rows = (
        db.table("hearing_briefs")
        .select("version")
        .eq("hearing_id", hearing_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version"] + 1) if rows else 1


def generate_hearing_brief(matter_id: str, hearing_id: str, db) -> dict[str, Any]:
    """Generate and persist a new Hearing Brief version for `hearing_id`.
    Always a new hearing_briefs row (immutable-per-version, same
    convention as litigation_case_analyses/draft_versions) -- status
    starts 'draft' and NEVER auto-advances; see review_hearing_brief()."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise HearingBriefError(f"Matter {matter_id} not found")
    matter = matter_rows[0]
    if matter.get("module") != "litigation":
        raise HearingBriefError("Hearing briefs are only available for litigation matters")

    hearing_rows = db.table("hearings").select("*").eq("id", hearing_id).eq("matter_id", matter_id).execute().data
    if not hearing_rows:
        raise HearingBriefError(f"Hearing {hearing_id} not found on matter {matter_id}")

    bundle: MatterBundle = assemble_matter_bundle(matter_id, db, exclude_hearing_id=hearing_id)

    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    entities: list[tuple[str, str]] = [("PARTY", p["party_name"]) for p in bundle.parties]
    if addrs := [p["address"] for p in bundle.parties if p.get("address")]:
        entities += [("ADDR", a) for a in addrs]

    prompt = (
        f"{bundle.as_prompt_text()}\n\n"
        "Produce a hearing/argument brief per your instructed JSON shape, grounded ONLY "
        "in the bundle above."
    )

    generation_warning: str | None = None
    result: GenerationResult = generate(
        prompt,
        task_type="hearing_analyst",
        mask_map=mask_map,
        entities=entities,
        auto_detect_names=True,
    )
    mask_store.save(mask_map)
    model_used = f"{result.provider}/{result.model}"

    parsed = _extract_json(result.text)
    if parsed is None:
        generation_warning = (
            "The AI response could not be parsed as a structured brief. Raw model output "
            "has been placed in case_record below — review manually before relying on it."
        )
        brief_content = {s: [] for s in REQUIRED_SECTIONS}
        brief_content["case_record"] = [
            {"heading": "Unparsed model output", "content": result.text.strip()[:4000], "source_refs": ["raw model output"]}
        ]
    else:
        brief_content = _validate_brief_sections(parsed)

    row = {
        "organization_id": matter["organization_id"],
        "matter_id": matter_id,
        "hearing_id": hearing_id,
        "version": _next_version_no(hearing_id, db),
        "status": "draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": model_used,
        "source_snapshot": {
            "party_ids": [p["id"] for p in bundle.parties],
            "fact_ids": [f["id"] for f in bundle.evidence],
            "pleading_draft_ids": [p["id"] for p in bundle.pleadings],
            "prior_hearing_ids": [h["id"] for h in bundle.hearings],
            "order_ids": [o["id"] for o in bundle.orders],
            "research_ids": [r["id"] for r in bundle.research],
        },
        "brief_content": brief_content,
    }
    if generation_warning:
        row["brief_content"] = {**brief_content, "generation_warning": generation_warning}

    inserted = db.table("hearing_briefs").insert(row).execute()
    brief = inserted.data[0] if inserted.data else row

    # notifications has no authenticated-role INSERT policy (0025) --
    # service_client() only, same as every other backend-authored table.
    notify_brief_ready(
        service_client(),
        organization_id=matter["organization_id"],
        user_id=matter["user_id"],
        matter_id=matter_id,
        matter_title=matter.get("title", "Matter"),
        hearing_date=str(hearing_rows[0].get("hearing_at", ""))[:10],
        brief_id=brief["id"],
        version=brief["version"],
    )

    return brief


def list_hearing_briefs(hearing_id: str, db) -> list[dict[str, Any]]:
    res = db.table("hearing_briefs").select("*").eq("hearing_id", hearing_id).order("version", desc=True).execute()
    return res.data or []


def review_hearing_brief(brief_id: str, *, status: str, lawyer_edits: dict[str, Any] | None, db) -> dict[str, Any]:
    """Lawyer review workflow (spec Section 11): draft -> reviewed ->
    approved_for_hearing. Never skips a step backward automatically --
    the caller (router) is responsible for only offering valid
    transitions; this function just persists whichever one it's given."""
    if status not in ("reviewed", "approved_for_hearing"):
        raise HearingBriefError(f"Invalid review status: {status}")

    update: dict[str, Any] = {"status": status}
    if lawyer_edits is not None:
        update["lawyer_edits"] = lawyer_edits
    now = datetime.now(timezone.utc).isoformat()
    if status == "reviewed":
        update["reviewed_at"] = now
    elif status == "approved_for_hearing":
        update["approved_at"] = now

    updated = db.table("hearing_briefs").update(update).eq("id", brief_id).execute()
    if not updated.data:
        raise HearingBriefError(f"Hearing brief {brief_id} not found")
    return updated.data[0]
