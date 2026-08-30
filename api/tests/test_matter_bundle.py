"""Tests for app/services/matter_bundle.py -- pure DB-read assembly.
Every category is either populated or explicitly listed in `missing`;
these tests prove both halves, plus the exclude_hearing_id behavior and
chronology sort order (undated facts sort last, mirroring
case_analysis.py's identical convention)."""

from __future__ import annotations

import pytest

from app.services.matter_bundle import MatterBundleError, assemble_matter_bundle
from tests.test_platform import FakeServiceClient


def _matter(id_="m1"):
    return {"id": id_, "organization_id": "org-1", "title": "Test Matter", "module": "litigation"}


def test_matter_not_found_raises():
    fake = FakeServiceClient({"matters": []})
    with pytest.raises(MatterBundleError):
        assemble_matter_bundle("nope", fake)


def test_all_categories_missing_when_nothing_recorded():
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_pleading_drafts": [],
            "hearings": [],
            "orders": [],
            "litigation_case_analyses": [],
        }
    )
    bundle = assemble_matter_bundle("m1", fake)

    assert "No parties recorded for this matter." in bundle.missing
    assert "No facts/chronology recorded for this matter." in bundle.missing
    assert "No composed pleading exists yet for this matter." in bundle.missing
    assert "No prior hearing history recorded for this matter." in bundle.missing
    assert "No orders on record for this matter." in bundle.missing
    assert "No verified case-law citations linked to this matter yet." in bundle.missing


def test_populated_bundle_has_no_spurious_missing_entries():
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [{"id": "p1", "matter_id": "m1", "party_type": "Petitioner", "party_number": 1, "party_name": "A"}],
            "litigation_facts_evidence": [{"id": "f1", "matter_id": "m1", "event_date": "2026-01-01", "fact_summary": "Something happened"}],
            "litigation_pleading_drafts": [{"id": "pd1", "matter_id": "m1", "version_no": 1, "composed_sections": [], "created_at": "2026-01-01T00:00:00Z"}],
            "hearings": [{"id": "h1", "matter_id": "m1", "hearing_at": "2026-01-15T00:00:00Z", "arguments_made": "We argued X", "notes": "lawyer note"}],
            "orders": [{"id": "o1", "matter_id": "m1", "order_date": "2026-01-10", "raw_text": "Order text", "ai_extracted_directions": []}],
            "litigation_case_analyses": [{"id": "ca1", "matter_id": "m1", "version_no": 1, "possible_precedents": [{"case_name": "X v Y", "status": "verified", "note": "n"}]}],
        }
    )
    bundle = assemble_matter_bundle("m1", fake)

    assert bundle.missing == []
    assert len(bundle.parties) == 1
    assert len(bundle.chronology) == 1
    assert len(bundle.pleadings) == 1
    assert len(bundle.hearings) == 1
    assert len(bundle.orders) == 1
    assert len(bundle.verified_citations) == 1
    assert bundle.lawyer_notes == ["lawyer note"]


def test_exclude_hearing_id_omits_that_hearing_from_prior_hearings():
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_pleading_drafts": [],
            "hearings": [
                {"id": "h1", "matter_id": "m1", "hearing_at": "2026-01-15T00:00:00Z"},
                {"id": "h2", "matter_id": "m1", "hearing_at": "2026-02-15T00:00:00Z"},
            ],
            "orders": [],
            "litigation_case_analyses": [],
        }
    )
    bundle = assemble_matter_bundle("m1", fake, exclude_hearing_id="h2")
    ids = [h["id"] for h in bundle.hearings]
    assert "h2" not in ids
    assert "h1" in ids


def test_chronology_sorts_undated_facts_last():
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [],
            "litigation_facts_evidence": [
                {"id": "f1", "matter_id": "m1", "event_date": None, "fact_summary": "undated"},
                {"id": "f2", "matter_id": "m1", "event_date": "2026-01-01", "fact_summary": "early"},
                {"id": "f3", "matter_id": "m1", "event_date": "2026-06-01", "fact_summary": "late"},
            ],
            "litigation_pleading_drafts": [],
            "hearings": [],
            "orders": [],
            "litigation_case_analyses": [],
        }
    )
    bundle = assemble_matter_bundle("m1", fake)
    summaries = [f["fact_summary"] for f in bundle.chronology]
    assert summaries == ["early", "late", "undated"]


def test_bundle_does_not_fetch_or_expose_draft_versions():
    """Iter 4/5 architecture decision: draft_versions is a Contracts-module
    artifact (docx_path/template_id) that document_composer.py explicitly
    documents Litigation never writes to -- it is deliberately excluded
    from the bundle, not merely unused. Seeding a draft_versions row here
    and asserting it never surfaces proves the removal is a real decision,
    not just an absent fixture key coincidentally matching."""
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [],
            "litigation_facts_evidence": [],
            "litigation_pleading_drafts": [],
            "hearings": [],
            "orders": [],
            "litigation_case_analyses": [],
            "draft_versions": [{"id": "dv1", "matter_id": "m1", "template_id": "t1", "version_no": 1, "docx_path": "x.docx"}],
        }
    )
    bundle = assemble_matter_bundle("m1", fake)
    assert not hasattr(bundle, "documents")
    assert "docx_path" not in bundle.as_prompt_text()
    assert "dv1" not in bundle.as_prompt_text()


def test_as_prompt_text_includes_key_markers_and_does_not_crash():
    fake = FakeServiceClient(
        {
            "matters": [_matter()],
            "litigation_parties": [{"id": "p1", "matter_id": "m1", "party_type": "Petitioner", "party_number": 1, "party_name": "A"}],
            "litigation_facts_evidence": [],
            "litigation_pleading_drafts": [],
            "hearings": [],
            "orders": [{"id": "o1", "matter_id": "m1", "order_date": "2026-01-10", "raw_text": "Comply within 30 days", "ai_extracted_directions": [{"direction": "File reply", "deadline": "2026-02-10", "complied": False}]}],
            "litigation_case_analyses": [],
        }
    )
    bundle = assemble_matter_bundle("m1", fake)
    text = bundle.as_prompt_text()
    assert "MATTER: Test Matter" in text
    assert "[Order dated 2026-01-10]" in text
    assert "Direction: File reply" in text
    assert "EXPLICITLY MISSING" in text
