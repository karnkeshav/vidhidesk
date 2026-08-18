"""Consulting & Legal Research (Phase 1 backend).

A general-purpose "which law covers this?" engine (Product_Vision.md
Module 4): a legal question in -> applicable law(s), correct forum,
available remedies, limitation period, case law references. Built almost
entirely from existing subsystems, mirroring case_analysis.py's own
combination for Litigation's AI Case Analysis:

    Matter Engine         -> matters (module='consulting'), no new entity
    RAG Retriever          -> hybrid_retrieve() for Applicable Law
    Limitation Engine      -> caller-supplied CaseAnalysisLimitationInput
                              (computed via limitation.calculate_limitation)
    Forum Advisor          -> caller-supplied CaseAnalysisForumInput
                              (computed via forum.determine_forum)
    LLM Gateway            -> generate_json(task_type="consulting_analyst"),
                              PII-masked, structured JSON output + retry
    Citation Verifier      -> verify_citation() for every proposed case
    Version Engine         -> immutable, auto-incrementing per-matter
                              versions (same pattern as litigation_case_analyses)

Deterministic vs. LLM-generated split (the trust boundary, not an
implementation detail, per CLAUDE.md Hard Rule 3): correct_forum and
limitation_period are ONLY ever the deterministic rule-based result when
the caller supplies one (computed via the existing Forum Advisor /
Limitation Calculator, exactly the litigation_case_analyses pattern) —
the LLM's own forum/limitation guess is used only as an explicitly
flagged (deterministic: false) advisory fallback, never silently
presented as equivalent. Every applicable_law entry the model claims is
cross-checked against the retrieved statute corpus and flagged
(grounded: true/false), never silently trusted or dropped. Every
case_law_references name is run through the same Citation Verifier gate
every other module uses (CLAUDE.md Hard Rule 1) before it can appear as
anything but a raw, unverified claim.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db import service_client
from app.services.citations import CitationRecord, verify_citation
from app.services.llm_gateway import generate_json
from app.services.pii_mask import SupabaseMaskStore, mask_text
from app.services.retrieval import RetrievedChunk, hybrid_retrieve

logger = logging.getLogger("vidhidesk.consulting")

MAX_PRECEDENTS_TO_VERIFY = 5  # bound external IK API calls per analysis run
MAX_STATUTE_CONTEXT_CHUNKS = 8  # same tuned value as case_analysis.py (Sprint 3.6 TICKET-16)


class ConsultingAnalysisError(ValueError):
    """Raised for preconditions this generation cannot proceed without —
    mirrors case_analysis.py's CaseAnalysisError-on-bad-input convention
    so the router can translate it to HTTP 400 the same way."""


def _next_version_no(matter_id: str, db) -> int:
    rows = (
        db.table("consulting_analyses")
        .select("version_no")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (rows[0]["version_no"] + 1) if rows else 1


def _statute_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No statutory provisions were retrieved for this question."
    return "\n".join(
        f"- {c.act} Section {c.section_no}: {c.chunk_text[:400]}" for c in chunks
    )


def _ground_applicable_law(
    raw_entries: list[dict[str, Any]], retrieved: list[RetrievedChunk]
) -> list[dict[str, Any]]:
    """Cross-check every statute the model claims applies against what was
    actually retrieved. Never dropped, never trusted silently — flagged
    either way (CLAUDE.md Hard Rule 3). Same pattern as
    case_analysis.py::_ground_statutes_relied_upon."""
    retrieved_keys = {(c.act.strip().lower(), c.section_no.strip().lower()) for c in retrieved}
    grounded: list[dict[str, Any]] = []
    for entry in raw_entries:
        act = str(entry.get("act", "")).strip()
        section_no = str(entry.get("section_no", "")).strip()
        if not act or not section_no:
            continue
        grounded.append(
            {
                "act": act,
                "section_no": section_no,
                "relevance": str(entry.get("relevance", "")).strip(),
                "grounded": (act.lower(), section_no.lower()) in retrieved_keys,
            }
        )
    return grounded


def _verify_case_law_references(raw_precedents: list[dict[str, Any]], db) -> list[dict[str, Any]]:
    """Same bounded Citation Verifier gate as case_analysis.py::_verify_precedents."""
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
            logger.warning("consulting._verify_case_law_references verify_citation failed for %r: %s", case_name, exc)
            out.append({"case_name": case_name, "note": str(item.get("note", "")), "status": "unverified", "ik_url": None, "court": None})
    return out


def _deterministic_forum(forum_input: dict[str, Any] | None) -> dict[str, Any] | None:
    """`forum_input` is a caller-supplied CaseAnalysisForumInput.model_dump()
    (recommended_forum + is_unambiguous), itself the output of
    forum.determine_forum() computed by the caller via the existing
    POST /api/litigation/forum-advisor endpoint — determine_forum() is a
    pure function with no litigation-matter binding, so it is directly
    reusable here without duplication. Passed through verbatim, never
    re-derived or second-guessed by this module."""
    if forum_input is None:
        return None
    recommended = forum_input.get("recommended_forum") or {}
    return {
        "forum_name": recommended.get("forum_name", ""),
        "reasoning": "; ".join(recommended.get("governing_provisions", []) or []) or None,
        "deterministic": True,
        "source": "forum_advisor",
    }


def _deterministic_limitation(limitation_input: dict[str, Any] | None) -> dict[str, Any] | None:
    """Same passthrough pattern as _deterministic_forum, for
    limitation.calculate_limitation() output supplied via the existing
    POST /api/litigation/limitation-calculator endpoint (also a pure
    function, no litigation-matter binding)."""
    if limitation_input is None:
        return None
    expiry = limitation_input.get("limitation_expiry_date")
    is_barred = limitation_input.get("is_barred")
    days_remaining = limitation_input.get("days_remaining")
    status = "already barred by limitation" if is_barred else f"{days_remaining} day(s) remaining"
    return {
        "summary": f"Limitation expires {expiry} ({status}).",
        "deterministic": True,
        "source": "limitation_calculator",
        "expiry_date": expiry,
        "is_barred": is_barred,
        "days_remaining": days_remaining,
    }


def generate_consulting_analysis(
    matter_id: str,
    question: str,
    limitation: dict[str, Any] | None,
    forum: dict[str, Any] | None,
    entities: list[tuple[str, str]],
    db,
) -> dict[str, Any]:
    """Generate and persist a new Consulting analysis version for
    `matter_id`. Always creates a new consulting_analyses row —
    regeneration/follow-up is a new version, never an overwrite, same
    convention as litigation_case_analyses/draft_versions."""
    matter_rows = db.table("matters").select("*").eq("id", matter_id).execute().data
    if not matter_rows:
        raise ConsultingAnalysisError(f"Matter {matter_id} not found")
    matter = matter_rows[0]
    if matter.get("module") != "consulting":
        raise ConsultingAnalysisError("Consulting analysis is only available for consulting matters")

    # Prior turns in this matter, most recent first — used both to build
    # short conversation history for the LLM call (so a follow-up question
    # is answered in context, not as an unrelated fresh query) and as
    # this version's ordinal.
    prior = (
        db.table("consulting_analyses")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .execute()
        .data
        or []
    )

    # pii_masks has no RLS policies at all (migrations/0002_rls.sql) — it is
    # reachable only via the service-role client, same convention as
    # case_analysis.py/matters.py's SupabaseMaskStore(service_client()).
    # `db` here is the caller's RLS-scoped client and must not be reused
    # for this table.
    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)
    if matter.get("client_name"):
        entities = list(entities) + [("PARTY", matter["client_name"])]

    retrieved = hybrid_retrieve(question, top_k=MAX_STATUTE_CONTEXT_CHUNKS, db=db)

    # Follow-up context: prior question + the LLM-synthesized parts of the
    # prior turn's answer, threaded as {role, content} history — same
    # shape app/routers/matters.py::_build_history already produces for
    # the generic chat endpoint. Re-masked through the same mask_map
    # rather than persisted pre-masked, for the identical reason
    # documented there (no second column that could drift out of sync).
    history: list[dict] = []
    for row in reversed(prior[:3]):  # oldest-first, bounded same as MAX_HISTORY_MESSAGES
        history.append({"role": "user", "content": mask_text(row["question"], mask_map)})
        prior_summary = "; ".join(
            r.get("remedy", "") for r in (row.get("remedies_available") or [])
        ) or "(no remedies identified)"
        history.append({"role": "assistant", "content": mask_text(f"Remedies discussed: {prior_summary}", mask_map)})

    prompt = (
        f"<user_instruction>\n{question}\n</user_instruction>\n\n"
        f"Retrieved statutory context:\n{_statute_context(retrieved)}\n\n"
        "Produce a Consulting analysis per your instructed JSON shape."
    )

    # A total generation failure (every provider exhausted) raises
    # ProviderError, deliberately NOT caught — propagates to the router as
    # HTTP 502, same convention as case_analysis.py/matters.py.
    result, parsed = generate_json(
        prompt,
        task_type="consulting_analyst",
        mask_map=mask_map,
        entities=entities,
        auto_detect_names=True,
        history=history or None,
    )
    mask_store.save(mask_map)

    model_used = f"{result.provider}/{result.model}"
    generation_warning: str | None = None
    applicable_law: list[dict[str, Any]] = []
    remedies_available: list[dict[str, Any]] = []
    case_law_references: list[dict[str, Any]] = []
    missing_information: list[str] = []
    llm_forum: dict[str, Any] | None = None
    llm_limitation_note: str | None = None

    if parsed is None:
        generation_warning = (
            "The AI response could not be parsed as structured analysis after retry. "
            "Raw model output is not included below — treat this version as failed "
            "and try again."
        )
    else:
        applicable_law = _ground_applicable_law(parsed.get("applicable_law", []) or [], retrieved)
        remedies_available = [
            {"remedy": str(r.get("remedy", "")), "description": str(r.get("description", ""))}
            for r in (parsed.get("remedies_available", []) or [])
        ]
        case_law_references = _verify_case_law_references(parsed.get("case_law_references", []) or [], db)
        missing_information = [str(x) for x in (parsed.get("missing_information", []) or [])]
        llm_forum = parsed.get("correct_forum")
        llm_limitation_note = parsed.get("limitation_period_note")

    correct_forum = _deterministic_forum(forum) or (
        {
            "forum_name": str((llm_forum or {}).get("forum_name", "")),
            "reasoning": (llm_forum or {}).get("reasoning"),
            "deterministic": False,
            "source": "llm_advisory",
        }
        if llm_forum
        else None
    )
    limitation_period = _deterministic_limitation(limitation) or (
        {
            "summary": llm_limitation_note,
            "deterministic": False,
            "source": "llm_advisory",
            "expiry_date": None,
            "is_barred": None,
            "days_remaining": None,
        }
        if llm_limitation_note
        else None
    )

    row = {
        "matter_id": matter_id,
        "version_no": _next_version_no(matter_id, db),
        "question": question,
        "applicable_law": applicable_law,
        "correct_forum": correct_forum,
        "remedies_available": remedies_available,
        "limitation_period": limitation_period,
        "case_law_references": case_law_references,
        "missing_information": missing_information,
        "model_used": model_used,
        "masked_prompt": result.masked_prompt,
        "retrieval_sources": [
            {"act": c.act, "section_no": c.section_no, "year": c.year, "chunk_excerpt": c.chunk_text[:400], "score": c.score}
            for c in retrieved
        ],
        "generation_warning": generation_warning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    inserted = db.table("consulting_analyses").insert(row).execute()
    return inserted.data[0] if inserted.data else row


def list_consulting_analyses(matter_id: str, db) -> list[dict[str, Any]]:
    res = (
        db.table("consulting_analyses")
        .select("*")
        .eq("matter_id", matter_id)
        .order("version_no", desc=True)
        .execute()
    )
    return res.data or []
