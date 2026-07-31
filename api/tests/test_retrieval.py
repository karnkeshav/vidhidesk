"""Tests for the hybrid statute retriever (TRD §3.2).

The real BAAI/bge-small-en-v1.5 model runs (no network — it's a local
model, already cached from the ingestion pipeline tests); only the
Supabase calls (RPC for vector search, table select for keyword search)
are faked.
"""

from __future__ import annotations

import pytest

from app.services.retrieval import (
    embed_query,
    fulltext_search,
    hybrid_retrieve,
    keyword_search,
    vector_search,
)


class _FakeRpcResponse:
    def __init__(self, data):
        self.data = data


class _FakeRpc:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return _FakeRpcResponse(self._data)


class _FakeSelectResponse:
    def __init__(self, data):
        self.data = data


class _FakeSelect:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def execute(self):
        return _FakeSelectResponse(self._rows)


class FakeDB:
    def __init__(self, rpc_data=None, table_rows=None, rpc_data_by_name=None):
        # rpc_data is shorthand for match_statute_chunks specifically
        # (kept for backward compatibility with tests written before a
        # second RPC function existed); rpc_data_by_name lets a test
        # supply distinct canned rows per RPC function name.
        self._rpc_data_by_name: dict[str, list[dict]] = dict(rpc_data_by_name or {})
        if rpc_data is not None:
            self._rpc_data_by_name.setdefault("match_statute_chunks", rpc_data)
        self._table_rows = table_rows or []
        self.rpc_calls: list[tuple[str, dict]] = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return _FakeRpc(self._rpc_data_by_name.get(name, []))

    def table(self, _name):
        return _FakeSelect(self._table_rows)


def test_embed_query_uses_the_bge_query_instruction_and_returns_384_dims():
    vec = embed_query("courier damaged goods in transit")
    assert len(vec) == 384


def test_vector_search_maps_rpc_rows_to_retrieved_chunks():
    db = FakeDB(
        rpc_data=[
            {"id": "1", "act": "Consumer Protection Act, 2019", "section_no": "34",
             "year": 2019, "text": "District Commission jurisdiction...", "similarity": 0.83},
        ]
    )

    results = vector_search([0.1] * 384, top_k=5, db=db)

    assert len(results) == 1
    assert results[0].act == "Consumer Protection Act, 2019"
    assert results[0].section_no == "34"
    assert results[0].score == 0.83
    assert db.rpc_calls[0][0] == "match_statute_chunks"
    assert db.rpc_calls[0][1]["match_count"] == 5


def test_keyword_search_scores_explicit_section_reference_highest():
    rows = [
        {"act": "Consumer Protection Act, 2019", "section_no": "18", "year": 2019,
         "text": "Central Authority duties..."},
        {"act": "Consumer Protection Act, 2019", "section_no": "34", "year": 2019,
         "text": "District Commission jurisdiction..."},
        {"act": "Carriage by Road Act, 2007", "section_no": "10", "year": 2007,
         "text": "Liability of common carrier..."},
    ]
    db = FakeDB(table_rows=rows)

    results = keyword_search("What does Section 34 say?", top_k=5, db=db)

    assert results[0].section_no == "34"
    assert results[0].score >= 1.0


def test_keyword_search_scores_act_name_overlap_when_no_section_cited():
    rows = [
        {"act": "Consumer Protection Act, 2019", "section_no": "1", "year": 2019, "text": "..."},
        {"act": "Carriage by Road Act, 2007", "section_no": "1", "year": 2007, "text": "..."},
    ]
    db = FakeDB(table_rows=rows)

    results = keyword_search("issues under the Consumer Protection Act", top_k=5, db=db)

    assert len(results) >= 1
    assert results[0].act == "Consumer Protection Act, 2019"


def test_keyword_search_returns_nothing_for_generic_facts_with_no_act_or_section():
    """Documents the known recall gap *for metadata-only keyword search*:
    pure fact patterns with no act name or section number get zero
    signal from this function specifically — that gap is what
    fulltext_search (below) exists to close."""
    rows = [
        {"act": "Consumer Protection Act, 2019", "section_no": "34", "year": 2019, "text": "..."},
    ]
    db = FakeDB(table_rows=rows)

    results = keyword_search("a courier lost my parcel between two cities", top_k=5, db=db)

    assert results == []


# --- fulltext_search ---------------------------------------------------------


def test_fulltext_search_maps_rpc_rows_and_calls_the_right_function():
    db = FakeDB(
        rpc_data_by_name={
            "search_statute_chunks_fulltext": [
                {"id": "1", "act": "Carriage by Road Act, 2007", "section_no": "9",
                 "year": 2007, "text": "General duty of common carrier to accept goods...",
                 "rank": 0.24},
            ]
        }
    )

    results = fulltext_search("carrier refused to accept the consignment", top_k=5, db=db)

    assert len(results) == 1
    assert results[0].act == "Carriage by Road Act, 2007"
    assert results[0].section_no == "9"
    assert db.rpc_calls[0][0] == "search_statute_chunks_fulltext"
    # "the" and "to" are filtered as stopwords/too-short; the rest are
    # passed as content-word keywords, not the raw sentence.
    assert db.rpc_calls[0][1]["query_text"] == "accept carrier consignment refused"
    assert db.rpc_calls[0][1]["match_count"] == 5


