"""RERA Phase 2H: regression coverage for the PII-unmasking boundary in
draft generation.

Root cause (confirmed by forensic trace + a real synthetic-data repro,
see the Phase 2H report): `fixed_boilerplate` clauses render their
`current_text` Jinja template against `masked_form_data`
(app/services/contracts.py's Phase 1 loop) -- correct, since that's what
must go out if an llm_fillable clause's prompt references the same field,
but the rendered fixed_boilerplate text itself never went through
`unmask_text()`. An `llm_fillable` clause's output *does* get unmasked,
but only inside `llm_gateway.generate()` (pii_mask.unmask_text calls at
llm_gateway.py:497,531) -- an entirely separate code path that
fixed_boilerplate never touches. Net effect: any free-text field
(`text`/`textarea`, per `_mask_form_data`'s schema-aware masking)
interpolated into a fixed_boilerplate clause via `{{ field }}` retained
its internal placeholder token (e.g. `PARTY_D`, `ADDR_2`) verbatim in the
final document -- confirmed live against a real generated Mortgage Deed
in Phase 2G's own E2E validation.

Fix: one authoritative unmask boundary in contracts.py's Phase 3 assembly
loop (`generate_draft`), applied uniformly to every clause's `rendered`
text regardless of clause_type, immediately before it's appended to
`final_clause_texts` -- the single list that feeds both the DocxTemplate
subdocument (the actual .docx) and `full_text` (the API response). This
guarantees no placeholder can survive into any downstream consumer,
without touching what's sent to the LLM (prompts are already built and
sent, in Phase 1/2, before this loop runs) and without weakening masking
itself (mask_text/_mask_form_data are untouched).

Runs against an in-memory FakeDB (same convention as test_rera.py /
test_draft_text_endpoint.py) with a real, committed .docx skeleton
(templates/contracts/nda.docx) for genuine docxtpl/python-docx rendering
-- never touches real Supabase. LLM calls are faked (no network) except
where noted; synthetic test data only, no real names/addresses/PAN/
Aadhaar/phone numbers anywhere in this file.
"""

from __future__ import annotations

import re
import uuid

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import contracts
from app.services.llm_gateway import GenerationResult
from app.services.model_pool import Capability, ModelSpec
from app.services.pii_mask import InMemoryMaskStore

# Phase 4.5 model-pool selection stand-in (same convention as
# test_contracts.py's FAKE_SELECTED_MODEL) -- keeps this file
# environment-independent, no real provider API keys required.
FAKE_SELECTED_MODEL = ModelSpec(
    provider="gemini", model="gemini-2.5-flash",
    capability=Capability.LEGAL_DRAFTING, priority=1, enabled=True,
)

REPO_ROOT = contracts.REPO_ROOT
PLACEHOLDER_RE = re.compile(r"\b[A-Z]+_[A-Z0-9]+\b")


# --- Fake DB (same shape/convention as test_rera.py's FakeDB) --------------


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: dict[str, object] = {}
        self._order_col = None
        self._order_desc = False
        self._limit = None

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False, **_k):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        matches = [r for r in self.table.rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self._order_col:
            matches = sorted(matches, key=lambda r: r.get(self._order_col) or 0, reverse=self._order_desc)
        if self._limit:
            matches = matches[: self._limit]
        if self.op == "select":
            return _FakeResponse(matches)
        if self.op == "update":
            for r in matches:
                r.update(self.payload)
            return _FakeResponse(matches)
        raise AssertionError(f"unsupported op {self.op}")


class _FakeInsertResult:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return _FakeResponse(self._rows)


class _FakeTable:
    def __init__(self, name):
        self.name = name
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self, "select")

    def update(self, payload):
        return _FakeQuery(self, "update", payload)

    def insert(self, record):
        items = record if isinstance(record, list) else [record]
        inserted = []
        for item in items:
            row = dict(item)
            row.setdefault("id", str(uuid.uuid4()))
            self.rows.append(row)
            inserted.append(row)
        return _FakeInsertResult(inserted)


