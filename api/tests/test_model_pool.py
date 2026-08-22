"""Tests for the LEGAL_DRAFTING model pool (Phase 4.5).

select_model() makes no network call -- every test here constructs its
own explicit fake Settings/pool (never the real .env), so these are
fully deterministic and require no real provider API keys.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.services.model_pool import (
    Capability,
    ModelSpec,
    ModelStatus,
    NoEligibleModelError,
    select_model,
)


def _settings(**keys) -> Settings:
    """Settings with only the given provider keys set (all others
    empty) -- never reads the real .env."""
    return Settings(
        gemini_api_key=keys.get("gemini", ""),
        groq_api_key=keys.get("groq", ""),
        sambanova_api_key=keys.get("sambanova", ""),
        cerebras_api_key=keys.get("cerebras", ""),
    )


def test_returns_highest_priority_enabled_candidate():
    pool = [
        ModelSpec(provider="groq", model="model-b", capability=Capability.LEGAL_DRAFTING, priority=2, enabled=True),
        ModelSpec(provider="gemini", model="model-a", capability=Capability.LEGAL_DRAFTING, priority=1, enabled=True),
    ]
    selected = select_model(Capability.LEGAL_DRAFTING, settings=_settings(gemini="k", groq="k"), pool=pool)
    assert (selected.provider, selected.model) == ("gemini", "model-a")


def test_disabled_model_is_skipped():
    pool = [
        ModelSpec(provider="gemini", model="disabled-model", capability=Capability.LEGAL_DRAFTING,
                   priority=1, enabled=False, reason="test"),
        ModelSpec(provider="groq", model="enabled-model", capability=Capability.LEGAL_DRAFTING,
                   priority=2, enabled=True),
    ]
    selected = select_model(Capability.LEGAL_DRAFTING, settings=_settings(gemini="k", groq="k"), pool=pool)
    assert selected.model == "enabled-model"


def test_model_with_no_configured_key_is_skipped():
    """'Unavailable' includes enabled=True but no credential configured at
    all -- a static, non-live check (no API call), not a real probe."""
    pool = [
        ModelSpec(provider="gemini", model="no-key-model", capability=Capability.LEGAL_DRAFTING,
                   priority=1, enabled=True),
        ModelSpec(provider="groq", model="has-key-model", capability=Capability.LEGAL_DRAFTING,
                   priority=2, enabled=True),
    ]
    selected = select_model(Capability.LEGAL_DRAFTING, settings=_settings(groq="k"), pool=pool)  # no gemini key
    assert selected.model == "has-key-model"


def test_capability_filtering():
    pool = [
        ModelSpec(provider="gemini", model="wrong-capability", capability="OTHER_CAPABILITY",
                   priority=1, enabled=True),
        ModelSpec(provider="groq", model="right-capability", capability=Capability.LEGAL_DRAFTING,
                   priority=2, enabled=True),
    ]
    selected = select_model(Capability.LEGAL_DRAFTING, settings=_settings(gemini="k", groq="k"), pool=pool)
    assert selected.model == "right-capability"


def test_no_eligible_model_raises():
    pool = [
        ModelSpec(provider="gemini", model="disabled", capability=Capability.LEGAL_DRAFTING,
                   priority=1, enabled=False, reason="test"),
    ]
    with pytest.raises(NoEligibleModelError):
        select_model(Capability.LEGAL_DRAFTING, settings=_settings(), pool=pool)


def test_no_eligible_model_raises_when_key_missing_even_if_enabled():
    pool = [
        ModelSpec(provider="gemini", model="enabled-but-no-key", capability=Capability.LEGAL_DRAFTING,
                   priority=1, enabled=True),
    ]
    with pytest.raises(NoEligibleModelError):
        select_model(Capability.LEGAL_DRAFTING, settings=_settings(), pool=pool)  # no keys at all


def test_pre_draft_selection_moves_to_next_candidate_when_highest_priority_unavailable():
    """Phase 4.5 TEST SCENARIO, part 1: 'Model A unavailable BEFORE draft
    begins -> Model B is selected.' Model A here is disabled (the static
    equivalent of 'known unavailable' -- e.g. quota exhausted, per the
    real registry's own gemini-2.5-flash/-lite entries)."""
    model_a = ModelSpec(provider="gemini", model="model-a", capability=Capability.LEGAL_DRAFTING,
                         priority=1, enabled=False, reason="unavailable for this test")
    model_b = ModelSpec(provider="groq", model="model-b", capability=Capability.LEGAL_DRAFTING,
                         priority=2, enabled=True)
    pool = [model_a, model_b]
    selected = select_model(Capability.LEGAL_DRAFTING, settings=_settings(gemini="k", groq="k"), pool=pool)
    assert selected.model == "model-b"


def test_production_validated_entries_match_phase_4_6_evidence():
    """Phase 4.4A Step 6 / Phase 4.5's explicit warning still holds: HTTP
    200 alone never earns PRODUCTION_VALIDATED. Phase 4.6's real-workload
    validation harness (api/scripts/validate_model_pool_phase46.py) is
    what actually promoted gemini-3.1-flash-lite and groq:openai/gpt-oss-120b
    -- see model_pool.py's registry comments for the evidence each one
    rests on. openai/gpt-oss-20b was deliberately NOT promoted despite a
    clean Phase 4.6 session, because that session's clean recitals-clause
    output conflicts with an earlier ad hoc pass's reproducible-refusal
    finding -- a conflict, not a resolved pass, so it stays CANDIDATE.
    Inspects the real, shipped registry (no selection call, no network, no
    live key needed)."""
    from app.services.model_pool import _REGISTRY
    validated = {
        (m.provider, m.model) for m in _REGISTRY if m.status == ModelStatus.PRODUCTION_VALIDATED
    }
    assert validated == {
        ("gemini", "gemini-3.1-flash-lite"),
        ("groq", "openai/gpt-oss-120b"),
    }
    still_candidate = next(m for m in _REGISTRY if (m.provider, m.model) == ("groq", "openai/gpt-oss-20b"))
    assert still_candidate.status == ModelStatus.CANDIDATE
    assert still_candidate.enabled is True


def test_real_registry_matches_approved_phase_4_5_design():
    """Confirms the actual shipped registry's enabled/priority ordering
    matches what was explicitly approved for this phase."""
    from app.services.model_pool import _REGISTRY
    enabled = sorted((m for m in _REGISTRY if m.enabled), key=lambda m: m.priority)
    assert [(m.provider, m.model) for m in enabled] == [
        ("gemini", "gemini-3.1-flash-lite"),
        ("groq", "openai/gpt-oss-120b"),
        ("groq", "openai/gpt-oss-20b"),
    ]
    disabled = {(m.provider, m.model) for m in _REGISTRY if not m.enabled}
    assert disabled == {
        ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
        ("gemini", "gemini-2.5-flash"),
        ("gemini", "gemini-2.5-flash-lite"),
        ("groq", "qwen/qwen3.6-27b"),
        ("cerebras", "gpt-oss-120b"),
        ("cerebras", "gemma-4-31b"),
    }
