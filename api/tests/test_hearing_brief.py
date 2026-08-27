"""Tests for app/services/hearing_brief.py. Mocks generate() (no real LLM
call) AND service_client() (no real Supabase call for pii_masks/
notifications, unlike test_case_analysis.py's sibling tests -- writing
test notification rows against a real project during a test run is worth
avoiding even though that pattern already exists elsewhere in this suite).

Covers: matter/hearing existence checks, the grounding enforcement that
drops any case_record/supported_arguments entry missing source_refs,
version incrementing, malformed-JSON degrade path, and the mandatory-
review workflow (draft -> reviewed -> approved_for_hearing)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from app.services import hearing_brief
from app.services.llm_gateway import GenerationResult


class DummyDBTable:
    def __init__(self, table_name: str, store: dict[str, list[dict]]):
        self.table_name = table_name
        self.store = store
        self._where: dict[str, Any] = {}

    def select(self, *_a, **_k):
        return self

    def insert(self, row_data):
        items = row_data if isinstance(row_data, list) else [row_data]
        inserted = []
        for item in items:
            record = dict(item)
            record.setdefault("id", str(uuid.uuid4()))
            record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            self.store.setdefault(self.table_name, []).append(record)
            inserted.append(record)
        self._inserted = inserted
        return self

    def update(self, payload):
        matches = [r for r in self.store.get(self.table_name, []) if all(r.get(k) == v for k, v in self._where.items())]
        for r in matches:
            r.update(payload)
        self._inserted = matches
        return self

    def eq(self, col, val):
        self._where[col] = val
        return self

    def order(self, col, desc=False, **_k):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        class R:
            def __init__(self, data):
                self.data = data

        if hasattr(self, "_inserted"):
            data = self._inserted
            del self._inserted
            return R(data)
        rows = [r for r in self.store.get(self.table_name, []) if all(r.get(k) == v for k, v in self._where.items())]
        if getattr(self, "_order", None):
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or 0, reverse=desc)
        if getattr(self, "_limit", None):
            rows = rows[: self._limit]
        return R(rows)


class DummyDBClient:
    def __init__(self):
        self.store: dict[str, list[dict]] = {}

    def table(self, name):
        return DummyDBTable(name, self.store)


def _seed_matter(db, matter_id="m1", module="litigation"):
    db.store["matters"] = [{"id": matter_id, "organization_id": "org-1", "user_id": "u1", "title": "Test Matter", "module": module}]


def _seed_hearing(db, matter_id="m1", hearing_id="h1"):
    db.store.setdefault("hearings", []).append({"id": hearing_id, "matter_id": matter_id, "hearing_at": "2026-08-28T00:00:00Z"})


def _seed_party(db, matter_id="m1"):
    db.store.setdefault("litigation_parties", []).append({"id": "p1", "matter_id": matter_id, "party_type": "Petitioner", "party_number": 1, "party_name": "A"})


def _fake_generate_factory(text: str):
    def _fake(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        return GenerationResult(text=text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt)

    return _fake


VALID_JSON = """{
  "case_record": [{"heading": "Posture", "content": "Matter is at arguments stage.", "source_refs": ["Order dated 2026-08-01"]}],
  "supported_arguments": [{"argument": "Limitation has not expired.", "source_refs": ["Pleading: Facts"]}],
  "ai_suggested_points": ["Consider requesting an adjournment if evidence is not ready."],
  "checklist": ["Carry certified copy of last order"],
  "information_gaps": ["No argument notes from the previous hearing"]
}"""

UNGROUNDED_JSON = """{
  "case_record": [{"heading": "Fabricated", "content": "An order that does not exist", "source_refs": []}],
  "supported_arguments": [{"argument": "An argument with no source", "source_refs": []}],
  "ai_suggested_points": [],
  "checklist": [],
  "information_gaps": []
}"""


def test_matter_not_found_raises(monkeypatch):
    db = DummyDBClient()
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    with pytest.raises(hearing_brief.HearingBriefError):
        hearing_brief.generate_hearing_brief("nope", "h1", db)


def test_non_litigation_matter_rejected(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db, module="contracts")
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    with pytest.raises(hearing_brief.HearingBriefError, match="litigation matters"):
        hearing_brief.generate_hearing_brief("m1", "h1", db)


def test_hearing_not_found_raises(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    with pytest.raises(hearing_brief.HearingBriefError, match="not found"):
        hearing_brief.generate_hearing_brief("m1", "does-not-exist", db)


def test_happy_path_creates_draft_brief_and_notification(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db)
    _seed_hearing(db)
    _seed_party(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    result = hearing_brief.generate_hearing_brief("m1", "h1", db)

    assert result["status"] == "draft"
    assert result["version"] == 1
    assert len(result["brief_content"]["case_record"]) == 1
    assert result["brief_content"]["case_record"][0]["source_refs"] == ["Order dated 2026-08-01"]
    assert len(result["brief_content"]["ai_suggested_points"]) == 1

    notifications = db.store.get("notifications", [])
    assert len(notifications) == 1
    assert notifications[0]["type"] == "brief_ready"


def test_ungrounded_entries_are_dropped(monkeypatch):
    """Hard requirement: case_record/supported_arguments entries with no
    source_refs must never appear in the persisted brief."""
    db = DummyDBClient()
    _seed_matter(db)
    _seed_hearing(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(UNGROUNDED_JSON))

    result = hearing_brief.generate_hearing_brief("m1", "h1", db)

    assert result["brief_content"]["case_record"] == []
    assert result["brief_content"]["supported_arguments"] == []


def test_malformed_json_degrades_with_warning(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db)
    _seed_hearing(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory("not valid json at all"))

    result = hearing_brief.generate_hearing_brief("m1", "h1", db)

    assert result["brief_content"]["generation_warning"] is not None
    assert "not valid json" in result["brief_content"]["case_record"][0]["content"]


def test_version_increments_per_hearing(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db)
    _seed_hearing(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    first = hearing_brief.generate_hearing_brief("m1", "h1", db)
    second = hearing_brief.generate_hearing_brief("m1", "h1", db)

    assert first["version"] == 1
    assert second["version"] == 2
    assert len(hearing_brief.list_hearing_briefs("h1", db)) == 2


def test_review_workflow_transitions(monkeypatch):
    db = DummyDBClient()
    _seed_matter(db)
    _seed_hearing(db)
    monkeypatch.setattr(hearing_brief, "service_client", lambda: db)
    monkeypatch.setattr(hearing_brief, "generate", _fake_generate_factory(VALID_JSON))

    brief = hearing_brief.generate_hearing_brief("m1", "h1", db)
    assert brief["status"] == "draft"

    reviewed = hearing_brief.review_hearing_brief(brief["id"], status="reviewed", lawyer_edits=None, db=db)
    assert reviewed["status"] == "reviewed"
    assert reviewed["reviewed_at"] is not None

    approved = hearing_brief.review_hearing_brief(brief["id"], status="approved_for_hearing", lawyer_edits={"note": "ready"}, db=db)
    assert approved["status"] == "approved_for_hearing"
    assert approved["approved_at"] is not None
    assert approved["lawyer_edits"] == {"note": "ready"}


def test_review_invalid_status_rejected(monkeypatch):
    db = DummyDBClient()
    with pytest.raises(hearing_brief.HearingBriefError):
        hearing_brief.review_hearing_brief("some-id", status="draft", lawyer_edits=None, db=db)


def test_review_unknown_brief_raises(monkeypatch):
    db = DummyDBClient()
    with pytest.raises(hearing_brief.HearingBriefError, match="not found"):
        hearing_brief.review_hearing_brief("does-not-exist", status="reviewed", lawyer_edits=None, db=db)
