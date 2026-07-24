"""Tests for the citation cache-first wrapper.

Core guarantee under test: a repeated lookup for the same case name never
re-calls the Indian Kanoon API, and a citation record only ever carries a
doc id / URL when a real match was found — never fabricated.
"""

from app.services.citations import verify_citation


class FakeIndianKanoonClient:
    """Records every call so tests can assert on cache-first behaviour."""

    def __init__(self, docs: list[dict]):
        self._docs = docs
        self.search_calls: list[tuple[str, str | None]] = []

    def search(self, query: str, court: str | None = None, max_pages: int = 1) -> dict:
        self.search_calls.append((query, court))
        return {"docs": self._docs, "pages_fetched": 1}


class FakeQuery:
    def __init__(self, table: "FakeTable"):
        self._table = table
        self._filters: dict[str, object] = {}

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def ilike(self, column: str, value: str) -> "FakeQuery":
        self._filters[column] = value.lower()
        return self

    def eq(self, column: str, value) -> "FakeQuery":
        self._filters[column] = value
        return self

    def is_(self, column: str, _value: str) -> "FakeQuery":
        self._filters[column] = None
        return self

    def limit(self, _n: int) -> "FakeQuery":
        return self

    def execute(self) -> "FakeResponse":
        matches = []
        for row in self._table.rows:
            ok = True
            for col, val in self._filters.items():
                row_val = row.get(col)
                row_val_cmp = row_val.lower() if isinstance(row_val, str) and col == "case_name" else row_val
                if row_val_cmp != val:
                    ok = False
                    break
            if ok:
                matches.append(row)
        return FakeResponse(matches)


class FakeInsert:
    def __init__(self, table: "FakeTable", record: dict):
        self._table = table
        self._record = record

    def execute(self) -> "FakeResponse":
        self._table.rows.append(dict(self._record))
        return FakeResponse([self._record])


class FakeResponse:
    def __init__(self, data: list[dict]):
        self.data = data


class FakeTable:
    def __init__(self):
        self.rows: list[dict] = []

    def select(self, *_args, **_kwargs) -> FakeQuery:
        return FakeQuery(self)

    def insert(self, record: dict) -> FakeInsert:
        return FakeInsert(self, record)


class FakeSupabase:
    def __init__(self):
        self._tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        return self._tables.setdefault(name, FakeTable())


def test_cache_miss_then_hit_calls_ik_api_exactly_once():
    ik = FakeIndianKanoonClient(
        docs=[{"title": "Kesavananda Bharati vs State of Kerala", "tid": "12345"}]
    )
    db = FakeSupabase()

    first = verify_citation("Kesavananda Bharati vs State of Kerala", ik_client=ik, db=db)
    assert first.status == "verified"
    assert first.ik_doc_id == "12345"
    assert first.ik_url == "https://indiankanoon.org/doc/12345/"
    assert first.from_cache is False
    assert len(ik.search_calls) == 1

    second = verify_citation("Kesavananda Bharati vs State of Kerala", ik_client=ik, db=db)
    assert second.from_cache is True
    assert second.ik_doc_id == "12345"
    # The repeated lookup must not hit the API again.
    assert len(ik.search_calls) == 1


def test_no_match_is_cached_as_unverified_with_no_fabricated_link():
    ik = FakeIndianKanoonClient(docs=[])
    db = FakeSupabase()

    result = verify_citation("Zzqxvthorpe Nonexistent Fictional Litigant", ik_client=ik, db=db)

    assert result.status == "unverified"
    assert result.ik_doc_id is None
    assert result.ik_url is None

    # Still cached — no repeat API call for the same nonsense query.
    verify_citation("Zzqxvthorpe Nonexistent Fictional Litigant", ik_client=ik, db=db)
    assert len(ik.search_calls) == 1


def test_weak_title_match_does_not_produce_a_false_positive_link():
    # A completely unrelated title should not be treated as a match just
    # because *a* result came back.
    ik = FakeIndianKanoonClient(docs=[{"title": "Unrelated Municipal Corporation Bylaw Notice", "tid": "999"}])
    db = FakeSupabase()

    result = verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)

    assert result.status == "unverified"
    assert result.ik_doc_id is None
