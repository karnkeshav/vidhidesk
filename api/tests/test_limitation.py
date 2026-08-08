from __future__ import annotations

from datetime import datetime
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.main import app
from app.services.limitation import calculate_limitation


def test_limitation_money_recovery_unbarred():
    """Verify money recovery suit within 3 years limitation."""
    # Cause of action 1 year ago relative to fixed current date
    res = calculate_limitation(
        cause_of_action_date_str="2025-05-10",
        suit_category="Money Recovery",
        current_date=datetime(2026, 5, 10),
    )

    assert res["cause_of_action_date"] == "2025-05-10"
    assert res["limitation_expiry_date"] == "2028-05-10"
    assert res["is_barred"] is False
    assert res["days_remaining"] == 731  # 2 years remaining
    assert res["primary_article"]["article_number"] == "Article 19"
    assert res["condonation_required"] is False


def test_limitation_money_recovery_barred_with_condonation():
    """Verify money recovery suit past 3 years is flagged as barred with Section 5 condonation note."""
    # Cause of action 4 years ago
    res = calculate_limitation(
        cause_of_action_date_str="2020-05-10",
        suit_category="Money Recovery",
        current_date=datetime(2026, 5, 10),
    )

    assert res["limitation_expiry_date"] == "2023-05-10"
    assert res["is_barred"] is True
    assert res["days_remaining"] < 0
    assert res["condonation_required"] is True
    assert "Section 5 of the Limitation Act, 1963" in res["condonation_notes"]


def test_limitation_possession_12_years():
    """Verify possession suit has 12-year statutory limitation period under Article 65."""
    res = calculate_limitation(
        cause_of_action_date_str="2018-01-01",
        suit_category="Possession",
        current_date=datetime(2026, 5, 10),
    )

    assert res["limitation_expiry_date"] == "2030-01-01"
    assert res["is_barred"] is False
    assert res["primary_article"]["article_number"] == "Article 65"


def test_limitation_statutory_exclusion_days():
    """Verify adding exclusion days under Section 4-15 extends expiry date."""
    res_base = calculate_limitation(
        cause_of_action_date_str="2023-01-01",
        suit_category="Money Recovery",
        exclusion_days=0,
        current_date=datetime(2026, 5, 10),
    )
    res_ext = calculate_limitation(
        cause_of_action_date_str="2023-01-01",
        suit_category="Money Recovery",
        exclusion_days=60,
        current_date=datetime(2026, 5, 10),
    )

    assert res_base["limitation_expiry_date"] == "2026-01-01"
    assert res_ext["limitation_expiry_date"] == "2026-03-02"
    assert res_ext["days_remaining"] == res_base["days_remaining"] + 60


def test_limitation_appeal_article_116_ninety_days_exact():
    """Regression for TICKET-5: Article 116 (HC appeal) must expire exactly
    90 days after the decree, not 89. The article is stored as a
    year-fraction (0.2465) for the day-based branch of calculate_limitation;
    int(0.2465 * 365) truncates to 89, one day short — round() is required
    to recover the intended 90-day statutory period."""
    res = calculate_limitation(
        cause_of_action_date_str="2026-06-20",
        suit_category="Appeal",
        current_date=datetime(2026, 8, 6),
    )

    assert res["primary_article"]["article_number"] == "Article 116"
    assert res["limitation_expiry_date"] == "2026-09-18"  # exactly 90 days, not 89
    assert res["days_remaining"] == 43


def test_limitation_appeal_article_115_thirty_days_exact():
    """Regression for TICKET-5: Article 115 (District/Subordinate Court
    appeal) must expire exactly 30 days after the decree, not 29."""
    res = calculate_limitation(
        cause_of_action_date_str="2026-07-20",
        suit_category="Appeal",
        selected_article="Article 115",
        current_date=datetime(2026, 8, 6),
    )

    assert res["primary_article"]["article_number"] == "Article 115"
    assert res["limitation_expiry_date"] == "2026-08-19"  # exactly 30 days, not 29
    assert res["days_remaining"] == 13


def test_limitation_api_endpoint():
    """Verify POST /api/litigation/limitation-calculator REST API."""
    app.dependency_overrides[get_current_user] = lambda: type("User", (), {"id": "user-123"})()
    client = TestClient(app)

    payload = {
        "cause_of_action_date": "2024-01-15",
        "suit_category": "Specific Performance",
        "exclusion_days": 15,
    }
    res = client.post("/api/litigation/limitation-calculator", json=payload)
    app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()
    assert data["cause_of_action_date"] == "2024-01-15"
    assert data["suit_category"] == "Specific Performance"
    assert data["primary_article"]["article_number"] == "Article 54"
    assert "Rule-based statutory calculation under Limitation Act, 1963" in data["notice"]
