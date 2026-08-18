"""Tests for the Consulting & Legal Research Phase 1 backend:
POST /api/consulting/analyze, GET /api/consulting/matters/{id}/analyses,
and app/services/consulting.py directly.

Reuses the DummyDBClient/DummyDBTable fake (same shape/convention as
test_case_analysis.py's own — table lookups are dynamic via
store.setdefault, so no changes to that fake were needed for a new
'consulting_analyses' table name).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import consulting
from app.services.citations import CitationRecord
from app.services.llm_gateway import GenerationResult, ProviderError
from app.services.retrieval import RetrievedChunk
from tests.test_case_analysis import DummyDBClient


def get_mock_user(user_id: str = "user-123"):
    return CurrentUser(id=user_id, email=f"{user_id}@vidhidesk.com", db=DummyDBClient())


def _seed_matter(db: DummyDBClient, module: str = "consulting", user_id: str = "user-123") -> str:
    row = db.table("matters").insert(
        {"user_id": user_id, "title": "Test Consulting Matter", "module": module}
    ).execute().data[0]
    return row["id"]


_FAKE_CHUNK = RetrievedChunk(
    act="Consumer Protection Act, 2019", section_no="35", year=2019,
    chunk_text="A complaint may be filed before the District Commission.", score=1.2,
)


def _fake_generate_json_factory(parsed: dict | None, raw_text: str = "irrelevant"):
    def _fake(prompt, task_type="chat", mask_map=None, entities=None, **kwargs):
        result = GenerationResult(text=raw_text, provider="test", model="test-model", latency_ms=1, masked_prompt=prompt)
        return result, parsed

    return _fake


VALID_ANALYSIS_JSON: dict[str, Any] = {
    "applicable_law": [
        {"act": "Consumer Protection Act, 2019", "section_no": "35", "relevance": "Governs complaints for defective goods."},
        {"act": "Made Up Act", "section_no": "999", "relevance": "Should be flagged not grounded."},
    ],
    "correct_forum": {"forum_name": "District Consumer Disputes Redressal Commission", "reasoning": "Claim value within district pecuniary limit."},
    "remedies_available": [{"remedy": "Refund", "description": "Full refund of the purchase price."}],
    "limitation_period_note": "Generally two years from the date of cause of action under Section 69.",
    "case_law_references": [{"case_name": "Ramesh Kumar vs Retailer Pvt Ltd", "note": "Similar defective-goods fact pattern"}],
    "missing_information": ["Exact date of purchase not provided"],
}


def _fake_verify_citation(case_name, neutral_citation=None, court=None, year=None, *, ik_client=None, db=None):
    return CitationRecord(
        case_name=case_name, neutral_citation=None, court="NCDRC", status="verified",
        ik_doc_id="999", ik_url="https://indiankanoon.org/doc/999/", decided_on="2021-01-01",
        stale=False, from_cache=False,
    )


def _unverified_citation(case_name, neutral_citation=None, court=None, year=None, *, ik_client=None, db=None):
    return CitationRecord(
        case_name=case_name, neutral_citation=None, court=None, status="unverified",
        ik_doc_id=None, ik_url=None, decided_on=None, stale=False, from_cache=False,
    )


QUESTION = "My washing machine broke within a week and the seller refuses a refund, what law covers this?"


# --- Service-level tests -----------------------------------------------------


def test_generate_consulting_analysis_rejects_missing_matter():
    db = DummyDBClient()
    try:
        consulting.generate_consulting_analysis("nonexistent", QUESTION, None, None, [], db)
        assert False, "expected ConsultingAnalysisError"
    except consulting.ConsultingAnalysisError as exc:
        assert "not found" in str(exc).lower()


def test_generate_consulting_analysis_rejects_non_consulting_matter():
    db = DummyDBClient()
    matter_id = _seed_matter(db, module="litigation")
    try:
        consulting.generate_consulting_analysis(matter_id, QUESTION, None, None, [], db)
        assert False, "expected ConsultingAnalysisError"
    except consulting.ConsultingAnalysisError as exc:
        assert "consulting" in str(exc).lower()


def test_generate_consulting_analysis_happy_path_grounds_law_and_verifies_case_law(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)

    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _fake_verify_citation)

    result = consulting.generate_consulting_analysis(matter_id, QUESTION, None, None, [], db)

    assert result["version_no"] == 1
    assert result["question"] == QUESTION

    # statute grounding: real statute marked grounded, invented one flagged not grounded
    grounded = {e["section_no"]: e["grounded"] for e in result["applicable_law"]}
    assert grounded["35"] is True
    assert grounded["999"] is False

    # citation verifier actually ran — reference carries verified status + ik_url, not the model's raw claim
    ref = result["case_law_references"][0]
    assert ref["status"] == "verified"
    assert ref["ik_url"] == "https://indiankanoon.org/doc/999/"

    # no deterministic forum/limitation supplied -> LLM advisory fallback, explicitly flagged
    assert result["correct_forum"]["deterministic"] is False
    assert result["correct_forum"]["source"] == "llm_advisory"
    assert result["limitation_period"]["deterministic"] is False
    assert result["limitation_period"]["source"] == "llm_advisory"

    assert result["remedies_available"][0]["remedy"] == "Refund"
    assert result["missing_information"] == ["Exact date of purchase not provided"]
    assert result["model_used"] == "test/test-model"
    assert result["masked_prompt"]


def test_generate_consulting_analysis_prefers_deterministic_forum_and_limitation(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)

    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _unverified_citation)

    forum_input = {
        "recommended_forum": {
            "forum_name": "District Consumer Commission, Delhi", "court_category": "Consumer Forum",
            "territorial_basis": "Cause of action in Delhi", "pecuniary_basis": "Within threshold",
            "governing_provisions": ["Section 34, Consumer Protection Act 2019"], "confidence": "Deterministic", "assumptions": [],
        },
        "is_unambiguous": True,
    }
    limitation_input = {
        "limitation_expiry_date": "2028-01-01", "is_barred": False, "days_remaining": 500,
        "primary_article": {"article_number": "Section 69", "description": "Consumer complaint", "statutory_period_years": 2.0, "trigger_event": "cause of action"},
        "condonation_required": False, "condonation_notes": "Within limitation.",
    }

    result = consulting.generate_consulting_analysis(matter_id, QUESTION, limitation_input, forum_input, [], db)

    assert result["correct_forum"]["forum_name"] == "District Consumer Commission, Delhi"
    assert result["correct_forum"]["deterministic"] is True
    assert result["correct_forum"]["source"] == "forum_advisor"

    assert result["limitation_period"]["deterministic"] is True
    assert result["limitation_period"]["source"] == "limitation_calculator"
    assert result["limitation_period"]["is_barred"] is False
    assert result["limitation_period"]["days_remaining"] == 500


def test_generate_consulting_analysis_follow_up_increments_version_same_matter(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)

    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _unverified_citation)

    first = consulting.generate_consulting_analysis(matter_id, QUESTION, None, None, [], db)
    second = consulting.generate_consulting_analysis(matter_id, "Follow-up: what if the seller ignores my notice?", None, None, [], db)

    assert first["version_no"] == 1
    assert second["version_no"] == 2
    assert first["matter_id"] == second["matter_id"] == matter_id
    versions = consulting.list_consulting_analyses(matter_id, db)
    assert len(versions) == 2
    assert versions[0]["version_no"] == 2  # most recent first


def test_generate_consulting_analysis_handles_malformed_llm_json_without_crashing(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)

    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(None, raw_text="not json at all"))

    result = consulting.generate_consulting_analysis(matter_id, QUESTION, None, None, [], db)
    assert result["generation_warning"] is not None
    assert result["applicable_law"] == []
    assert result["case_law_references"] == []


def test_generate_consulting_analysis_propagates_provider_error(monkeypatch):
    db = DummyDBClient()
    matter_id = _seed_matter(db)
    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [])

    def _boom(*a, **k):
        raise ProviderError("all", "everything failed")

    monkeypatch.setattr(consulting, "generate_json", _boom)

    try:
        consulting.generate_consulting_analysis(matter_id, QUESTION, None, None, [], db)
        assert False, "expected ProviderError to propagate"
    except ProviderError:
        pass


# --- Router-level tests (HTTP wiring, validation, authorization) ------------


def test_analyze_endpoint_requires_auth():
    client = TestClient(app)
    resp = client.post("/api/consulting/analyze", json={"question": QUESTION})
    assert resp.status_code in (401, 422)


def test_analyze_endpoint_rejects_short_question():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": "too short"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_analyze_endpoint_rejects_whitespace_only_question():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": " " * 20})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_analyze_endpoint_rejects_empty_question():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": ""})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_analyze_endpoint_creates_new_matter_when_no_matter_id(monkeypatch):
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _fake_verify_citation)

    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": QUESTION})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["version_no"] == 1
    assert body["matter_id"]
    # the auto-created matter is a real module='consulting' matter
    matter = mock_user.db.table("matters").select("*").eq("id", body["matter_id"]).execute().data[0]
    assert matter["module"] == "consulting"
    assert matter["title"]  # derived from the question, non-empty


def test_analyze_endpoint_follow_up_reuses_same_matter(monkeypatch):
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _unverified_citation)

    client = TestClient(app)
    try:
        first = client.post("/api/consulting/analyze", json={"question": QUESTION})
        matter_id = first.json()["matter_id"]
        second = client.post("/api/consulting/analyze", json={"question": "Follow-up question about the same dispute here", "matter_id": matter_id})
        listing = client.get(f"/api/consulting/matters/{matter_id}/analyses")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["matter_id"] == matter_id
    assert second.json()["version_no"] == 2
    assert listing.status_code == 200
    assert len(listing.json()) == 2
    # only ONE matter was created across both calls
    all_matters = mock_user.db.table("matters").select("*").execute().data
    assert len(all_matters) == 1


def test_analyze_endpoint_rejects_matter_id_belonging_to_another_module(monkeypatch):
    mock_user = get_mock_user()
    matter_id = _seed_matter(mock_user.db, module="litigation")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": QUESTION, "matter_id": matter_id})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


def test_analyze_endpoint_404_for_unknown_matter_id():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": QUESTION, "matter_id": "does-not-exist"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_analyze_endpoint_denies_another_users_matter():
    """DummyDBClient has no real RLS (documented limitation shared with
    every other module's unit tests this session — see
    test_pleading_export.py / test_rera.py for the identical caveat): in
    production, RLS makes another user's matter row invisible to this
    query entirely. What IS exercised here: the router's own
    _get_matter_or_404 call path, the same code a live RLS-scoped 404
    would flow through."""
    owner = get_mock_user(user_id="user-owner")
    matter_id = _seed_matter(owner.db, module="consulting", user_id="user-owner")

    other = get_mock_user(user_id="user-other")
    app.dependency_overrides[get_current_user] = lambda: other
    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": QUESTION, "matter_id": matter_id})
    finally:
        app.dependency_overrides.clear()
    # other's DummyDBClient is a separate empty store -> matter genuinely not found
    assert resp.status_code == 404


def test_list_analyses_requires_auth():
    client = TestClient(app)
    resp = client.get("/api/consulting/matters/does-not-exist/analyses")
    assert resp.status_code in (401, 422)


def test_list_analyses_404_for_unknown_matter():
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    try:
        resp = client.get("/api/consulting/matters/does-not-exist/analyses")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_analyze_endpoint_happy_path_full_response_shape(monkeypatch):
    mock_user = get_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    monkeypatch.setattr(consulting, "hybrid_retrieve", lambda *a, **k: [_FAKE_CHUNK])
    monkeypatch.setattr(consulting, "generate_json", _fake_generate_json_factory(VALID_ANALYSIS_JSON))
    monkeypatch.setattr(consulting, "verify_citation", _fake_verify_citation)

    client = TestClient(app)
    try:
        resp = client.post("/api/consulting/analyze", json={"question": QUESTION})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["applicable_law"][0]["grounded"] is True
    assert body["case_law_references"][0]["status"] == "verified"
    assert body["notice"].lower().startswith("ai-generated")