def test_fulltext_search_extracts_content_words_not_the_raw_sentence():
    """websearch_to_tsquery implicitly ANDs every term — passing a full
    multi-sentence fact pattern through unfiltered would require every
    single content word to appear in one statute chunk, which is
    over-constrained and matches nothing in practice. The query sent to
    the RPC must be shorter than the raw input and free of function
    words."""
    db = FakeDB(rpc_data_by_name={"search_statute_chunks_fulltext": []})
    facts = (
        "Common carrier refused to accept a consignment of goods for transport "
        "without giving any reason. Consignor wants to know if the carrier had "
        "a legal duty to accept."
    )

    fulltext_search(facts, top_k=5, db=db)

    sent_query = db.rpc_calls[0][1]["query_text"]
    assert len(sent_query.split()) < len(facts.split())
    # "if"/"a"/"to"/"of" are dropped for being too short to count as a
    # word at all; "the"/"for" are dropped as stopwords. Neither should
    # survive into the query sent to the RPC.
    for dropped in ("the", "a", "of", "for", "to", "if"):
        assert dropped not in sent_query.split()
    for content_word in ("carrier", "refused", "accept", "consignment", "duty"):
        assert content_word in sent_query.split()


def test_fulltext_search_normalizes_rank_so_top_hit_gets_full_weight():
    db = FakeDB(
        rpc_data_by_name={
            "search_statute_chunks_fulltext": [
                {"id": "1", "act": "A", "section_no": "1", "year": 2020, "text": "...", "rank": 0.30},
                {"id": "2", "act": "A", "section_no": "2", "year": 2020, "text": "...", "rank": 0.15},
            ]
        }
    )

    results = fulltext_search("query", top_k=5, db=db)

    assert results[0].score == pytest.approx(0.5)  # FULLTEXT_WEIGHT, top hit
    assert results[1].score == pytest.approx(0.25)  # half the top hit's rank


def test_fulltext_search_returns_empty_list_when_rpc_returns_no_rows():
    db = FakeDB(rpc_data_by_name={"search_statute_chunks_fulltext": []})

    assert fulltext_search("nothing matches this", top_k=5, db=db) == []


def test_hybrid_retrieve_surfaces_fulltext_only_match_when_vector_and_keyword_both_miss():
    """The scenario that motivated this feature: an informal fact pattern
    that names neither the act nor a section number, where the correct
    section only turns up via full-text match against the statute's own
    wording — vector and metadata-keyword search both miss entirely."""
    fulltext_only_row = {
        "act": "Carriage by Road Act, 2007", "section_no": "9", "year": 2007,
        "text": "General duty of common carrier to accept goods for carriage...",
    }
    vector_noise_row = {
        "act": "Carriage by Road Act, 2007", "section_no": "2", "year": 2007,
        "text": "Definitions...",
    }
    db = FakeDB(
        rpc_data_by_name={
            "match_statute_chunks": [{**vector_noise_row, "id": "1", "similarity": 0.7}],
            "search_statute_chunks_fulltext": [{**fulltext_only_row, "id": "2", "rank": 0.2}],
        },
        table_rows=[fulltext_only_row, vector_noise_row],  # no act/section named -> keyword_search finds nothing
    )

    results = hybrid_retrieve(
        "Common carrier refused to accept a consignment of goods for transport "
        "without giving any reason.",
        top_k=3,
        db=db,
    )

    assert any(r.act == "Carriage by Road Act, 2007" and r.section_no == "9" for r in results)


def test_hybrid_retrieve_boosts_chunks_both_signals_agree_on():
    shared_row = {
        "act": "Consumer Protection Act, 2019", "section_no": "34", "year": 2019,
        "text": "District Commission jurisdiction...",
    }
    vector_only_row = {
        "act": "Carriage by Road Act, 2007", "section_no": "10", "year": 2007,
        "text": "Liability of common carrier...",
    }
    db = FakeDB(
        rpc_data=[
            {**shared_row, "id": "1", "similarity": 0.5},
            {**vector_only_row, "id": "2", "similarity": 0.6},
        ],
        table_rows=[shared_row, vector_only_row],
    )

    results = hybrid_retrieve("What does Section 34 say?", top_k=5, db=db)

    # shared_row: 0.5 (vector) + 1.0 (exact section match) = 1.5, beats
    # vector_only_row's 0.6 despite the latter's higher raw vector score.
    assert results[0].act == "Consumer Protection Act, 2019"
    assert results[0].section_no == "34"
    assert results[0].score == 1.5


def test_hybrid_retrieve_respects_top_k():
    rows = [
        {"act": "Consumer Protection Act, 2019", "section_no": str(n), "year": 2019, "text": "..."}
        for n in range(1, 10)
    ]
    db = FakeDB(
        rpc_data=[
            {**row, "id": str(i), "similarity": 0.9 - i * 0.01}
            for i, row in enumerate(rows)
        ],
        table_rows=rows,
    )

    results = hybrid_retrieve("consumer complaint", top_k=3, db=db)

    assert len(results) == 3
