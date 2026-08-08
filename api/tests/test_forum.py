from __future__ import annotations

from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.main import app
from app.services.forum import determine_forum


def test_forum_delhi_pecuniary_boundary_high_court():
    """Verify Delhi suit > 2 Crores is routed to High Court Ordinary Original Civil Jurisdiction."""
    res = determine_forum(
        suit_type="Civil Suit",
        claim_value_inr=25_000_000.0,  # 2.5 Crores
        jurisdiction_state="Delhi",
    )

    rec = res["recommended_forum"]
    assert rec["court_category"] == "High Court"
    assert "High Court of Delhi" in rec["forum_name"]
    assert "Section 5(2) Delhi High Court Act" in rec["governing_provisions"][0]
    assert res["is_unambiguous"] is True


def test_forum_delhi_pecuniary_boundary_district_court():
    """Verify Delhi suit between 20 Lakhs and 2 Crores is routed to District Judge."""
    res = determine_forum(
        suit_type="Civil Suit",
        claim_value_inr=5_000_000.0,  # 50 Lakhs
        jurisdiction_state="Delhi",
    )

    rec = res["recommended_forum"]
    assert rec["court_category"] == "District Courts"
    assert "District Court" in rec["forum_name"]


def test_forum_property_dispute_section_16_cpc():
    """Verify property dispute enforces property location under Section 16 CPC."""
    res = determine_forum(
        suit_type="Property Dispute",
        claim_value_inr=1_500_000.0,
        jurisdiction_state="Karnataka",
        defendant_residence_state="Maharashtra",
        property_location_state="Karnataka",
    )

    rec = res["recommended_forum"]
    assert "Section 16(a)-(d), Code of Civil Procedure, 1908" in rec["governing_provisions"]
    assert "Immovable property situated within local limits" in rec["territorial_basis"]


def test_forum_commercial_courts_act():
    """Verify commercial dispute > 3 Lakhs recommends Commercial Court."""
    res = determine_forum(
        suit_type="Commercial Dispute",
        claim_value_inr=10_000_000.0,
        jurisdiction_state="Delhi",
    )

    options = res["viable_options"]
    comm_option = next((opt for opt in options if opt["court_category"] == "Commercial Court"), None)
    assert comm_option is not None
    assert "Commercial Courts Act, 2015" in comm_option["governing_provisions"][0]


def test_forum_commercial_courts_act_recommends_commercial_court_not_general_civil():
    """Regression for TICKET-6: a Commercial Dispute meeting the Commercial
    Courts Act, 2015 threshold (>= INR 3 Lakhs) must have the Commercial
    Court itself as recommended_forum, not the general civil court. The
    general civil option previously overwrote it in viable_options[0]
    regardless of the Commercial Court's presence."""
    res = determine_forum(
        suit_type="Commercial Dispute",
        claim_value_inr=300_000.0,  # exactly at the threshold
        jurisdiction_state="Delhi",
    )

    rec = res["recommended_forum"]
    assert rec["court_category"] == "Commercial Court"
    assert "Commercial Court" in rec["forum_name"]


def test_forum_commercial_dispute_below_threshold_recommends_general_civil():
    """A Commercial Dispute below the INR 3 Lakh threshold has no Commercial
    Court option at all — the general civil recommendation is correct here,
    confirming the TICKET-6 fix didn't overreach to disputes that never
    qualified for a Commercial Court in the first place."""
    res = determine_forum(
        suit_type="Commercial Dispute",
        claim_value_inr=200_000.0,
        jurisdiction_state="Delhi",
    )

    rec = res["recommended_forum"]
    assert rec["court_category"] != "Commercial Court"
    assert not any(opt["court_category"] == "Commercial Court" for opt in res["viable_options"])


def test_forum_rera_dispute():
    """Verify RERA real estate dispute recommends RERA tribunal."""
    res = determine_forum(
        suit_type="RERA",
        claim_value_inr=8_000_000.0,
        jurisdiction_state="Maharashtra",
        property_location_state="Maharashtra",
    )

    rec = res["recommended_forum"]
    assert rec["court_category"] == "Special Tribunal"
    assert "Real Estate Regulatory Authority" in rec["forum_name"]


def test_forum_cross_state_ambiguity_multi_option():
    """Verify multi-state defendant residence vs cause of action returns candidate options and flags Manual Review Required."""
    res = determine_forum(
        suit_type="Civil Suit",
        claim_value_inr=1_000_000.0,
        jurisdiction_state="Delhi",
        defendant_residence_state="Maharashtra",
        cause_of_action_location="Delhi",
    )

    assert res["is_unambiguous"] is False
    assert len(res["viable_options"]) >= 2
    sec20_alt = next((opt for opt in res["viable_options"] if "Section 20(a)" in "".join(opt["governing_provisions"])), None)
    assert sec20_alt is not None
    assert sec20_alt["confidence"] == "Manual Review Required"


def test_forum_api_endpoint():
    """Verify POST /api/litigation/forum-advisor REST API."""
    app.dependency_overrides[get_current_user] = lambda: type("User", (), {"id": "user-123"})()
    client = TestClient(app)

    payload = {
        "suit_type": "Civil Suit",
        "claim_value_inr": 30_000_000.0,
        "jurisdiction_state": "Delhi",
    }
    res = client.post("/api/litigation/forum-advisor", json=payload)
    app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()
    assert data["recommended_forum"]["court_category"] == "High Court"
    assert "Rule-based statutory jurisdiction calculation" in data["notice"]
