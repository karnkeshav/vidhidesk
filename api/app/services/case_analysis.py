"""AI Case Analysis (Sprint 3.5.3 — End-to-End Advocate Experience vertical
slice). Produces a trustworthy pre-drafting review of a litigation matter —
explicitly not a pleading (ADR-011) — by combining every existing subsystem
rather than introducing new ones:

    Matter Engine        -> matters/litigation_parties/litigation_facts_evidence
    RAG Retriever         -> hybrid_retrieve() for Applicable Statutes
    Limitation Engine     -> caller-supplied CaseAnalysisLimitationInput
    Forum Advisor         -> caller-supplied CaseAnalysisForumInput
    LLM Gateway           -> generate(task_type="case_analyst"), PII-masked
    Citation Verifier     -> verify_citation() for every proposed precedent
    Version Engine        -> immutable, auto-incrementing per-matter versions
                             (same pattern as draft_versions, new table)

Deterministic vs. LLM-generated split (this is the trust boundary, not an
implementation detail): chronological_facts, jurisdiction_summary,
limitation_summary, and applicable_statutes' (act, section_no) identity are
NEVER produced by the model — they are sorted/passed-through/retrieved data.
Only the qualitative synthesis (matter_summary, missing_information,
possible_causes_of_action, potential_risks, evidence_gaps,
recommended_next_steps, possible_precedents) comes from a single masked LLM
call, and even there, every statute the model claims to rely on is
cross-checked against the retrieved corpus (grounded: true/false, never
silently dropped or silently trusted — CLAUDE.md Hard Rule 3), and every
case name it proposes is run through the same Citation Verifier gate every
other module uses (CLAUDE.md Hard Rule 1) before it can appear as anything
but a raw, unverified claim.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db import service_client
from app.services.citations import CitationRecord, verify_citation
from app.services.llm_gateway import GenerationResult, generate
from app.services.pii_mask import SupabaseMaskStore, mask_text
from app.services.retrieval import RetrievedChunk, hybrid_retrieve

logger = logging.getLogger("vidhidesk.case_analysis")

MAX_PRECEDENTS_TO_VERIFY = 5  # bound external IK API calls per analysis run
# Sprint 3.6 Phase 1/2 (TICKET-16 corpus expansion): raised from 5 to 8 after
# the expanded 12-act corpus measurably crowded out smaller, more specific
# acts at top_k=5 — the Code of Civil Procedure alone is ~48% of all chunks
# by volume, so a query's top-5 by score sometimes fills entirely with
# generic CPC procedure over a smaller, more on-topic act (e.g. Specific
# Relief Act, Indian Easements Act). Measured directly against the 26 real
# Sprint 3.5.6 certification matters: recall@5 (correct act present) was
# 62%, recall@8 was 73% on the identical queries — see
# docs/40_Validation/Sprint_3.6_Phase1_Foundation_Report_2026-08-09.md §2.
MAX_STATUTE_CONTEXT_CHUNKS = 8


class CaseAnalysisError(ValueError):
    """Raised for preconditions this generation cannot proceed without —
    mirrors limitation.py/forum.py's plain ValueError-on-bad-input
    convention so the router can translate it to HTTP 400 the same way."""


def _next_version_no(matter_id: str, db) -> int:
    rows = (
        db.table("litigation_case_analyses")
        .select("version_no")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version_no"] + 1) if rows else 1


def _sort_key(fact: dict[str, Any]) -> tuple[int, str]:
    # Undated facts sort last, not first — an unknown date is worse
    # information than any known date, and burying it at the top of a
    # chronology an advocate skims would misrepresent it as early-occurring.
    date = fact.get("event_date")
    return (1, "") if not date else (0, date)


def _chronological_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(facts, key=_sort_key)
    return [
        {
            "event_date": f.get("event_date"),
            "fact_summary": f["fact_summary"],
            "exhibit_number": f.get("exhibit_number"),
            "has_evidence_file": bool(f.get("file_url")),
        }
        for f in ordered
    ]


def _deterministic_evidence_gaps(facts: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for f in facts:
        label = f.get("exhibit_number") or (f["fact_summary"][:60] + "...")
        if f.get("exhibit_number") and not f.get("file_url"):
            gaps.append(f"Exhibit {f['exhibit_number']} is referenced but no file has been uploaded yet.")
        elif not f.get("exhibit_number") and not f.get("file_url"):
            gaps.append(f"Fact \"{label}\" has no attached exhibit or supporting document.")
    return gaps


def _deterministic_missing_information(
    matter: dict[str, Any],
    parties: list[dict[str, Any]],
    hearings: list[dict[str, Any]],
    limitation: Any | None,
    forum: Any | None,
) -> list[str]:
    missing: list[str] = []
    if not any(p.get("party_type", "").lower() in ("respondent", "defendant") for p in parties):
        missing.append("No opposing party (Respondent/Defendant) is on record for this matter.")
    if not matter.get("jurisdiction_state"):
        missing.append("Matter has no jurisdiction state recorded.")
    if not matter.get("case_number_formatted") and not matter.get("cnr_number"):
        missing.append("No case number or CNR has been recorded yet — matter may be pre-filing.")
    if not hearings:
        missing.append("No hearing dates logged — docket may not be current.")
    if limitation is None:
        missing.append("Limitation has not been calculated for this matter — run the Limitation Calculator before relying on this analysis for filing timelines.")
    if forum is None:
        missing.append("Forum and jurisdiction have not been determined for this matter — run the Forum Advisor before relying on this analysis for venue.")
    return missing


def _facts_narrative(matter: dict[str, Any], parties: list[dict[str, Any]], facts: list[dict[str, Any]]) -> str:
    lines = [f"Matter: {matter.get('title', 'Untitled matter')}"]
    if matter.get("court_category"):
        lines.append(f"Forum on record: {matter['court_category']} ({matter.get('jurisdiction_state', 'India')})")
    for p in parties:
        lines.append(f"{p['party_type']} #{p['party_number']}: {p['party_name']}")
    lines.append("Chronological facts:")
    for f in sorted(facts, key=_sort_key):
        date = f.get("event_date") or "undated"
        lines.append(f"- [{date}] {f['fact_summary']}")
    return "\n".join(lines)


def _statute_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No statutory provisions were retrieved for these facts."
    return "\n".join(
        f"- {c.act} Section {c.section_no}: {c.chunk_text[:400]}" for c in chunks
    )


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    """The model is instructed to return bare JSON, but strip markdown
    fences defensively (every provider occasionally wraps output in
    ```json ... ``` despite the instruction) before parsing. Returns None
    rather than raising — a malformed response is a degraded result, not a
    crash; see generate_case_analysis's fallback handling."""
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


