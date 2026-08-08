"""Tests for POST /api/matters/{matter_id}/evidence/upload (Sprint 3.5.3):
real exhibit/document upload, not just a text label, following the same
Supabase Storage pattern as profile.py's avatar upload."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers import litigation as litigation_router

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_0014_PATH = REPO_ROOT / "migrations" / "0014_litigation_case_analysis.sql"


class DummyDBTable:
    def __init__(self, table_name: str, store: dict[str, list[dict]]):
        self.table_name = table_name
        self.store = store
        self._where_clause: dict[str, Any] = {}

    def select(self, *args, **kwargs):
        return self

    def insert(self, row_data: dict | list[dict]):
        items = row_data if isinstance(row_data, list) else [row_data]
        inserted = []
        for item in items:
            record = dict(item)
            if "id" not in record:
                import uuid

                record["id"] = str(uuid.uuid4())
            if "created_at" not in record:
                from datetime import datetime, timezone

                record["created_at"] = datetime.now(timezone.utc).isoformat()
            self.store.setdefault(self.table_name, []).append(record)
            inserted.append(record)
        self._inserted_data = inserted
        return self

    def eq(self, column: str, value: Any):
        self._where_clause[column] = value
        return self

    def limit(self, count: int):
        return self

    def order(self, column: str, **kwargs):
        return self

    def execute(self):
        class DummyResp:
            def __init__(self, data):
                self.data = data

        if hasattr(self, "_inserted_data"):
            data = self._inserted_data
            del self._inserted_data
            return DummyResp(data)
        records = self.store.get(self.table_name, [])
        filtered = [r for r in records if all(r.get(k) == v for k, v in self._where_clause.items())]
        return DummyResp(filtered)


class DummyDBClient:
    def __init__(self):
        self.store: dict[str, list[dict]] = {"matters": [], "litigation_facts_evidence": []}

    def table(self, name: str):
        return DummyDBTable(name, self.store)


def get_mock_user():
    return CurrentUser(id="user-123", email="advocate@vidhidesk.com", db=DummyDBClient())


@pytest.fixture
def client():
    # Capture ONE CurrentUser (and its one in-memory DummyDBClient) so state
    # persists across requests within a test — dependency_overrides calls
    # this callable fresh per request, so passing get_mock_user directly
    # (instead of a fixed instance) would hand every request a brand new,
    # empty fake database and every matter lookup would 404.
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _create_matter(client: TestClient) -> str:
    res = client.post("/api/matters", json={"title": "Evidence Test Matter", "module": "litigation"})
    return res.json()["id"]


def test_upload_evidence_rejects_unsupported_file_type(client):
    matter_id = _create_matter(client)
    files = {"file": ("notes.exe", b"binary", "application/x-msdownload")}
    res = client.post(f"/api/matters/{matter_id}/evidence/upload", files=files)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_upload_evidence_rejects_oversized_file(client):
    matter_id = _create_matter(client)
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    files = {"file": ("scan.pdf", oversized, "application/pdf")}
    res = client.post(f"/api/matters/{matter_id}/evidence/upload", files=files)
    assert res.status_code == 400
    assert "10MB" in res.json()["detail"]


def test_upload_evidence_404_for_missing_matter(client):
    files = {"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")}
    res = client.post("/api/matters/does-not-exist/evidence/upload", files=files)
    assert res.status_code == 404


class _FakeBucket:
    def __init__(self):
        self.uploaded_path = None

    def upload(self, path, file, file_options=None):
        self.uploaded_path = path
        return {"path": path}

    def get_public_url(self, path):
        return f"https://fake-storage.local/{path}"


class _FakeStorage:
    def __init__(self):
        self.bucket = _FakeBucket()

    def from_(self, bucket_name):
        return self.bucket


class _FakeServiceClient:
    def __init__(self):
        self.storage = _FakeStorage()


def test_upload_evidence_happy_path_creates_evidence_row_with_file_url(client, monkeypatch):
    monkeypatch.setattr(litigation_router, "service_client", lambda: _FakeServiceClient())

    matter_id = _create_matter(client)
    files = {"file": ("agreement_scan.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")}
    data = {"exhibit_number": "Exhibit P-2", "relevance_notes": "Signed agreement scan"}

    res = client.post(f"/api/matters/{matter_id}/evidence/upload", files=files, data=data)
    assert res.status_code == 201
    body = res.json()
    assert body["exhibit_number"] == "Exhibit P-2"
    assert body["file_name"] == "agreement_scan.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["file_url"].startswith(f"https://fake-storage.local/evidence/{matter_id}/")
    assert body["file_size_bytes"] == len(b"%PDF-1.4 fake pdf content")

    listed = client.get(f"/api/matters/{matter_id}/evidence")
    assert len(listed.json()) == 1


def test_upload_evidence_degrades_gracefully_when_storage_fails(client, monkeypatch):
    """A storage outage must not lose the evidence record — the row is
    still created, just without a file_url, matching profile.py's avatar
    upload fallback convention."""

    def _boom():
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(litigation_router, "service_client", _boom)

    matter_id = _create_matter(client)
    files = {"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")}
    res = client.post(f"/api/matters/{matter_id}/evidence/upload", files=files)
    assert res.status_code == 201
    assert res.json()["file_url"] is None
    assert res.json()["file_name"] == "scan.pdf"


def test_migration_0014_idempotency_and_rls():
    assert MIGRATION_0014_PATH.exists(), "Migration 0014_litigation_case_analysis.sql must exist"
    sql = MIGRATION_0014_PATH.read_text()
    assert "ADD COLUMN IF NOT EXISTS file_url" in sql
    assert "CREATE TABLE IF NOT EXISTS public.litigation_case_analyses" in sql
    assert "ALTER TABLE public.litigation_case_analyses ENABLE ROW LEVEL SECURITY;" in sql
    assert "UNIQUE (matter_id, version_no)" in sql
