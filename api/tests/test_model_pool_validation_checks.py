"""Deterministic unit tests for the Phase 4.6 validation-scoring
helpers (app.services.model_pool_validation_checks).

Pure functions, no network, no fixtures beyond plain strings/dicts --
these must never need a real provider key or a real draft to exercise."""
from __future__ import annotations

from app.services.model_pool_validation_checks import (
    contains_raw_value,
    distinct_value_to_placeholder_ratio,
    has_leftover_placeholder,
    has_reasoning_leakage,
)


def test_contains_raw_value_detects_leak():
    assert contains_raw_value("Please contact Rohan Mehta at once.", ["Rohan Mehta"]) == ["Rohan Mehta"]


def test_contains_raw_value_clean_masked_prompt():
    assert contains_raw_value("Please contact PARTY_1 at once.", ["Rohan Mehta"]) == []


def test_contains_raw_value_ignores_blank_entries():
    assert contains_raw_value("some text", ["", "Rohan Mehta"]) == []


def test_has_leftover_placeholder_detects_unresolved_token():
    assert has_leftover_placeholder("The Client, PARTY_1, shall pay ADDR_2.") == ["PARTY_1", "ADDR_2"]


def test_has_leftover_placeholder_clean_final_text():
    assert has_leftover_placeholder("The Client, Rohan Mehta, shall pay the fee.") == []


def test_has_leftover_placeholder_does_not_false_positive_on_similar_text():
    # "PARTY" without a trailing "_<suffix>" is not a placeholder token.
    assert has_leftover_placeholder("Each PARTY shall perform its obligations.") == []


def test_has_reasoning_leakage_detects_think_tag():
    assert "<think" in has_reasoning_leakage("<think>reasoning about the clause</think>Actual text.")


def test_has_reasoning_leakage_detects_refusal():
    assert "i cannot " in has_reasoning_leakage("I cannot help draft this clause.")


def test_has_reasoning_leakage_clean_prose():
    assert has_reasoning_leakage("The Consultant shall provide the Services with reasonable skill and care.") == []


def test_has_reasoning_leakage_case_insensitive():
    assert "as an ai" in has_reasoning_leakage("As an AI, I should note this is not legal advice.")


def test_distinct_value_to_placeholder_ratio_no_collision():
    rows = [
        {"real_value": "Rohan Mehta", "placeholder": "PARTY_1"},
        {"real_value": "Bluewave Logistics Pvt Ltd", "placeholder": "PARTY_2"},
        {"real_value": "12 Example Road, Hyderabad", "placeholder": "ADDR_1"},
    ]
    assert distinct_value_to_placeholder_ratio(rows) == (3, 3)


def test_distinct_value_to_placeholder_ratio_detects_collision():
    # Two different real values collapsed onto the same placeholder would
    # only happen from a masking bug -- this proves the check would catch it.
    rows = [
        {"real_value": "Rohan Mehta", "placeholder": "PARTY_1"},
        {"real_value": "Someone Else", "placeholder": "PARTY_1"},
    ]
    distinct_values, distinct_placeholders = distinct_value_to_placeholder_ratio(rows)
    assert distinct_values == 2
    assert distinct_placeholders == 1
