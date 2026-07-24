"""Tests for the LLM Gateway's failover order and PII-masking integration.

No real network calls: every provider HTTP call is mocked via respx.
"""

import httpx
import pytest
import respx

from app.config import Settings
from app.services.llm_gateway import GenerationResult, ProviderError, generate
from app.services.pii_mask import MaskMap


@pytest.fixture
def settings():
    return Settings(
        gemini_api_key="gemini-key",
        groq_api_key="groq-key",
        sambanova_api_key="sambanova-key",
        cerebras_api_key="cerebras-key",
    )


def _gemini_ok(text: str):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def _openai_ok(text: str):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@respx.mock
def test_uses_gemini_first_when_it_succeeds(settings):
    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        return_value=_gemini_ok("Gemini says hi")
    )

    result = generate("hello", settings=settings)

    assert isinstance(result, GenerationResult)
    assert result.provider == "gemini"
    assert result.text == "Gemini says hi"


@respx.mock
def test_fails_over_gemini_to_groq_on_rate_limit(settings):
    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        return_value=httpx.Response(429, json={"error": "rate limited"})
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=_openai_ok("Groq says hi")
    )

    result = generate("hello", settings=settings)

    assert result.provider == "groq"
    assert result.text == "Groq says hi"


@respx.mock
def test_fails_over_through_full_chain_to_cerebras(settings):
    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        return_value=httpx.Response(500, text="server error")
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(429)
    )
    respx.post("https://api.sambanova.ai/v1/chat/completions").mock(
        return_value=httpx.Response(500)
    )
    respx.post("https://api.cerebras.ai/v1/chat/completions").mock(
        return_value=_openai_ok("Cerebras says hi")
    )

    result = generate("hello", settings=settings)

    assert result.provider == "cerebras"
    assert result.text == "Cerebras says hi"


@respx.mock
def test_raises_when_all_providers_fail(settings):
    for url in [
        "https://generativelanguage.googleapis.com",
    ]:
        respx.post(url__startswith=url).mock(return_value=httpx.Response(500))
    for url in [
        "https://api.groq.com/openai/v1/chat/completions",
        "https://api.sambanova.ai/v1/chat/completions",
        "https://api.cerebras.ai/v1/chat/completions",
    ]:
        respx.post(url).mock(return_value=httpx.Response(500))

    with pytest.raises(ProviderError):
        generate("hello", settings=settings)


@respx.mock
def test_outbound_request_never_contains_raw_pii(settings):
    """The masked prompt sent over the wire must not contain the real name."""
    captured: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        captured["body"] = body
        return _gemini_ok("Drafted for PARTY_A.")

    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        side_effect=_capture
    )

    mm = MaskMap(matter_id="m1")
    result = generate(
        "Draft a notice for Ramesh Kumar.",
        mask_map=mm,
        entities=[("PARTY", "Ramesh Kumar")],
        settings=settings,
    )

    assert "Ramesh Kumar" not in captured["body"]
    assert "PARTY_A" in captured["body"]
    # And the caller-facing result has the real name restored.
    assert result.text == "Drafted for Ramesh Kumar."


@respx.mock
def test_retries_transient_network_error_before_failing_over(settings):
    call_count = {"gemini": 0}

    def _flaky(request: httpx.Request) -> httpx.Response:
        call_count["gemini"] += 1
        if call_count["gemini"] == 1:
            raise httpx.ConnectTimeout("timed out", request=request)
        return _gemini_ok("Gemini recovered")

    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        side_effect=_flaky
    )

    result = generate("hello", settings=settings)

    assert result.provider == "gemini"
    assert result.text == "Gemini recovered"
    assert call_count["gemini"] == 2
