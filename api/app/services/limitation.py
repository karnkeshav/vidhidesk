from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# Statutory Rules Repository under Indian Limitation Act, 1963
LIMITATION_ARTICLES: dict[str, list[dict[str, Any]]] = {
    "Money Recovery": [
        {
            "article_number": "Article 19",
            "description": "For money lent or paid under a contract/loan",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the loan is made or money is paid",
            "notes": "3-year limitation from the date money is paid or loan disbursed.",
        },
        {
            "article_number": "Article 20",
            "description": "For money lent under an agreement that it shall be payable on demand",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the loan is made",
            "notes": "3 years from the date of loan disbursement.",
        },
        {
            "article_number": "Article 22",
            "description": "For money deposited under an agreement that it shall be payable on demand",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the demand is made",
            "notes": "3 years from the date of formal written demand.",
        },
    ],
    "Specific Performance": [
        {
            "article_number": "Article 54",
            "description": "For specific performance of a contract",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "Date fixed for performance, or when plaintiff has notice that performance is refused",
            "notes": "3 years from agreed performance date, or from date of notice of refusal.",
        },
    ],
    "Possession": [
        {
            "article_number": "Article 65",
            "description": "For possession of immovable property based on title",
            "statutory_period_years": 12.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the possession of the defendant becomes adverse to the plaintiff",
            "notes": "12-year limitation period from adverse possession trigger.",
        },
        {
            "article_number": "Article 64",
            "description": "For possession of immovable property based on previous possession",
            "statutory_period_years": 12.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "Date of dispossession",
            "notes": "12 years from date of unlawful dispossession.",
        },
    ],
    "Declaratory": [
        {
            "article_number": "Article 58",
            "description": "To obtain any other declaration",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the right to sue first accrues",
            "notes": "3 years from when the cause of action or right to sue first arose.",
        },
    ],
    "Breach of Contract": [
        {
            "article_number": "Article 55",
            "description": "For compensation for breach of any contract, express or implied",
            "statutory_period_years": 3.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the contract is broken or breach occurs",
            "notes": "3 years from date of contractual breach.",
        },
    ],
    "Appeal": [
        {
            "article_number": "Article 116",
            "description": "Appeal to High Court under Code of Civil Procedure",
            "statutory_period_years": 0.2465,  # 90 days
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "Date of the decree or order appealed against",
            "notes": "90 days from date of decree/order (excluding time taken to obtain certified copy).",
        },
        {
            "article_number": "Article 115",
            "description": "Appeal to District Court or Subordinate Court",
            "statutory_period_years": 0.0821,  # 30 days
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "Date of the decree or order appealed against",
            "notes": "30 days from date of decree/order.",
        },
    ],
    "Execution": [
        {
            "article_number": "Article 136",
            "description": "For the execution of any decree or order of any civil court",
            "statutory_period_years": 12.0,
            "governing_act": "Limitation Act, 1963",
            "trigger_event": "When the decree or order becomes enforceable",
            "notes": "12 years from date of decree enforceability.",
        },
    ],
}


def calculate_limitation(
    cause_of_action_date_str: str,
    suit_category: str,
    exclusion_days: int = 0,
    selected_article: str | None = None,
    current_date: datetime | None = None,
) -> dict[str, Any]:
    """Deterministically calculate limitation expiry date and statutory status under Limitation Act, 1963."""
    try:
        coa_date = datetime.strptime(cause_of_action_date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date format for cause_of_action_date: '{cause_of_action_date_str}'. Expected YYYY-MM-DD.") from exc

    candidates = LIMITATION_ARTICLES.get(suit_category)
    if not candidates:
        # Default fallback to general declaration / contract Article 58/55
        candidates = [
            {
                "article_number": "Article 58 / 113",
                "description": f"Residuary Limitation Period for {suit_category}",
                "statutory_period_years": 3.0,
                "governing_act": "Limitation Act, 1963",
                "trigger_event": "When the right to sue first accrues",
                "notes": "Residuary 3-year period under Article 113 for suits without specific provision.",
            }
        ]

    # Select primary article
    primary_article = candidates[0]
    if selected_article:
        for article in candidates:
            if article["article_number"].lower() == selected_article.lower():
                primary_article = article
                break

    # Calculate exact expiry date
    years = primary_article["statutory_period_years"]
    if years < 1.0:
        # Day-based articles (e.g. 90 days or 30 days). round(), not int():
        # the stored year-fraction (e.g. 0.2465 for 90 days) is a lossy
        # decimal encoding of an exact day count, and int() truncates
        # 0.2465*365 == 89.9725 down to 89 — one day short of the
        # statutory period every time (see TICKET-5,
        # docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md
        # scenarios APP-01/APP-02/APP-03). round() recovers the intended
        # whole-day count correctly for any day-based article defined this
        # way, since the encoding error is always far under half a day.
        days = round(years * 365)
        expiry_date = coa_date + timedelta(days=days)
    else:
        # Year-based articles (e.g. 3 years or 12 years)
        # Using exact leap-year safe date addition
        try:
            expiry_date = coa_date.replace(year=coa_date.year + int(years))
        except ValueError:
            # Feb 29 leap year fallback to Feb 28
            expiry_date = coa_date.replace(year=coa_date.year + int(years), day=28)

    # Apply statutory exclusions (e.g. Section 4-15 Limitation Act)
    if exclusion_days > 0:
        expiry_date = expiry_date + timedelta(days=exclusion_days)

    now = current_date or datetime.now()
    days_remaining = (expiry_date.date() - now.date()).days
    is_barred = days_remaining < 0

    condonation_required = is_barred
    if condonation_required:
        condonation_notes = (
            f"Statutory limitation period of {primary_article['article_number']} expired on {expiry_date.strftime('%Y-%m-%d')} "
            f"({abs(days_remaining)} days ago). An Application for Condonation of Delay under Section 5 of the Limitation Act, 1963 "
            "must be filed along with sufficient cause explanations."
        )
    else:
        condonation_notes = (
            f"Suit is within limitation under {primary_article['article_number']}. "
            f"Expiry date is {expiry_date.strftime('%Y-%m-%d')} ({days_remaining} days remaining)."
        )

    return {
        "cause_of_action_date": cause_of_action_date_str,
        "suit_category": suit_category,
        "limitation_expiry_date": expiry_date.strftime("%Y-%m-%d"),
        "is_barred": is_barred,
        "days_remaining": days_remaining,
        "primary_article": primary_article,
        "candidate_articles": candidates,
        "condonation_required": condonation_required,
        "condonation_notes": condonation_notes,
        "notice": "Rule-based statutory calculation under Limitation Act, 1963. Advocate vetting required.",
    }
