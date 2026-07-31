"""Hybrid statute retrieval (TRD §3.2): vector similarity + keyword
search (act_name/section_no metadata + full-text over chunk bodies),
merged and re-ranked.

Full-text search (migration 0006) was added after the golden test set
showed the original metadata-only keyword search's known gap in
practice: GT-02 and GT-05 both used informal fact-pattern language
("where should client file", "carrier refused to accept") that never
names the act or cites a section number, so only vector search carried
them — and bge-small alone didn't bridge informal-to-statutory language
reliably enough to surface the correct section in the top 3.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from app.db import service_client

# BAAI/bge-small-en-v1.5's own model card: queries get this instruction
# prefix, documents/passages get none (see scripts/ingest_statutes.py's
# embed_chunks — opposite of e5-style symmetric "query: "/"passage: "
# prefixes, don't carry that convention over by habit).
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@functools.lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("BAAI/bge-small-en-v1.5")


def embed_query(text: str) -> list[float]:
    model = _get_embedding_model()
    embedding = model.encode([QUERY_INSTRUCTION + text], normalize_embeddings=True)
    return embedding[0].tolist()


@dataclass
class RetrievedChunk:
    act: str
    section_no: str
    year: int | None
    chunk_text: str
    score: float


_SECTION_REF_RE = re.compile(r"(?:section|sec\.?|§)\s*(\d{1,3}[A-Z]?)", re.IGNORECASE)
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is",
    "was", "were", "with", "by", "from", "as", "that", "this", "under",
}


def _keyword_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def vector_search(query_embedding: list[float], top_k: int, db=None) -> list[RetrievedChunk]:
    db = db if db is not None else service_client()
    rows = (
        db.rpc("match_statute_chunks", {"query_embedding": query_embedding, "match_count": top_k})
        .execute()
        .data
        or []
    )
    return [
        RetrievedChunk(
            act=r["act"],
            section_no=r["section_no"],
            year=r.get("year"),
            chunk_text=r["text"],
            score=float(r["similarity"]),
        )
        for r in rows
    ]


def keyword_search(facts: str, top_k: int, db=None) -> list[RetrievedChunk]:
    """Keyword search against act_name + section_no metadata, per spec.

    An explicit section reference in `facts` ("Section 18") is a very
    strong, near-unambiguous signal and scores highest; a fuzzy word
    overlap between `facts` and an act's name is a weaker secondary
    signal. Corpus-wide metadata fetch (act, section_no, year, text —
    no embedding column) is cheap at Phase 1's scale (low thousands of
    rows across ~15 acts per TRD Appendix B); revisit if that stops
    being true.
    """
    db = db if db is not None else service_client()
    section_refs = {m.group(1) for m in _SECTION_REF_RE.finditer(facts)}
    tokens = _keyword_tokens(facts)

    rows = db.table("statute_chunks").select("act,section_no,year,text").execute().data or []

    scored: list[tuple[float, dict]] = []
    for row in rows:
        score = 0.0
        if row["section_no"] in section_refs:
            score += 1.0
        act_tokens = _keyword_tokens(row["act"])
        if act_tokens:
            overlap = len(tokens & act_tokens)
            score += 0.5 * (overlap / len(act_tokens))
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        RetrievedChunk(
            act=row["act"], section_no=row["section_no"], year=row.get("year"),
            chunk_text=row["text"], score=score,
        )
        for score, row in scored[:top_k]
    ]


# Weight cap for the full-text signal's contribution to a merged score —
# matches the act-name-overlap weight in keyword_search() above, since
# both are "softer" lexical signals than an exact section-number match
# (weight 1.0). Postgres's raw ts_rank isn't on a fixed [0,1] scale (it
# depends on term frequency/document length), so it's normalized against
# the top hit in each result batch before this weight is applied — the
# best full-text match for a given query always contributes exactly
# FULLTEXT_WEIGHT, not whatever ts_rank's absolute units happened to be.
FULLTEXT_WEIGHT = 0.5


def fulltext_search(facts: str, top_k: int, db=None) -> list[RetrievedChunk]:
    """Full-text search over chunk bodies (not just act/section metadata)
    via Postgres websearch_to_tsquery, ranked by ts_rank. This is what
    lets an informal fact pattern that never names the act or cites a
    section ("carrier refused to accept the consignment") still surface
    a lexical match against the statute's own wording ("duty to accept
    goods"), which act-name/section-number matching alone cannot do.

    The raw fact pattern is NOT passed to websearch_to_tsquery directly —
    a multi-sentence fact pattern runs 15-30+ words, and
    websearch_to_tsquery implicitly ANDs every non-stopword term
    together. Requiring every single content word in a whole fact
    pattern to appear in one ~200-character statute chunk is
    over-constrained; in practice it matches nothing, which would defeat
    the entire point of adding this signal. Extracting just the content
    words first — reusing keyword_search()'s own _keyword_tokens()
    tokenizer, the same stopword filtering already used for act-name
    overlap above — keeps the AND-query short enough to actually match
    real statute text.

    Chose hardcoded stopword filtering over spaCy noun/verb extraction
    for this: the bug is "don't AND filler words together with content
    words," which stopword filtering solves completely. POS-tagging
    precision (additionally excluding adjectives/adverbs that slip past
    a stopword list) is a marginal refinement on a problem that's
    already fixed once function-word noise is gone — not worth loading a
    second, differently-configured spaCy pipeline into this module. POS
    tagging needs spaCy's tagger component, which app.services.pii_mask
    explicitly disables (`disable=["tagger", ...]`) for latency; adding
    it back here means two separate model configs resident in memory for
    two different purposes, on top of every /api/retrieve call already
    running one full embedding-model inference. Not a good trade against
    CLAUDE.md's own "provision lookup ≤15s" target for a fix this simple
    a stopword list already covers.
    """
    db = db if db is not None else service_client()
    keywords = _keyword_tokens(facts)
    query_text = " ".join(sorted(keywords)) if keywords else facts
    rows = (
        db.rpc("search_statute_chunks_fulltext", {"query_text": query_text, "match_count": top_k})
        .execute()
        .data
        or []
    )
    if not rows:
        return []

    max_rank = max(float(r["rank"]) for r in rows) or 1.0
    return [
        RetrievedChunk(
            act=r["act"],
            section_no=r["section_no"],
            year=r.get("year"),
            chunk_text=r["text"],
            score=FULLTEXT_WEIGHT * (float(r["rank"]) / max_rank),
        )
        for r in rows
    ]


def _merge_into(merged: dict[tuple[str, str], RetrievedChunk], chunks: list[RetrievedChunk]) -> None:
    for chunk in chunks:
        key = (chunk.act, chunk.section_no)
        if key in merged:
            existing = merged[key]
            merged[key] = RetrievedChunk(
                act=existing.act,
                section_no=existing.section_no,
                year=existing.year,
                chunk_text=existing.chunk_text,
                score=existing.score + chunk.score,
            )
        else:
            merged[key] = chunk


def hybrid_retrieve(facts: str, top_k: int = 5, db=None) -> list[RetrievedChunk]:
    """Vector + keyword (metadata) + full-text search, merged by
    (act, section_no) and re-ranked. A chunk multiple signals agree on is
    boosted — its score is the *sum* across every signal that surfaced
    it, not just whichever was highest — since agreement between
    independent signals (semantic, metadata-lexical, full-text-lexical)
    is itself informative."""
    db = db if db is not None else service_client()
    query_embedding = embed_query(facts)

    vector_results = vector_search(query_embedding, top_k=top_k, db=db)
    keyword_results = keyword_search(facts, top_k=top_k, db=db)
    fulltext_results = fulltext_search(facts, top_k=top_k, db=db)

    merged: dict[tuple[str, str], RetrievedChunk] = {}
    _merge_into(merged, vector_results)
    _merge_into(merged, keyword_results)
    _merge_into(merged, fulltext_results)

    ranked = sorted(merged.values(), key=lambda c: c.score, reverse=True)
    return ranked[:top_k]
