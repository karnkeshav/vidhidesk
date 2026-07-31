"""Citation Verifier — TRD §3.3 state machine (Sprint 1).

    LLM proposes case (name / citation / year)
       -> IK API /search (structured party/year/court query)
          -> high-confidence match?
               YES -> fetch full doc -> tid from that response is the
                      canonical id -> attach https://indiankanoon.org/doc/{tid}/
                      store {case, ik_id, url, court, date} in citations
               NO  -> retry with normalized query (party names only,
                      no year, no court)
                      -> still no -> render as UNVERIFIED (grey, no link)

Two things the Sprint 0 IK spike proved and this module encodes in code,
not just in a comment:

(a) ik_doc_id MUST be the `tid` from GET /doc/{id}/, not whatever id field
    a /search/ hit happens to carry (docid/tid on a search hit can diverge
    from the canonical tid for statute documents — the public
    https://indiankanoon.org/doc/{id}/ URL only resolves against tid). So
    every match — first-pass or retry-pass — is confirmed by an explicit
    get_doc() fetch before anything is persisted.

(b) Query construction is structured (party names + year + court), never
    a concept phrase. The spike showed a concept-phrase query like
    "Carriage by Road Act damages" returns noisy, unrelated hits (e.g.
    Punjab Municipal Act) — not a safe verification signal.

Hard rule enforced here: a row only ever carries ik_doc_id/ik_url when a
get_doc()-confirmed match was found. Everything else is
status="unverified" with those fields null.
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

# --- Case-name parsing -------------------------------------------------------
# The verifier needs party_a/party_b (and, ideally, a year) separately —
# it never searches on the raw proposed case name as a concept phrase.
_VS_SPLIT_RE = re.compile(r"\s+(?:vs\.?|versus|v\.|v)\s+", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")

# --- Cache-key normalization --------------------------------------------
# Real Indian Kanoon titles carry noise the cache key needs to look past:
# "vs" / "v." / "v" (IK occasionally drops the period) / "versus" are all
# the same separator; "and Anr." / "and Ors." / "& Ors" are party-count
# annotations, not part of the identity of the case; trailing ellipses
# and stray punctuation are typographic noise. Without normalizing these
# away, the same case cited two different ways fragments into two cache
# rows instead of one hit.
#
# Deliberately NOT end-anchored: a party-count suffix can follow *either*
# party, not just the last one — "Ramesh Kumar and Anr. vs Sunita Sharma
# and Ors." has one right in the middle of the string, before "vs", which
# an end-anchored ($) pattern would miss entirely.
_PARTY_COUNT_SUFFIX_RE = re.compile(
    r"\s*(?:and|&)\s+(?:anr|ors|another|others)\.?", re.IGNORECASE
)


def normalize_case_name(case_name: str) -> str:
    text = case_name.strip().rstrip(".…").strip()
    text = _PARTY_COUNT_SUFFIX_RE.sub("", text)
    text = _VS_SPLIT_RE.sub(" v ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def parse_case_name(case_name: str, neutral_citation: str | None = None) -> tuple[str, str, int | None]:
    """Best-effort split of "Party A vs Party B (1973)" into
    (party_a, party_b, year). If no "vs"/"v."/"v"/"versus" separator is
    found, party_b is "" and callers fall back to a single-party query."""
    year = None
    for source in (case_name, neutral_citation or ""):
        m = _YEAR_RE.search(source)
        if m:
            year = int(m.group(1))
            break

    # Strip a trailing "(1973)"-style year (and any citation tail after
    # it) before splitting on vs/v./versus, so the year doesn't end up
    # glued onto party_b.
    name_without_year = _YEAR_RE.sub("", case_name).strip(" ()").strip()

    parts = _VS_SPLIT_RE.split(name_without_year, maxsplit=1)
    if len(parts) == 2:
        party_a, party_b = parts[0].strip(" ,"), parts[1].strip(" ,")
    else:
        party_a, party_b = name_without_year.strip(" ,"), ""

    return party_a, party_b, year


def _normalize(text: str) -> set[str]:
    cleaned = _NORMALIZE_RE.sub(" ", text.lower())
    return {w for w in cleaned.split() if w and w not in _STOPWORDS}


def _best_match(target_text: str, docs: list[dict]) -> dict | None:
    """Does a search result's title share a strong majority of the query's
    significant words? This is the confidence gate before we ever fetch a
    doc and treat it as a real match."""
    target_words = _normalize(target_text)
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

    if best is not None and best_score >= 0.6:
        return best
    return None


def _candidate_id(doc: dict) -> str | None:
    candidate = doc.get("tid") or doc.get("docid") or doc.get("doc_id")
    return str(candidate) if candidate is not None else None


@dataclass
class CitationRecord:
    case_name: str
    neutral_citation: str | None
    court: str | None
    status: str  # "verified" | "unverified"
    ik_doc_id: str | None
    ik_url: str | None
    decided_on: str | None
    stale: bool
    from_cache: bool


def _row_to_record(row: dict, from_cache: bool) -> CitationRecord:
    return CitationRecord(
        case_name=row["case_name"],
        neutral_citation=row.get("neutral_citation"),
        court=row.get("court"),
        status=row["status"],
        ik_doc_id=row.get("ik_doc_id"),
        ik_url=row.get("ik_url"),
        decided_on=row.get("decided_on"),
        stale=bool(row.get("stale", False)),
        from_cache=from_cache,
    )


def _confirm_via_doc_fetch(
    ik_client: IndianKanoonClient, candidate: dict
) -> tuple[str, str | None, str | None] | None:
    """Fetch the full document for a search hit and pull the *canonical*
    tid off of it — never trust the search hit's own id field (Sprint 0
    spike finding (a)). Returns (tid, court, decided_on) or None if the
    fetch fails / the response has no tid."""
    candidate_id = _candidate_id(candidate)
    if candidate_id is None:
        return None
    try:
        doc = ik_client.get_doc(candidate_id)
    except IndianKanoonError as exc:
        logger.warning("citations._confirm_via_doc_fetch fetch failed for %r: %s", candidate_id, exc)
        return None

    tid = doc.get("tid")
    if tid is None:
        logger.warning(
            "citations._confirm_via_doc_fetch doc %r has no tid field — refusing to verify",
            candidate_id,
        )
        return None

    court = doc.get("docsource") or candidate.get("docsource")
    decided_on = doc.get("publishdate") or candidate.get("publishdate")
    return str(tid), court, decided_on


def verify_citation(
    case_name: str,
    neutral_citation: str | None = None,
    court: str | None = None,
    year: int | None = None,
    *,
    ik_client: IndianKanoonClient | None = None,
    db=None,
) -> CitationRecord:
    """Cache-first citation verification per TRD §3.3.

    `court`, if given, is used only as a search filter on the first pass —
    it is not required for a match and is dropped entirely on retry.
    `year`, if not given, is parsed out of `case_name`/`neutral_citation`.
    """
    db = db if db is not None else service_client()
    ik_client = ik_client or IndianKanoonClient()

    case_name_normalized = normalize_case_name(case_name)
    query = (
        db.table("citations")
        .select("*")
        .eq("case_name_normalized", case_name_normalized)
    )
    query = (
        query.eq("neutral_citation", neutral_citation)
        if neutral_citation
        else query.is_("neutral_citation", "null")
    )
    resp = query.limit(1).execute()
    if resp.data:
        logger.info("citations.verify_citation cache_hit case_name=%r", case_name)
        return _row_to_record(resp.data[0], from_cache=True)

    logger.info("citations.verify_citation cache_miss case_name=%r — calling IK API", case_name)
    party_a, party_b, parsed_year = parse_case_name(case_name, neutral_citation)
    year = year or parsed_year

    confirmed: tuple[str, str | None, str | None] | None = None

    # First pass: structured party/year query + court filter.
    first_pass_query = f"{party_a} vs {party_b}".strip() if party_b else party_a
    if year:
        first_pass_query = f"{first_pass_query} {year}"
    try:
        result = ik_client.search(first_pass_query, court=court, max_pages=1)
        match = _best_match(f"{party_a} {party_b} {year or ''}".strip(), result.get("docs", []))
        if match is not None:
            confirmed = _confirm_via_doc_fetch(ik_client, match)
    except IndianKanoonError as exc:
        logger.warning("citations.verify_citation first-pass IK API error: %s", exc)

    # Retry pass: party names only, no year, no court — only if party_b
    # is known (a single-party query is too weak a signal to bother with).
    if confirmed is None and party_b:
        retry_query = f"{party_a} {party_b}".strip()
        try:
            result = ik_client.search(retry_query, court=None, max_pages=1)
            match = _best_match(f"{party_a} {party_b}", result.get("docs", []))
            if match is not None:
                confirmed = _confirm_via_doc_fetch(ik_client, match)
        except IndianKanoonError as exc:
            logger.warning("citations.verify_citation retry-pass IK API error: %s", exc)

    now = datetime.now(timezone.utc).isoformat()
    if confirmed is not None:
        tid, matched_court, decided_on = confirmed
        record = {
            "case_name": case_name,
            "case_name_normalized": case_name_normalized,
            "neutral_citation": neutral_citation,
            "court": court or matched_court,
            "status": "verified",
            "ik_doc_id": tid,
            "ik_url": doc_url(tid),
            "decided_on": decided_on,
            "verified_at": now,
            "last_checked_at": now,
            "stale": False,
        }
    else:
        record = {
            "case_name": case_name,
            "case_name_normalized": case_name_normalized,
            "neutral_citation": neutral_citation,
            "court": court,
            "status": "unverified",
            "ik_doc_id": None,
            "ik_url": None,
            "decided_on": None,
            "verified_at": None,
            "last_checked_at": None,
            "stale": False,
        }

    inserted = db.table("citations").insert(record).execute()
    return _row_to_record(inserted.data[0] if inserted.data else record, from_cache=False)
