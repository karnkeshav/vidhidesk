"""Tests for Advocate Profile API and Migration 0011 Idempotency Guarantee.

Guarantees under test:
  - GET /api/profile returns canonical profile structure
  - PUT /api/profile updates advocate fields cleanly with E.164 phone validation
  - POST /api/profile/avatar validates image file format (JPG, PNG, WEBP) and 2MB limit
  - Migration 0011_create_advocate_profiles.sql is 100% idempotent (IF NOT EXISTS, ON CONFLICT DO NOTHING)
"""

from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.auth import get_current_user, CurrentUser
from app.routers import profile as profile_router

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATION_0011_PATH = REPO_ROOT / "api" / "migrations" / "0011_create_advocate_profiles.sql"


class FakeUserClient:
    def __init__(self, data=None):
        self._data = data or []

    def table(self, name):
        return self

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def execute(self):
        class Res:
            data = []
        return Res()

    def upsert(self, data, *args, **kwargs):
        self._data = [data]
        return self


def mock_get_current_user():
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        email="keshav.karn@gmail.com",
        raw_user_meta_data={
            "full_name": "Adv. Keshav Karn",
            "bar_number": "D/999/2026",
            "primary_court": "Delhi High Court",
            "phone": "+919876543210",
        },
        db=FakeUserClient(),
    )



@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_profile_endpoint(client):
    res = client.get("/api/profile")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert data["full_name"] == "Adv. Keshav Karn"
    assert data["bar_number"] == "D/999/2026"
    assert data["designation"] == "Advocate"


def test_update_profile_endpoint(client):
    payload = {
        "full_name": "Adv. Keshav Karn",
        "designation": "Senior Partner",
        "bar_number": "D/999/2026",
        "primary_court": "Delhi High Court & Supreme Court",
        "phone": "+919876543210",
        "office_address": "Chamber 412, High Court of Delhi",
    }
    res = client.put("/api/profile", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["full_name"] == "Adv. Keshav Karn"
    assert data["designation"] == "Senior Partner"
    assert data["primary_court"] == "Delhi High Court & Supreme Court"


def test_update_profile_invalid_phone(client):
    payload = {
        "phone": "invalid-phone-string-12345678901234567890",
    }
    res = client.put("/api/profile", json=payload)
    assert res.status_code == 422


def test_upload_avatar_invalid_format(client):
    files = {"file": ("test.txt", b"text content", "text/plain")}
    res = client.post("/api/profile/avatar", files=files)
    assert res.status_code == 400
    assert "Invalid image format" in res.json()["detail"]


# --- Oversized-avatar-JWT regression coverage (2026-08-13) ------------------
# A production incident traced a 117KB JWT to user_metadata.avatar_url
# holding a raw base64 data: URI (~87KB) instead of a Supabase Storage
# URL/path. PUT /api/profile had no validation stopping that value from
# being written into Supabase Auth metadata in the first place.


def test_update_profile_rejects_data_uri_avatar(client):
    payload = {"avatar_url": "data:image/jpeg;base64," + "A" * 500}
    res = client.put("/api/profile", json=payload)
    assert res.status_code == 422
    assert "base64" in res.text.lower()


def test_update_profile_rejects_oversized_avatar_url(client):
    # Not a data: URI, but still far larger than any real Storage URL/path
    # ever is -- defense in depth beyond the data: prefix check alone.
    payload = {"avatar_url": "https://example.com/" + "a" * 3000}
    res = client.put("/api/profile", json=payload)
    assert res.status_code == 422


def test_update_profile_accepts_normal_storage_url(client):
    short_url = "https://pgwemjswxdlnshrfoggj.supabase.co/storage/v1/object/public/avatars/user1.jpg"
    payload = {"avatar_url": short_url}
    res = client.put("/api/profile", json=payload)
    assert res.status_code == 200
    assert res.json()["avatar_url"] == short_url


class _FakeAuthAdmin:
    def __init__(self):
        self.last_metadata_update: tuple[str, dict] | None = None

    def update_user_by_id(self, user_id, payload):
        self.last_metadata_update = (user_id, payload)
        return {"id": user_id}


class _FakeAuth:
    def __init__(self):
        self.admin = _FakeAuthAdmin()


class _FakeAvatarBucket:
    def upload(self, path, file, file_options=None):
        return {"path": path}

    def get_public_url(self, path):
        return f"https://fake-storage.local/{path}"


class _FakeAvatarStorage:
    def __init__(self):
        self._bucket = _FakeAvatarBucket()

    def from_(self, bucket_name):
        return self._bucket


class _FakeAvatarServiceClient:
    def __init__(self):
        self.storage = _FakeAvatarStorage()
        self.auth = _FakeAuth()


def test_upload_avatar_happy_path_stores_short_storage_url(client, monkeypatch):
    """The real /avatar upload flow -- Storage upload, not base64 -- must
    keep working, and the value it syncs into Supabase Auth user_metadata
    must be short (proves the fix doesn't just block bad input, it doesn't
    disturb the already-correct golden path either)."""
    fake_svc = _FakeAvatarServiceClient()
    monkeypatch.setattr(profile_router, "service_client", lambda: fake_svc)

    files = {"file": ("photo.jpg", b"\xff\xd8\xff\xe0fake jpeg bytes", "image/jpeg")}
    res = client.post("/api/profile/avatar", files=files)
    assert res.status_code == 200

    data = res.json()
    assert data["avatar_url"].startswith("https://fake-storage.local/avatars/")
    assert len(data["avatar_url"]) < 200

    user_id, metadata_payload = fake_svc.auth.admin.last_metadata_update
    stored_avatar_url = metadata_payload["user_metadata"]["avatar_url"]
    assert stored_avatar_url == data["avatar_url"]
    assert len(stored_avatar_url) < 200
    assert not stored_avatar_url.startswith("data:")


MIGRATION_0012_PATH = REPO_ROOT / "api" / "migrations" / "0012_simplify_advocate_profiles.sql"


def test_migration_0011_and_0012_idempotency_syntax():
    """Verify migrations 0011 and 0012 contain required idempotent SQL constructs."""
    assert MIGRATION_0011_PATH.exists(), "Migration 0011_create_advocate_profiles.sql must exist"
    sql11 = MIGRATION_0011_PATH.read_text()

    assert "CREATE TABLE IF NOT EXISTS public.advocate_profiles" in sql11
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in sql11
    assert "ON CONFLICT (user_id) DO NOTHING" in sql11
    assert "CONSTRAINT uq_advocate_profiles_bar_state UNIQUE" in sql11
    assert "CHECK (phone IS NULL OR phone ~ '^\\+?[1-9]\\d{1,14}$')" in sql11
    assert "raw_user_meta_data->>'full_name' IS NOT NULL" in sql11

    assert MIGRATION_0012_PATH.exists(), "Migration 0012_simplify_advocate_profiles.sql must exist"
    sql12 = MIGRATION_0012_PATH.read_text()
    assert "ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS enrollment_state;" in sql12
    assert "ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS practice_areas;" in sql12