def _ground_statutes_relied_upon(
    causes: list[dict[str, Any]], retrieved: list[RetrievedChunk]
) -> list[dict[str, Any]]:
    """Cross-check every statute the model claims a cause of action relies
    on against what was actually retrieved. Never dropped, never trusted
    silently — flagged either way (CLAUDE.md Hard Rule 3)."""
    retrieved_keys = {(c.act.strip().lower(), c.section_no.strip().lower()) for c in retrieved}
    grounded_causes = []
    for cause in causes:
        refs = []
        for ref in cause.get("statutes_relied_upon", []) or []:
            act = str(ref.get("act", "")).strip()
            section_no = str(ref.get("section_no", "")).strip()
            if not act or not section_no:
                continue
            refs.append(
                {
                    "act": act,
                    "section_no": section_no,
                    "grounded": (act.lower(), section_no.lower()) in retrieved_keys,
                }
            )
        grounded_causes.append(
            {
                "title": cause.get("title", "Untitled"),
                "description": cause.get("description", ""),
                "supporting_facts": cause.get("supporting_facts", []) or [],
                "statutes_relied_upon": refs,
            }
        )
    return grounded_causes


def _verify_precedents(raw_precedents: list[dict[str, Any]], db) -> list[dict[str, Any]]:
    """Every proposed case name goes through the same Citation Verifier
    gate as any other module — CLAUDE.md Hard Rule 1, no exceptions for
    "just an analysis." Bounded to avoid an unbounded burst of external IK
    API calls from one generation."""
    out: list[dict[str, Any]] = []
    for item in raw_precedents[:MAX_PRECEDENTS_TO_VERIFY]:
        case_name = str(item.get("case_name", "")).strip()
        if not case_name:
            continue
        try:
            record: CitationRecord = verify_citation(case_name, db=db)
            out.append(
                {
                    "case_name": case_name,
                    "note": str(item.get("note", "")),
                    "status": record.status,
                    "ik_url": record.ik_url,
                    "court": record.court,
                }
            )
        except Exception as exc:  # noqa: BLE001 — a verification failure must not fail the whole analysis
            logger.warning("case_analysis._verify_precedents verify_citation failed for %r: %s", case_name, exc)
            out.append({"case_name": case_name, "note": str(item.get("note", "")), "status": "unverified", "ik_url": None, "court": None})
    return out


