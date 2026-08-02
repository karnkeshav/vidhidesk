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
def test_success_log_line_reports_final_provider_and_failed_providers(settings, caplog):
    """Observability gap found live (2026-08-01): a warning line per
    failed attempt already existed, but nothing on the eventual success
    line said which providers had already failed for *that* request —
    with multiple concurrent generate() calls (one per llm_fillable
    clause in a single Contracts draft), failures and successes
    interleave in the log and can't be correlated. failed_providers on
    the success line closes that."""
    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(
        return_value=httpx.Response(429, json={"error": "rate limited"})
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="server error")
    )
    respx.post("https://api.sambanova.ai/v1/chat/completions").mock(
        return_value=_openai_ok("SambaNova says hi")
    )

    with caplog.at_level("INFO", logger="vidhidesk.llm_gateway"):
        result = generate("hello", settings=settings)

    assert result.provider == "sambanova"
    success_lines = [r.message for r in caplog.records if "status=ok" in r.message]
    assert len(success_lines) == 1
    assert "provider=sambanova" in success_lines[0]
    assert "failed_providers=['gemini', 'groq']" in success_lines[0]


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


def _capture_outbound_body(mock_target) -> dict:
    captured: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return _gemini_ok("ok")

    mock_target.mock(side_effect=_capture)
    return captured


@respx.mock
def test_outbound_body_never_contains_raw_person_name(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")

    # No explicit entities passed — this must be caught by automatic
    # person-name detection alone.
    generate("Ramesh Kumar signed the notice.", mask_map=mm, settings=settings)

    assert "Ramesh Kumar" not in captured["body"]


@respx.mock
def test_outbound_body_never_contains_raw_postal_address(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")

    generate(
        "The property is located at 12, MG Road, New Delhi 110001.",
        mask_map=mm,
        settings=settings,
    )

    assert "12, MG Road, New Delhi" not in captured["body"]


@respx.mock
def test_outbound_body_never_contains_raw_company_name(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")

    generate(
        "The vendor, Sharma Enterprises Pvt Ltd, breached clause 4.",
        mask_map=mm,
        settings=settings,
    )

    assert "Sharma Enterprises Pvt Ltd" not in captured["body"]


@respx.mock
def test_outbound_body_never_contains_raw_mobile_number_10_digit(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")

    generate("Call the client at 9876543210.", mask_map=mm, settings=settings)

    assert "9876543210" not in captured["body"]


@respx.mock
def test_outbound_body_never_contains_raw_mobile_number_plus91(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")

    generate("Call the client at +91 9876543210.", mask_map=mm, settings=settings)

    assert "+91 9876543210" not in captured["body"]
    assert "9876543210" not in captured["body"]


@respx.mock
def test_history_turns_are_included_in_outbound_request_in_order(settings):
    captured = _capture_outbound_body(
        respx.post(url__startswith="https://generativelanguage.googleapis.com")
    )
    mm = MaskMap(matter_id="m1")
    history = [
        {"role": "user", "content": "My client PARTY_A has PAN PAN_1."},
        {"role": "assistant", "content": "Understood, PARTY_A's PAN is PAN_1."},
    ]

    generate("What is his PAN?", mask_map=mm, history=history, settings=settings)

    import json

    body = json.loads(captured["body"])
    contents = body["contents"]
    assert len(contents) == 3  # 2 history turns + current turn
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "My client PARTY_A has PAN PAN_1."
    assert contents[1]["role"] == "model"  # assistant -> Gemini's "model" role
    assert contents[1]["parts"][0]["text"] == "Understood, PARTY_A's PAN is PAN_1."
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["text"] == "What is his PAN?"


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
