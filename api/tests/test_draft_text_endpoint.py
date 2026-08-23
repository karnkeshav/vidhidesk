"""Tests for GET /api/drafts/{draft_version_id}/text (RERA Phase 2G).

This endpoint restores a historical draft's preview text by reading the
already-persisted .docx directly (python-docx), not by reconstructing
content from template_clauses/draft_clause_fills — see the docstring on
app.routers.contracts.get_draft_text for why reconstruction was rejected
(generation-time form_data, which decides both clause applicability and
fixed_boilerplate's Jinja substitutions, is never persisted).

Runs against an in-memory FakeDB (same convention as test_rera.py/
test_matters_update.py) — never touches real Supabase. The real .docx
read/write in these tests goes through a real temp directory (monkeypatched
in place of REPO_ROOT), not the repo tree.
"""

from __future__ import annotations

import uuid

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers import contracts as contracts_router


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op):
        self.table = table
        self.op = op
        self.filters: dict[str, object] = {}

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        return _FakeResponse(matches)


class _FakeTable:
    def __init__(self, name):
        self.name = name
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def insert(self, record):
        items = record if isinstance(record, list) else [record]
        inserted = []
        for item in items:
            row = dict(item)
            row.setdefault("id", str(uuid.uuid4()))
            self.rows.append(row)
            inserted.append(row)
        return _FakeInsertResult(inserted)


class _FakeInsertResult:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return _FakeResponse(self._rows)


class FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))

    def snapshot(self) -> dict[str, list[dict]]:
        """Deep-ish snapshot of every table's rows, for a before/after
        no-mutation assertion — a plain dict copy is enough since these
        tests never mutate a row's nested values in place."""
        return {name: [dict(r) for r in t.rows] for name, t in self._tables.items()}


def _make_client(fake_db, user_id="user-1"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, email="nitesh@example.com", db=fake_db
    )
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token"}


def _seed_draft(db: FakeDB, docx_path: str, version_no: int = 1) -> str:
    row = db.table("draft_versions").insert(
        {
            "matter_id": str(uuid.uuid4()),
            "template_id": str(uuid.uuid4()),
            "version_no": version_no,
            "docx_path": docx_path,
            "change_summary": "Generated from Mortgage Deed",
        }
    ).execute().data[0]
    return row["id"]


def _write_real_docx(path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def test_authorized_access_to_valid_docx_returns_extracted_text(monkeypatch, tmp_path):
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    docx_rel = "api/generated_drafts/matter-1_v1.docx"
    _write_real_docx(
        tmp_path / docx_rel,
        ["MORTGAGE DEED", "", "1. Recitals", "", "This is the recital text."],
    )
    db = FakeDB()
    draft_id = _seed_draft(db, docx_rel, version_no=1)
    client = _make_client(db)

    resp = client.get(f"/api/drafts/{draft_id}/text", headers=AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert body["draft_version_id"] == draft_id
    assert body["version_no"] == 1
    assert "MORTGAGE DEED" in body["full_text"]
    assert "This is the recital text." in body["full_text"]


def test_nonexistent_draft_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    db = FakeDB()
    client = _make_client(db)

    resp = client.get(f"/api/drafts/{uuid.uuid4()}/text", headers=AUTH)

    assert resp.status_code == 404


def test_missing_docx_file_on_disk_returns_404_not_500(monkeypatch, tmp_path):
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    db = FakeDB()
    draft_id = _seed_draft(db, "api/generated_drafts/does_not_exist_v1.docx")
    client = _make_client(db)

    resp = client.get(f"/api/drafts/{draft_id}/text", headers=AUTH)

    assert resp.status_code == 404
    assert "missing on disk" in resp.json()["detail"].lower()


def test_corrupt_docx_file_returns_clean_error_not_500(monkeypatch, tmp_path):
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    bad_path = tmp_path / "api/generated_drafts/corrupt_v1.docx"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("this is not a real docx file")
    db = FakeDB()
    draft_id = _seed_draft(db, "api/generated_drafts/corrupt_v1.docx")
    client = _make_client(db)

    resp = client.get(f"/api/drafts/{draft_id}/text", headers=AUTH)

    assert resp.status_code == 422


def test_same_lookup_helper_as_existing_download_endpoint_missing_id_parity(tmp_path, monkeypatch):
    """Both /download and /text sit behind the exact same `_get_draft_or_404`
    helper (app.routers.contracts) -- the real ownership/access boundary is
    enforced by Supabase RLS on that shared lookup (see the helper's own
    docstring), which a FakeDB unit test cannot simulate. What IS verifiable
    here, without touching real Supabase, is that both endpoints behave
    identically -- same 404 -- for a draft id that doesn't resolve for this
    caller, confirming /text didn't add an independent, potentially-weaker
    lookup path."""
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    db = FakeDB()
    client = _make_client(db)
    missing_id = str(uuid.uuid4())

    download_resp = client.get(f"/api/drafts/{missing_id}/download", headers=AUTH)
    text_resp = client.get(f"/api/drafts/{missing_id}/text", headers=AUTH)

    assert download_resp.status_code == text_resp.status_code == 404


def test_text_endpoint_never_mutates_the_database(monkeypatch, tmp_path):
    monkeypatch.setattr(contracts_router, "REPO_ROOT", tmp_path)
    docx_rel = "api/generated_drafts/matter-2_v1.docx"
    _write_real_docx(tmp_path / docx_rel, ["SALE DEED", "Some clause text."])
    db = FakeDB()
    draft_id = _seed_draft(db, docx_rel)
    client = _make_client(db)

    before = db.snapshot()
    resp = client.get(f"/api/drafts/{draft_id}/text", headers=AUTH)
    after = db.snapshot()

    assert resp.status_code == 200
    assert before == after