def generate_case_analysis(
    matter_id: str,
    limitation: dict[str, Any] | None,
    forum: dict[str, Any] | None,
    db,
) -> dict[str, Any]:
    """Generate and persist a new AI Case Analysis version for `matter_id`.
    Always creates a new litigation_case_analyses row — regeneration is an
    amendment, not an overwrite, same convention as draft_versions."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise CaseAnalysisError(f"Matter {matter_id} not found")
    matter = matter_rows[0]
    if matter.get("module") != "litigation":
        raise CaseAnalysisError("AI Case Analysis is only available for litigation matters")

    parties = db.table("litigation_parties").select("*").eq("matter_id", matter_id).execute().data or []
    facts = db.table("litigation_facts_evidence").select("*").eq("matter_id", matter_id).execute().data or []
    hearings = db.table("litigation_hearings").select("*").eq("matter_id", matter_id).execute().data or []

    if not parties:
        raise CaseAnalysisError("Add at least one party before generating a case analysis.")
    if not facts:
        raise CaseAnalysisError("Record at least one fact before generating a case analysis.")

    # --- Deterministic sections -------------------------------------------
    chronological_facts = _chronological_facts(facts)
    deterministic_evidence_gaps = _deterministic_evidence_gaps(facts)
    deterministic_missing_info = _deterministic_missing_information(matter, parties, hearings, limitation, forum)

    narrative = _facts_narrative(matter, parties, facts)
    retrieved = hybrid_retrieve(narrative, top_k=MAX_STATUTE_CONTEXT_CHUNKS, db=db)
    applicable_statutes = [
        {"act": c.act, "section_no": c.section_no, "year": c.year, "chunk_excerpt": c.chunk_text[:400], "score": c.score}
        for c in retrieved
    ]

    # --- LLM-synthesized section --------------------------------------------
    # pii_masks has no RLS policies at all (migrations/0002_rls.sql) — it is
    # reachable only via the service-role client, same convention as
    # matters.py's SupabaseMaskStore(service_client()). `db` here is the
    # caller's RLS-scoped user client and must not be reused for this table.
    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    entities: list[tuple[str, str]] = [("PARTY", p["party_name"]) for p in parties]
    if p_addr := [p["address"] for p in parties if p.get("address")]:
        entities += [("ADDR", a) for a in p_addr]
    if matter.get("client_name"):
        entities.append(("PARTY", matter["client_name"]))

    prompt = (
        f"{narrative}\n\n"
        f"Retrieved statutory context:\n{_statute_context(retrieved)}\n\n"
        "Produce a pre-drafting case analysis per your instructed JSON shape. "
        "Do not draft a pleading — only analyze."
    )

    generation_warning: str | None = None
    llm_result: dict[str, Any] = {
        "matter_summary": "",
        "missing_information": [],
        "possible_causes_of_action": [],
        "potential_risks": [],
        "evidence_gaps": [],
        "recommended_next_steps": [],
        "possible_precedents": [],
    }
    model_used: str | None = None
    model_routing: dict[str, Any] | None = None
    masked_prompt: str | None = None

    # A total generation failure (every provider in the failover chain
    # exhausted) raises ProviderError here and is deliberately NOT caught —
    # it propagates to the router, which translates it to HTTP 502, same
    # convention as matters.py's send_message. That is a different failure
    # mode from a malformed-but-present response (handled below as a
    # degraded-but-real result, not an error) and the two must not be
    # conflated: a total failure means nothing to show the advocate at
    # all; a parse failure means something to show, just not structured.
    result: GenerationResult = generate(
        prompt,
        task_type="case_analyst",
        mask_map=mask_map,
        entities=entities,
        auto_detect_names=True,
    )
    mask_store.save(mask_map)
    model_used = f"{result.provider}/{result.model}"
    masked_prompt = result.masked_prompt
    # Sprint 3.6 Phase 4 (TICKET-20/21): record actual model used and
    # expose fallback decisions explicitly, not just as a bare
    # provider/model string an advocate would have no way to interpret as
    # "this is a lower tier than the architecture leads with."
    model_routing = {
        "requested_model": result.requested_model,
        "actual_provider": result.provider,
        "actual_model": result.model,
        "degraded": result.degraded,
        "fallback_chain": result.fallback_chain,
    }

    parsed = _extract_json(result.text)
    if parsed is None:
        generation_warning = (
            "The AI response could not be parsed as structured analysis. "
            "Raw model output has been placed in the matter summary below — "
            "review manually before relying on it."
        )
        llm_result["matter_summary"] = result.text.strip()[:4000]
    else:
        llm_result["matter_summary"] = str(parsed.get("matter_summary", "")).strip()
        llm_result["missing_information"] = [str(x) for x in parsed.get("missing_information", []) or []]
        llm_result["possible_causes_of_action"] = _ground_statutes_relied_upon(
            parsed.get("possible_causes_of_action", []) or [], retrieved
        )
        llm_result["potential_risks"] = [
            {
                "risk": str(r.get("risk", "")),
                "severity": str(r.get("severity", "Medium")),
                "mitigation": r.get("mitigation"),
            }
            for r in (parsed.get("potential_risks", []) or [])
        ]
        llm_result["evidence_gaps"] = [str(x) for x in parsed.get("evidence_gaps", []) or []]
        llm_result["recommended_next_steps"] = [str(x) for x in parsed.get("recommended_next_steps", []) or []]
        llm_result["possible_precedents"] = _verify_precedents(parsed.get("possible_precedents", []) or [], db)

    # --- Assemble + persist --------------------------------------------------
    row = {
        "matter_id": matter_id,
        "version_no": _next_version_no(matter_id, db),
        "chronological_facts": chronological_facts,
        "jurisdiction_summary": forum,
        "limitation_summary": limitation,
        "applicable_statutes": applicable_statutes,
        "matter_summary": llm_result["matter_summary"],
        "missing_information": deterministic_missing_info + llm_result["missing_information"],
        "possible_causes_of_action": llm_result["possible_causes_of_action"],
        "potential_risks": llm_result["potential_risks"],
        "evidence_gaps": deterministic_evidence_gaps + llm_result["evidence_gaps"],
        "recommended_next_steps": llm_result["recommended_next_steps"],
        "possible_precedents": llm_result["possible_precedents"],
        "model_used": model_used,
        "model_routing": model_routing,
        "masked_prompt": masked_prompt,
        "retrieval_sources": applicable_statutes,
        "generation_warning": generation_warning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    inserted = db.table("litigation_case_analyses").insert(row).execute()
    return inserted.data[0] if inserted.data else row


def list_case_analyses(matter_id: str, db) -> list[dict[str, Any]]:
    res = (
        db.table("litigation_case_analyses")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .execute()
    )
    return res.data or []
