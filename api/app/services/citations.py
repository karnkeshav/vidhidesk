"""Citation cache: cache-first wrapper around the Indian Kanoon client.

Sprint 0 scope only: the `citations` table (TRD §4) plus a wrapper that
never re-calls the API for a case_name/court pair already cached. This is
NOT yet the full Citation Verifier state machine from TRD §3.3 (normalized
retry, nightly dead-link recheck) — that lands in Sprint 1 alongside the
statute RAG. The match heuristic here is deliberately simple.

Hard rule enforced here: a row only carries `ik_doc_id`/`ik_url` when a
match was actually found. Everything else is `status="unverified"` with
those fields null — the renderer (frontend) must treat a null ik_doc_id
as "grey, no link" no matter what, but this is the backend's first line
of defense: we never fabricate a doc id.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db import service_client
from app.services.indian_kanoon import IndianKanoonClient, IndianKanoonError, doc_url

logger = logging.getLogger("vidhidesk.citations")

_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")
_STOPWORDS = {"vs", "v", "versus", "the", "of", "and", "state", "union", "india"}


def _normalize(text: str) -> set[str]:
    cleaned = _NORMALIZE_RE.sub(" ", text.lower())
    return {w for w in cleaned.split() if w and w not in _STOPWORDS}


def _best_match(case_name: str, docs: list[dict]) -> dict | None:
    """Best-effort confidence check: does the search result title share a
    strong majority of the case name's significant words? Sprint 1 hardens
    this into the full TRD §3.3 state machine (normalized retry, etc.)."""
    target_words = _normalize(case_name)
    if not target_words or not docs:
        return None

    best: dict | None = None
    best_score = 0.0
    for doc in docs:
        title = doc.get("title", "")
        title_words = _normalize(title)
        if not title_words:
            continue
        overlap = len(target_words & title_words)
        score = overlap / len(target_words)
        if score > best_score:
            best_score = score
            best = doc

    # Require most of the case name's words to show up in the title.
    if best is not None and best_score >= 0.6:
        return best
    return None


@dataclass
class CitationRecord:
    case_name: str
    court: str | None
    status: str  # "verified" | "unverified"
    ik_doc_id: str | None
    ik_url: str | None
    decided_on: str | None
    from_cache: bool


def verify_citation(
    case_name: str,
    court: str | None = None,
    *,
    ik_client: IndianKanoonClient | None = None,
    db=None,
) -> CitationRecord:
    db = db if db is not None else service_client()
    ik_client = ik_client or IndianKanoonClient()

    query = db.table("citations").select("*").ilike("case_name", case_name)
    query = query.eq("court", court) if court else query.is_("court", "null")
    resp = query.limit(1).execute()
    if resp.data:
        row = resp.data[0]
        logger.info("citations.verify_citation cache_hit case_name=%r", case_name)
        return CitationRecord(
            case_name=row["case_name"],
            court=row.get("court"),
            status=row["status"],
            ik_doc_id=row.get("ik_doc_id"),
            ik_url=row.get("ik_url"),
            decided_on=row.get("decided_on"),
            from_cache=True,
        )

    logger.info("citations.verify_citation cache_miss case_name=%r — calling IK API", case_name)
    try:
        search_result = ik_client.search(case_name, court=court, max_pages=1)
        match = _best_match(case_name, search_result.get("docs", []))
    except IndianKanoonError as exc:
        logger.warning("citations.verify_citation IK API error: %s", exc)
        match = None

    now = datetime.now(timezone.utc).isoformat()
    if match is not None:
        doc_id = str(match.get("tid") or match.get("docid") or match.get("doc_id"))
        record = {
            "case_name": case_name,
            "court": court or match.get("docsource"),
            "status": "verified",
            "ik_doc_id": doc_id,
            "ik_url": doc_url(doc_id),
            "decided_on": match.get("publishdate"),
            "verified_at": now,
        }
    else:
        record = {
            "case_name": case_name,
            "court": court,
            "status": "unverified",
            "ik_doc_id": None,
            "ik_url": None,
            "decided_on": None,
            "verified_at": None,
        }

    db.table("citations").insert(record).execute()
    return CitationRecord(
        case_name=record["case_name"],
        court=record["court"],
        status=record["status"],
        ik_doc_id=record["ik_doc_id"],
        ik_url=record["ik_url"],
        decided_on=record["decided_on"],
        from_cache=False,
    )