class FakeDB:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable(name))


# --- Shared fixtures ---------------------------------------------------------

REAL_SKELETON = "templates/contracts/nda.docx"  # existing, committed, real .docx

# Two clauses: one fixed_boilerplate that interpolates a free-text field
# (the exact pattern that leaked placeholders), one llm_fillable (regression
# guard for the already-working path). Both reference the same masked
# field, and a second field, to also cover "multiple distinct values" and
# "repeated occurrence of the same value".
CLAUSES = [
    {
        "clause_key": "schedule_fixed", "display_order": 1, "clause_type": "fixed_boilerplate",
        "applicable_condition": None, "heading": "Schedule",
        "source_text": "Property: {{ property_description }}. Secondary owner reference: {{ secondary_owner_note }}.",
        "current_text": "Property: {{ property_description }}. Secondary owner reference: {{ secondary_owner_note }}.",
    },
    {
        "clause_key": "recitals_llm", "display_order": 2, "clause_type": "llm_fillable",
        "applicable_condition": None, "heading": "Recitals",
        "source_text": "Draft recitals mentioning: {{ property_description }}",
        "current_text": "Draft recitals mentioning: {{ property_description }}",
    },
]

SCHEMA = {
    "fields": [
        {"key": "party_a_name", "type": "text"},
        {"key": "party_a_address", "type": "text"},
        {"key": "party_b_name", "type": "text"},
        {"key": "party_b_address", "type": "text"},
        {"key": "property_description", "type": "textarea"},
        {"key": "secondary_owner_note", "type": "textarea"},
    ]
}

# Synthetic-only values. property_description and secondary_owner_note both
# deliberately re-mention "Ramesh Kumar Sharma" (Synthetic Test Party) --
# the SAME real value in two places -- to exercise "repeated occurrence of
# the same masked value" (same placeholder both times, per MaskMap.
# get_or_assign's memoization). property_description and party_a_name each
# carry a distinct synthetic value too, for "multiple distinct values".
FORM_DATA = {
    "party_a_name": "Ramesh Kumar Sharma (Synthetic Test Party A)",
    "party_a_address": "1 Synthetic Test Road, Delhi",
    "party_b_name": "Sunita Devi Verma (Synthetic Test Party B)",
    "party_b_address": "2 Synthetic Test Road, Mumbai",
    "property_description": "Plot 99, Synthetic Test Layout, owned by Ramesh Kumar Sharma (synthetic test data).",
    "secondary_owner_note": "Co-owned historically with Ramesh Kumar Sharma per synthetic test records.",
}


def _seed_template(db: FakeDB, clauses=None) -> str:
    template_id = "template-pii-boundary"
    db.table("templates").rows.append({
        "id": template_id,
        "name": "PII Boundary Test Template",
        "category": "rera",
        "docx_path": REAL_SKELETON,
        "review_status": "beta",
        "schema_json": SCHEMA,
    })
    for clause in clauses if clauses is not None else CLAUSES:
        db.table("template_clauses").rows.append(
            {"id": f"clause-{clause['clause_key']}", "template_id": template_id, **clause, "review_status": "unreviewed"}
        )
    return template_id


def _seed_matter(db: FakeDB, matter_id="matter-pii-boundary", user_id="user-1") -> str:
    db.table("matters").rows.append({"id": matter_id, "user_id": user_id, "client_name": "Synthetic Test Client"})
    return matter_id


# Deliberately bears no textual resemblance to any FORM_DATA value (no
# shared words/substrings) -- this is what makes every assertion below
# unambiguous: text found in the Recitals section can only have come from
# this constant, and text found in the Schedule section can only have
# come from the fixed_boilerplate clause's own Jinja rendering. An
# earlier version of this file's fake echoed property_description back
# into the canned LLM text, which accidentally made a broken
# fixed_boilerplate-unmasking assertion pass anyway (the LLM section
# leaked the real value on its own, masking -- no pun intended -- the
# actual defect); this constant exists specifically to prevent that.
LLM_CANNED_TEXT = "LLM-GENERATED RECITALS: independent synthetic clause text, unrelated to any masked field."


