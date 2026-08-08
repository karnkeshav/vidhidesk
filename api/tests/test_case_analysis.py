from __future__ import annotations

from typing import Any

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import case_analysis
from app.services.citations import CitationRecord
from app.services.llm_gateway import GenerationResult, ProviderError
from app.services.retrieval import RetrievedChunk


# --- Fake DB (same shape/convention as test_litigation.py's DummyDBClient) ---

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

    def order(self, column: str, desc: bool = False, **kwargs):
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, count: int):
        self._limit = count
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
        if getattr(self, "_order_col", None):
            filtered = sorted(filtered, key=lambda r: r.get(self._order_col) or 0, reverse=getattr(self, "_order_desc", False))
        if getattr(self, "_limit", None):
            filtered = filtered[: self._limit]
        return DummyResp(filtered)


class DummyDBClient:
    def __init__(self):
        self.store: dict[str, list[dict]] = {
            "matters": [],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_hearings": [],
            "litigation_case_analyses": [],
            "pii_masks": [],
        }

    def table(self, name: str):
        return DummyDBTable(name, self.store)


def get_mock_user():
    return CurrentUser(id="user-123", email="advocate@vidhidesk.com", db=DummyDBClient())


def _seed_matter(db: DummyDBClient, module: str = "litigation") -> str:
    row = db.table("matters").insert(
        {"user_id": "user-123", "title": "Test Matter", "module": module, "jurisdiction_state": "Delhi"}
    ).execute().data[0]
    return row["id"]


def _seed_party(db: DummyDBClient, matter_id: str, party_type="Petitioner"):
    db.table("litigation_parties").insert(
        {"matter_id": matter_id, "party_type": party_type, "party_name": "Ramesh Kumar", "party_number": 1}
    ).execute()


def _seed_fact(db: DummyDBClient, matter_id: str, **overrides):
    row = {
        "matter_id": matter_id,
        "event_date": "2026-01-15",
        "fact_summary": "Agreement executed between the parties",
        "exhibit_number": None,
        "document_title": None,
        "relevance_notes": None,
        "file_url": None,
    }
    row.update(overrides)
    db.table("litigation_facts_evidence").insert(row).execute()


_FAKE_CHUNK = RetrievedChunk(act="Indian Contract Act, 1872", section_no="73", year=1872, chunk_text="Compensation for loss or damage caused by breach of contract.", score=1.5)


