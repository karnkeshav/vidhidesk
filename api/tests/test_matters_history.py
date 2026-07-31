"""Integration test for conversation history across chat turns.

Exercises the full router path (POST /api/matters/{id}/messages) against
a fake Supabase client and a mocked LLM provider — no real network or
database calls. Proves the concrete scenario: a PAN mentioned in message
1 is correctly resolved when message 2 asks about it via a pronoun,
because (a) history is assembled from persisted messages and sent to the
LLM, and (b) the placeholder the mocked LLM echoes back gets unmasked
using the same per-matter mask_map.
"""

from __future__ import annotations

import itertools
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import respx
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table: "_FakeTable"):
        self.table = table
        self.filters: dict[str, object] = {}
        self._order = None
        self._desc = False
        self._limit = None

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def is_(self, col, _value):
        self.filters[col] = None
        return self

    def order(self, col, desc=False):
        self._order = col
        self._desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = [
            r for r in self.table.rows
            if all(r.get(k) == v for k, v in self.filters.items())
        ]
        if self._order:
            rows = sorted(rows, key=lambda r: r[self._order], reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _FakeResponse(rows)


class _FakeInsert:
    def __init__(self, table: "_FakeTable", record):
        self.table = table
        self.record = record

    def execute(self):
        records = self.record if isinstance(self.record, list) else [self.record]
        inserted = []
        for rec in records:
            row = dict(rec)
            row.setdefault("id", str(uuid.uuid4()))
            seq = next(self.table.db.clock)
            row.setdefault(
                "created_at",
                (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seq)).isoformat(),
            )
            row.setdefault("client_name", None)
            row.setdefault("model_used", None)
            row.setdefault("masked_prompt", None)
            row.setdefault("retrieval_sources", None)
            self.table.rows.append(row)
            inserted.append(row)
        return _FakeResponse(inserted)


class _FakeTable:
    def __init__(self, db: "FakeDB", name: str):
        self.db = db
        self.name = name
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self)

    def insert(self, record):
        return _FakeInsert(self, record)


class FakeDB:
    """Backs both `user.db` and the service-role client used for
    pii_masks — same tables, since matter/message ownership isn't the
    concern under test here."""

    def __init__(self):
        self.clock = itertools.count()
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name: str) -> _FakeTable:
        return self._tables.setdefault(name, _FakeTable(self, name))


def _gemini_response(text: str) -> httpx.Response:
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}
    )


def test_history_resolves_pronoun_reference_across_messages(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr("app.routers.matters.service_client", lambda: fake_db)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-1", email="nitesh@example.com", db=fake_db
    )
    client = TestClient(app)

    matter = fake_db.table("matters").insert(
        {"id": str(uuid.uuid4()), "user_id": "user-1", "title": "Test matter",
         "client_name": None, "module": "litigation"}
    ).execute().data[0]

    captured_bodies: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured_bodies.append(body)
        if len(captured_bodies) == 1:
            # Message 1: model just acknowledges — no PII in its reply.
            return _gemini_response("Noted.")
        # Message 2: simulate a model that correctly used history to
        # resolve "his" and answer using the placeholders it saw.
        return _gemini_response("His PAN is PAN_1, on file for PARTY_A.")

    try:
        with respx.mock:
            respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
                side_effect=_capture
            )

            r1 = client.post(
                f"/api/matters/{matter['id']}/messages",
                json={"content": "My client Ramesh Kumar has PAN ABCDE1234F"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert r1.status_code == 201

            r2 = client.post(
                f"/api/matters/{matter['id']}/messages",
                json={"content": "what is his PAN?"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert r2.status_code == 201
    finally:
        app.dependency_overrides.clear()

    # The outbound request for message 2 must include message 1's masked
    # content as history — not the raw name/PAN, and not omitted entirely.
    assert len(captured_bodies) == 2
    second_request_contents = captured_bodies[1]["contents"]
    history_texts = [c["parts"][0]["text"] for c in second_request_contents[:-1]]
    assert any("PARTY_A" in t and "PAN_1" in t for t in history_texts)
    assert not any("Ramesh Kumar" in t for t in history_texts)
    assert not any("ABCDE1234F" in t for t in history_texts)

    # The final assistant reply, as returned to the caller and stored,
    # must have the placeholders resolved back to the real values.
    assistant_message = r2.json()[1]
    assert assistant_message["role"] == "assistant"
    assert "ABCDE1234F" in assistant_message["content"]
    assert "Ramesh Kumar" in assistant_message["content"]
    assert "PAN_1" not in assistant_message["content"]
    assert "PARTY_A" not in assistant_message["content"]