def _fake_generate(monkeypatch, canned_text=LLM_CANNED_TEXT):
    """Mirrors what llm_gateway.generate() actually contracts to return:
    already-unmasked text (its own unmask_text() call has already run) --
    this is deliberately NOT a masked value, to regression-guard that the
    new boundary doesn't corrupt an already-correct llm_fillable result."""

    def _fake(prompt, **kwargs):
        return GenerationResult(
            text=canned_text,
            provider="gemini", model="gemini-2.5-flash", latency_ms=10,
            masked_prompt=prompt,
        )

    monkeypatch.setattr(contracts, "generate", _fake)
    monkeypatch.setattr(contracts, "select_model", lambda capability, settings=None: FAKE_SELECTED_MODEL)


@pytest.fixture(autouse=True)
def _use_in_memory_mask_store(monkeypatch):
    """generate_draft() constructs SupabaseMaskStore(db) internally --
    swap it for the in-memory store so this test never touches real
    Supabase, matching the existing test_contracts.py convention for the
    same constraint (docs/30_Implementation/Backlog.md's "never let unit
    tests write to production" rule)."""
    store = InMemoryMaskStore()

    class _Adapter:
        def __init__(self, _db):
            pass

        def load(self, matter_id):
            return store.load(matter_id)

        def save(self, mask_map):
            return store.save(mask_map)

    monkeypatch.setattr(contracts, "SupabaseMaskStore", _Adapter)
    return store


