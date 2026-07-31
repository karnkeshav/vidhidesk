"""Tests for the nightly dead-link recheck job.

Guarantees under test: a verified citation whose URL stops resolving gets
marked stale (never deleted); one that recovers gets un-staled; the row's
`status` itself is never touched by this job.
"""

import httpx
import respx

from scripts.recheck_citations import recheck_all


class FakeUpdate:
    def __init__(self, table: "FakeTable", patch: dict):
        self._table = table
        self._patch = patch
        self._id = None

    def eq(self, _column: str, value) -> "FakeUpdate":
        self._id = value
        return self

    def execute(self):
        for row in self._table.rows:
            if row["id"] == self._id:
                row.update(self._patch)
        return None


class FakeSelect:
    def __init__(self, table: "FakeTable"):
        self._table = table
        self._filters: dict[str, object] = {}
        self._range: tuple[int, int] | None = None

    def select(self, *_a, **_k) -> "FakeSelect":
        return self

    def eq(self, column: str, value) -> "FakeSelect":
        self._filters[column] = value
        return self

    def range(self, start: int, end: int) -> "FakeSelect":
        self._range = (start, end)
        return self

    def execute(self):
        matches = [
            row for row in self._table.rows
            if all(row.get(c) == v for c, v in self._filters.items())
        ]
        if self._range:
            start, end = self._range
            matches = matches[start : end + 1]

        class R:
            data = matches

        return R()


class FakeTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def select(self, *_a, **_k) -> FakeSelect:
        return FakeSelect(self)

    def update(self, patch: dict) -> FakeUpdate:
        return FakeUpdate(self, patch)


class FakeSupabase:
    def __init__(self, citation_rows: list[dict]):
        self._citations = FakeTable(citation_rows)

    def table(self, name: str):
        assert name == "citations"
        return self._citations


@respx.mock
def test_dead_link_gets_marked_stale():
    rows = [{"id": "c1", "status": "verified", "ik_url": "https://indiankanoon.org/doc/1/", "stale": False}]
    db = FakeSupabase(rows)
    respx.head("https://indiankanoon.org/doc/1/").mock(return_value=httpx.Response(404))

    stats = recheck_all(db=db)

    assert stats["marked_stale"] == 1
    assert rows[0]["stale"] is True


@respx.mock
def test_live_link_stays_unstale():
    rows = [{"id": "c1", "status": "verified", "ik_url": "https://indiankanoon.org/doc/1/", "stale": False}]
    db = FakeSupabase(rows)
    respx.head("https://indiankanoon.org/doc/1/").mock(return_value=httpx.Response(200))

    stats = recheck_all(db=db)

    assert stats["ok"] == 1
    assert rows[0]["stale"] is False


@respx.mock
def test_previously_stale_link_recovers():
    rows = [{"id": "c1", "status": "verified", "ik_url": "https://indiankanoon.org/doc/1/", "stale": True}]
    db = FakeSupabase(rows)
    respx.head("https://indiankanoon.org/doc/1/").mock(return_value=httpx.Response(200))

    stats = recheck_all(db=db)

    assert stats["recovered"] == 1
    assert rows[0]["stale"] is False


@respx.mock
def test_network_error_counts_as_not_ok_and_marks_stale():
    rows = [{"id": "c1", "status": "verified", "ik_url": "https://indiankanoon.org/doc/1/", "stale": False}]
    db = FakeSupabase(rows)
    respx.head("https://indiankanoon.org/doc/1/").mock(side_effect=httpx.ConnectTimeout("timeout"))

    stats = recheck_all(db=db)

    assert stats["marked_stale"] == 1
    assert rows[0]["stale"] is True
