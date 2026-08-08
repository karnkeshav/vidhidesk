from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient
from app.auth import CurrentUser, get_current_user
from app.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_0013_PATH = REPO_ROOT / "migrations" / "0013_litigation_schema.sql"


class DummyDBTable:
    def __init__(self, table_name: str, store: dict[str, list[dict]]):
        self.table_name = table_name
        self.store = store
        self._where_clause = {}
        self._order_col = None

    def select(self, *args, **kwargs):
        return self

    def insert(self, row_data: dict | list[dict]):
        if self.table_name not in self.store:
            self.store[self.table_name] = []
        if isinstance(row_data, list):
            items = row_data
        else:
            items = [row_data]

        inserted = []
        for item in items:
            record = dict(item)
            if "id" not in record:
                import uuid
                record["id"] = str(uuid.uuid4())
            if "created_at" not in record:
                from datetime import datetime, timezone
                record["created_at"] = datetime.now(timezone.utc).isoformat()
            self.store[self.table_name].append(record)
            inserted.append(record)

        self._inserted_data = inserted
        return self

    def update(self, update_data: dict):
        self._update_data = update_data
        return self

    def delete(self):
        self._is_delete = True
        return self

    def eq(self, column: str, value: Any):
        self._where_clause[column] = value
        return self

    def limit(self, count: int):
        return self

    def order(self, column: str, **kwargs):
        self._order_col = column
        return self

    def execute(self):
        if hasattr(self, "_inserted_data"):
            data = self._inserted_data
            del self._inserted_data
            class DummyResp:
                def __init__(self, data):
                    self.data = data
            return DummyResp(data)

        records = self.store.get(self.table_name, [])
        filtered = []
        for r in records:
            match = True
            for k, v in self._where_clause.items():
                if r.get(k) != v:
                    match = False
                    break
            if match:
                filtered.append(r)

        if hasattr(self, "_update_data"):
            updated = []
            for r in filtered:
                r.update(self._update_data)
                updated.append(r)
            class DummyResp:
                def __init__(self, data):
                    self.data = data
            return DummyResp(updated)

        if hasattr(self, "_is_delete"):
            self.store[self.table_name] = [r for r in records if r not in filtered]
            class DummyResp:
                def __init__(self, data):
                    self.data = data
            return DummyResp(filtered)

        class DummyResp:
            def __init__(self, data):
                self.data = data
        return DummyResp(filtered)


class DummyDBClient:
    def __init__(self):
        self.store = {
            "matters": [],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_hearings": [],
        }

    def table(self, name: str):
        return DummyDBTable(name, self.store)


def get_mock_user():
    return CurrentUser(id="user-123", email="advocate@vidhidesk.com", db=DummyDBClient())


def test_migration_0013_idempotency_syntax():
    """Verify migration 0013 contains required idempotent SQL constructs."""
    assert MIGRATION_0013_PATH.exists(), "Migration 0013_litigation_schema.sql must exist"
    sql = MIGRATION_0013_PATH.read_text()

    assert "ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS court_category text;" in sql
    assert "CREATE TABLE IF NOT EXISTS public.litigation_parties" in sql
    assert "CREATE TABLE IF NOT EXISTS public.litigation_facts_evidence" in sql
    assert "CREATE TABLE IF NOT EXISTS public.litigation_hearings" in sql
    assert "ALTER TABLE public.litigation_parties ENABLE ROW LEVEL SECURITY;" in sql


def test_create_litigation_matter():
    """Verify creating a litigation matter with court category and jurisdiction state."""
    app.dependency_overrides[get_current_user] = get_mock_user
    client = TestClient(app)

    payload = {
        "title": "Karn vs State of Delhi",
        "client_name": "Keshav Karn",
        "module": "litigation",
        "court_category": "High Court",
        "jurisdiction_state": "Delhi",
        "cnr_number": "DHC123456789",
        "case_number_formatted": "WP(C) 1234/2026",
    }
    res = client.post("/api/matters", json=payload)
    app.dependency_overrides.clear()

    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Karn vs State of Delhi"
    assert data["module"] == "litigation"
    assert data["court_category"] == "High Court"
    assert data["jurisdiction_state"] == "Delhi"
    assert data["cnr_number"] == "DHC123456789"


def test_litigation_parties_crud():
    """Verify adding, listing, and deleting Petitioners and Respondents."""
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    # 1. Create Matter
    m_res = client.post("/api/matters", json={"title": "Test Litigation Matter", "module": "litigation"})
    matter_id = m_res.json()["id"]

    # 2. Add Petitioner
    p1 = client.post(
        f"/api/matters/{matter_id}/parties",
        json={"party_type": "Petitioner", "party_name": "Keshav Karn", "party_number": 1},
    )
    assert p1.status_code == 201
    assert p1.json()["party_name"] == "Keshav Karn"

    # 3. Add Respondent
    p2 = client.post(
        f"/api/matters/{matter_id}/parties",
        json={"party_type": "Respondent", "party_name": "State of Delhi", "party_number": 1},
    )
    assert p2.status_code == 201

    # 4. List Parties
    l_res = client.get(f"/api/matters/{matter_id}/parties")
    assert l_res.status_code == 200
    assert len(l_res.json()) == 2

    # 5. Delete Party
    del_id = p1.json()["id"]
    d_res = client.delete(f"/api/matters/{matter_id}/parties/{del_id}")
    assert d_res.status_code == 200

    # 6. Verify List
    l_res2 = client.get(f"/api/matters/{matter_id}/parties")
    assert len(l_res2.json()) == 1

    app.dependency_overrides.clear()


def test_litigation_facts_and_hearings():
    """Verify adding fact timeline entries and court hearing dockets."""
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    # 1. Create Matter
    m_res = client.post("/api/matters", json={"title": "Fact & Hearing Test Matter", "module": "litigation"})
    matter_id = m_res.json()["id"]

    # 2. Add Fact
    f_res = client.post(
        f"/api/matters/{matter_id}/evidence",
        json={
            "event_date": "2026-05-10",
            "fact_summary": "Sub-lease agreement executed between parties",
            "exhibit_number": "Exhibit P-1",
        },
    )
    assert f_res.status_code == 201
    assert f_res.json()["exhibit_number"] == "Exhibit P-1"

    # 3. Add Hearing
    h_res = client.post(
        f"/api/matters/{matter_id}/hearings",
        json={
            "hearing_date": "2026-08-15",
            "purpose_of_hearing": "Arguments on Interim Stay",
            "ia_number": "IA 456/2026",
            "status": "Scheduled",
        },
    )
    assert h_res.status_code == 201
    assert h_res.json()["ia_number"] == "IA 456/2026"

    # 4. List Hearings
    hl_res = client.get(f"/api/matters/{matter_id}/hearings")
    assert hl_res.status_code == 200
    assert len(hl_res.json()) == 1

    app.dependency_overrides.clear()