def _generate_and_read_docx(db: FakeDB, matter_id: str, template_id: str, form_data: dict):
    result = contracts.generate_draft(matter_id, template_id, form_data, db=db)
    output_path = REPO_ROOT / result.docx_path
    assert output_path.exists()
    doc = Document(str(output_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    return result, full_text, output_path


def _schedule_section(full_text: str) -> str:
    """Isolates the fixed_boilerplate "1. Schedule" clause's own rendered
    text (up to the next clause heading) -- the exact, and only, place a
    masked-then-unmasked value from this fixture can appear. Scoping
    assertions to this section (rather than searching `full_text` as a
    whole) is what makes each assertion below unambiguous."""
    start = full_text.index("1. Schedule")
    end = full_text.index("2. Recitals", start)
    return full_text[start:end]


# --- 1. Fixed boilerplate with masked values produces correct final output -


def test_fixed_boilerplate_masked_value_restored_to_original(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        schedule = _schedule_section(full_text)
        assert "Plot 99, Synthetic Test Layout, owned by Ramesh Kumar Sharma (synthetic test data)." in schedule
        assert PLACEHOLDER_RE.findall(schedule) == [], f"placeholder(s) still present in Schedule clause: {schedule!r}"
        assert "Plot 99, Synthetic Test Layout, owned by Ramesh Kumar Sharma (synthetic test data)." in result.full_text
    finally:
        output_path.unlink(missing_ok=True)


# --- 2. LLM-generated clause behavior remains correct -----------------------


def test_llm_fillable_clause_output_remains_correct_and_unaffected(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        assert LLM_CANNED_TEXT in full_text
        assert LLM_CANNED_TEXT in result.full_text
        assert result.clause_fills[0].generated_text == LLM_CANNED_TEXT
    finally:
        output_path.unlink(missing_ok=True)


# --- 3. Internal placeholder tokens do not appear in final output ----------


def test_no_placeholder_tokens_survive_in_final_output(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        leaked = PLACEHOLDER_RE.findall(full_text)
        assert leaked == [], f"placeholder token(s) leaked into final DOCX: {leaked}"
        leaked_api = PLACEHOLDER_RE.findall(result.full_text)
        assert leaked_api == [], f"placeholder token(s) leaked into API full_text: {leaked_api}"
    finally:
        output_path.unlink(missing_ok=True)


# --- 4. Multiple distinct masked values are restored correctly -------------


def test_multiple_distinct_masked_values_all_restored(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        # property_description and secondary_owner_note are distinct
        # values, both interpolated into the same fixed_boilerplate clause.
        schedule = _schedule_section(full_text)
        assert "Plot 99, Synthetic Test Layout" in schedule
        assert "Co-owned historically with Ramesh Kumar Sharma per synthetic test records." in schedule
        assert PLACEHOLDER_RE.findall(schedule) == []
    finally:
        output_path.unlink(missing_ok=True)


# --- 5. Repeated occurrence of the same masked value ------------------------


def test_repeated_occurrence_of_same_masked_value_restored_consistently(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        # "Ramesh Kumar Sharma" appears in BOTH property_description and
        # secondary_owner_note, within the one fixed_boilerplate clause --
        # same real value, necessarily the same placeholder both times
        # (MaskMap.get_or_assign memoizes by normalized value), so both
        # occurrences must restore identically. Scoped to the Schedule
        # section specifically -- party_a_name's own (always-unmasked,
        # top-level context) occurrences elsewhere in the document are a
        # separate thing this test isn't about.
        schedule = _schedule_section(full_text)
        occurrences = schedule.count("Ramesh Kumar Sharma")
        assert occurrences == 2, f"expected exactly 2 restored occurrences in the Schedule clause, found {occurrences} in: {schedule!r}"
        assert PLACEHOLDER_RE.findall(schedule) == []
    finally:
        output_path.unlink(missing_ok=True)


# --- 6. Mixed fixed_boilerplate + llm_fillable document --------------------


def test_mixed_fixed_and_llm_fillable_clauses_produce_correct_final_result(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)  # CLAUSES already has one of each type
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        assert "1. Schedule" in full_text
        assert "2. Recitals" in full_text
        schedule = _schedule_section(full_text)
        assert "Plot 99, Synthetic Test Layout, owned by Ramesh Kumar Sharma (synthetic test data)." in schedule
        assert LLM_CANNED_TEXT in full_text
        assert PLACEHOLDER_RE.findall(full_text) == []
    finally:
        output_path.unlink(missing_ok=True)


# --- 7. DOCX content contains the expected synthetic values ----------------


def test_docx_file_on_disk_contains_expected_synthetic_values(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, _full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        # Re-open independently (not reusing the helper's already-open
        # Document) to prove it's genuinely persisted to disk, not just an
        # in-memory artifact of generation.
        doc = Document(str(output_path))
        persisted_text = "\n".join(p.text for p in doc.paragraphs)
        schedule = _schedule_section(persisted_text)
        assert "Ramesh Kumar Sharma" in schedule
        assert "Plot 99, Synthetic Test Layout" in schedule
        assert PLACEHOLDER_RE.findall(persisted_text) == []
    finally:
        output_path.unlink(missing_ok=True)


# --- 8. GET /api/drafts/{id}/text returns correct final content ------------


def _make_client(fake_db, user_id="user-1"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user_id, email="nitesh@example.com", db=fake_db, organization_id="org-test-1"
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def test_draft_text_endpoint_returns_unmasked_content_for_generated_draft(monkeypatch):
    db = FakeDB()
    template_id = _seed_template(db)
    matter_id = _seed_matter(db)
    _fake_generate(monkeypatch)

    result, _full_text, output_path = _generate_and_read_docx(db, matter_id, template_id, FORM_DATA)
    try:
        client = _make_client(db)
        resp = client.get(f"/api/drafts/{result.draft_version_id}/text", headers={"Authorization": "Bearer test-token"})

        assert resp.status_code == 200
        body = resp.json()
        schedule = _schedule_section(body["full_text"])
        assert "Ramesh Kumar Sharma" in schedule
        assert "Plot 99, Synthetic Test Layout" in schedule
        assert PLACEHOLDER_RE.findall(body["full_text"]) == []
    finally:
        output_path.unlink(missing_ok=True)