def _fake_generate_factory(json_text: str):
    def _fake_generate(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        return GenerationResult(text=json_text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt)

    return _fake_generate


VALID_JSON = """{
  "matter_summary": "A breach of contract dispute between Ramesh Kumar and the respondent.",
  "missing_information": ["Signed copy of the agreement not yet on file"],
  "possible_causes_of_action": [
    {
      "title": "Breach of Contract",
      "description": "The respondent failed to perform under the agreement.",
      "supporting_facts": ["Agreement executed between the parties"],
      "statutes_relied_upon": [{"act": "Indian Contract Act, 1872", "section_no": "73"}, {"act": "Made Up Act", "section_no": "999"}]
    }
  ],
  "potential_risks": [{"risk": "Limitation may run out", "severity": "High", "mitigation": "File promptly"}],
  "evidence_gaps": ["No proof of delivery"],
  "recommended_next_steps": ["Send a legal notice"],
  "possible_precedents": [{"case_name": "Ramesh Kumar vs State of Delhi", "note": "Similar fact pattern"}]
}"""


def test_generate_case_analysis_requires_parties_and_facts(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    try:
        case_analysis.generate_case_analysis(matter_id, None, None, db)
        assert False, "expected CaseAnalysisError"
    except case_analysis.CaseAnalysisError as exc:
        assert "party" in str(exc).lower()

    _seed_party(db, matter_id)
    try:
        case_analysis.generate_case_analysis(matter_id, None, None, db)
        assert False, "expected CaseAnalysisError"
    except case_analysis.CaseAnalysisError as exc:
        assert "fact" in str(exc).lower()


def test_generate_case_analysis_rejects_non_litigation_matter():
    db = DummyDBClient()
    matter_id = _seed_matter(db, module="contracts")
    try:
        case_analysis.generate_case_analysis(matter_id, None, None, db)
        assert False, "expected CaseAnalysisError"
    except case_analysis.CaseAnalysisError as exc:
        assert "litigation" in str(exc).lower()


def test_generate_case_analysis_happy_path_grounds_statutes_and_verifies_precedents(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id, "Petitioner")
    _seed_party(db, matter_id, "Respondent")
    _seed_fact(db, matter_id, exhibit_number="Exhibit P-1", file_url="https://storage/e1.pdf")
    _seed_fact(db, matter_id, event_date="2026-02-01", fact_summary="Breach occurred")  # no exhibit, no file -> gap

    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(case_analysis, "generate", _fake_generate_factory(VALID_JSON))
    monkeypatch.setattr(
        case_analysis,
        "verify_citation",
        lambda case_name, db=None: CitationRecord(
            case_name=case_name, neutral_citation=None, court="Delhi HC", status="verified",
            ik_doc_id="12345", ik_url="https://indiankanoon.org/doc/12345/", decided_on="2020-01-01",
            stale=False, from_cache=False,
        ),
    )

    result = case_analysis.generate_case_analysis(matter_id, limitation=None, forum=None, db=db)

    assert result["version_no"] == 1
    assert "breach of contract" in result["matter_summary"].lower()
    # deterministic chronological_facts are sorted and always present regardless of LLM output
    assert len(result["chronological_facts"]) == 2
    assert result["chronological_facts"][0]["event_date"] == "2026-01-15"
    # deterministic evidence gap seed present even though only one fact lacks a file
    assert any("no attached exhibit" in g.lower() for g in result["evidence_gaps"])
    # deterministic missing-information seeds (no forum/limitation supplied) present
    assert any("forum" in m.lower() for m in result["missing_information"])
    assert any("limitation" in m.lower() for m in result["missing_information"])

    # statute grounding: real statute marked grounded, invented one flagged not grounded
    refs = result["possible_causes_of_action"][0]["statutes_relied_upon"]
    grounded = {r["section_no"]: r["grounded"] for r in refs}
    assert grounded["73"] is True
    assert grounded["999"] is False

    # citation verifier actually ran — precedent carries verified status + ik_url, not the model's raw claim
    precedent = result["possible_precedents"][0]
    assert precedent["status"] == "verified"
    assert precedent["ik_url"] == "https://indiankanoon.org/doc/12345/"

    assert result["model_used"] == "test/test-model"
    assert result["masked_prompt"]


def test_generate_case_analysis_regeneration_increments_version(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    _seed_fact(db, matter_id)

    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(case_analysis, "generate", _fake_generate_factory(VALID_JSON))
    monkeypatch.setattr(
        case_analysis, "verify_citation",
        lambda case_name, db=None: CitationRecord(case_name=case_name, neutral_citation=None, court=None, status="unverified", ik_doc_id=None, ik_url=None, decided_on=None, stale=False, from_cache=False),
    )

    first = case_analysis.generate_case_analysis(matter_id, None, None, db)
    second = case_analysis.generate_case_analysis(matter_id, None, None, db)
    assert first["version_no"] == 1
    assert second["version_no"] == 2
    assert len(case_analysis.list_case_analyses(matter_id, db)) == 2


def test_generate_case_analysis_handles_malformed_llm_json_without_crashing(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    _seed_fact(db, matter_id)

    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(case_analysis, "generate", _fake_generate_factory("not json at all, sorry"))

    result = case_analysis.generate_case_analysis(matter_id, None, None, db)
    assert result["generation_warning"] is not None
    assert "not json at all" in result["matter_summary"].lower()
    assert result["possible_causes_of_action"] == []  # degrades safely, doesn't fabricate structure


def test_generate_case_analysis_extracts_json_from_markdown_fenced_response(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    _seed_fact(db, matter_id)

    fenced = f"```json\n{VALID_JSON}\n```"
    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(case_analysis, "generate", _fake_generate_factory(fenced))
    monkeypatch.setattr(
        case_analysis, "verify_citation",
        lambda case_name, db=None: CitationRecord(case_name=case_name, neutral_citation=None, court=None, status="unverified", ik_doc_id=None, ik_url=None, decided_on=None, stale=False, from_cache=False),
    )

    result = case_analysis.generate_case_analysis(matter_id, None, None, db)
    assert result["generation_warning"] is None
    assert "breach of contract" in result["matter_summary"].lower()


def test_generate_case_analysis_propagates_provider_error_when_all_llm_providers_fail(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    _seed_party(db, matter_id)
    _seed_fact(db, matter_id)

    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [])

    def _boom(*a, **k):
        raise ProviderError("all", "everything failed")

    monkeypatch.setattr(case_analysis, "generate", _boom)

    try:
        case_analysis.generate_case_analysis(matter_id, None, None, db)
        assert False, "expected ProviderError to propagate"
    except ProviderError:
        pass


# --- Router-level tests (endpoint wiring, HTTP status translation) ----------

def test_case_analysis_endpoint_400_when_preconditions_unmet():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    from fastapi.testclient import TestClient

    client = TestClient(app)
    m_res = client.post("/api/matters", json={"title": "Empty Matter", "module": "litigation"})
    matter_id = m_res.json()["id"]

    res = client.post(f"/api/matters/{matter_id}/case-analysis", json={})
    app.dependency_overrides.clear()

    assert res.status_code == 400
    assert "party" in res.json()["detail"].lower()


def test_case_analysis_endpoint_happy_path(monkeypatch):
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    from fastapi.testclient import TestClient

    monkeypatch.setattr(case_analysis, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(case_analysis, "generate", _fake_generate_factory(VALID_JSON))
    monkeypatch.setattr(
        case_analysis, "verify_citation",
        lambda case_name, db=None: CitationRecord(case_name=case_name, neutral_citation=None, court=None, status="unverified", ik_doc_id=None, ik_url=None, decided_on=None, stale=False, from_cache=False),
    )

    client = TestClient(app)
    m_res = client.post("/api/matters", json={"title": "Wired Matter", "module": "litigation"})
    matter_id = m_res.json()["id"]
    client.post(f"/api/matters/{matter_id}/parties", json={"party_type": "Petitioner", "party_name": "Ramesh Kumar", "party_number": 1})
    client.post(f"/api/matters/{matter_id}/evidence", json={"fact_summary": "Agreement executed"})

    res = client.post(
        f"/api/matters/{matter_id}/case-analysis",
        json={
            "limitation": {
                "limitation_expiry_date": "2029-01-15", "is_barred": False, "days_remaining": 900,
                "primary_article": {"article_number": "Article 55", "description": "Breach of contract", "statutory_period_years": 3.0, "trigger_event": "breach"},
                "condonation_required": False, "condonation_notes": "Within limitation.",
            },
            "forum": {
                "recommended_forum": {
                    "forum_name": "District Court, Delhi", "court_category": "District Courts",
                    "territorial_basis": "Cause of action in Delhi", "pecuniary_basis": "Within threshold",
                    "governing_provisions": ["Section 15 CPC"], "confidence": "Deterministic", "assumptions": [],
                },
                "is_unambiguous": True,
            },
        },
    )
    list_res = client.get(f"/api/matters/{matter_id}/case-analysis")
    app.dependency_overrides.clear()

    assert res.status_code == 201
    body = res.json()
    assert body["version_no"] == 1
    assert body["jurisdiction_summary"]["recommended_forum"]["forum_name"] == "District Court, Delhi"
    assert body["limitation_summary"]["is_barred"] is False
    # supplying limitation+forum removes those two deterministic gap seeds
    assert not any("run the limitation calculator" in m.lower() for m in body["missing_information"])
    assert not any("run the forum advisor" in m.lower() for m in body["missing_information"])
    assert body["notice"].lower().startswith("ai-generated")

    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
