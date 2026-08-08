"""Part 4 — Provider Verification (Sprint 3.5.5B).

Makes one real, minimal call to every configured provider — Gemini,
Groq, SambaNova, Cerebras (the LLM Gateway's failover chain, CLAUDE.md
Decision 3), and Indian Kanoon (the Citation Verifier's data source) —
and reports configured / reachable / latency / authentication /
failure-reason for each. Every number below is a real, timed call made
during this run, not a cached or estimated figure. Calls are deliberately
minimal (a few tokens / one search query) to bound real cost and quota
usage — this script is meant to be run often, including in CI.

Run standalone: python scripts/verify_llm_providers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with, timed  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

_TEST_TURNS = [("user", "Reply with exactly the single word: OK")]


def _check_llm_provider(result: VerificationResult, name: str, api_key: str, call_fn) -> None:
    if not api_key:
        result.add(name, Status.SKIP, "Not configured (empty API key)")
        return

    value, dt, err = timed(call_fn)
    if err is not None:
        result.add(name, Status.FAIL, f"Configured but unreachable/unauthorized: {type(err).__name__}: {err}", dt)
        return
    text, model = value
    result.add(name, Status.PASS, f"model={model}  response={text[:80]!r}", dt)


def run() -> VerificationResult:
    result = VerificationResult("LLM & Citation Provider Verification (Part 4)")

    try:
        from app.config import get_settings  # noqa: PLC0415
        from app.services.llm_gateway import _call_gemini, _call_openai_compatible  # noqa: PLC0415
        from app.services.indian_kanoon import IndianKanoonClient  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        result.add("Import provider client code", Status.FAIL, f"{type(exc).__name__}: {exc}")
        return result

    settings = get_settings()

    _check_llm_provider(
        result, "Gemini (GEMINI_API_KEY)", settings.gemini_api_key,
        lambda: _call_gemini(settings, "gemini-2.5-flash-lite", "You are a test.", _TEST_TURNS),
    )
    _check_llm_provider(
        result, "Groq (GROQ_API_KEY)", settings.groq_api_key,
        lambda: _call_openai_compatible("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, "llama-3.1-8b-instant", "You are a test.", _TEST_TURNS),
    )
    _check_llm_provider(
        result, "SambaNova (SAMBANOVA_API_KEY)", settings.sambanova_api_key,
        lambda: _call_openai_compatible("sambanova", "https://api.sambanova.ai/v1", settings.sambanova_api_key, "Meta-Llama-3.3-70B-Instruct", "You are a test.", _TEST_TURNS),
    )
    _check_llm_provider(
        result, "Cerebras (CEREBRAS_API_KEY)", settings.cerebras_api_key,
        lambda: _call_openai_compatible("cerebras", "https://api.cerebras.ai/v1", settings.cerebras_api_key, "gpt-oss-120b", "You are a test.", _TEST_TURNS),
    )

    # Indian Kanoon — not an LLM, but grouped here per this sprint's own
    # Part 4 spec, which lists it alongside the four LLM providers as
    # "every configured provider."
    if not settings.indian_kanoon_api_token:
        result.add("Indian Kanoon (INDIAN_KANOON_API_TOKEN)", Status.SKIP, "Not configured (empty token)")
    else:
        def _ik_call():
            client = IndianKanoonClient()
            return client.search("Ramesh Kumar vs State of Delhi", max_pages=1)

        value, dt, err = timed(_ik_call)
        if err is not None:
            result.add("Indian Kanoon (INDIAN_KANOON_API_TOKEN)", Status.FAIL, f"{type(err).__name__}: {err}", dt)
        else:
            n = len(value.get("docs", []))
            result.add("Indian Kanoon (INDIAN_KANOON_API_TOKEN)", Status.PASS, f"{n} search results returned", dt)

    # Failover-chain health: as long as at least one of the first three
    # tiers works, generate() will always succeed for a real request —
    # report this distinctly from any single provider's status, since a
    # single dead tier (e.g. TICKET-11's Cerebras key) has zero practical
    # impact if the tiers ahead of it are healthy.
    working_llm = [c.label for c in result.checks if c.label.split(" (")[0] in ("Gemini", "Groq", "SambaNova", "Cerebras") and c.status == Status.PASS]
    if working_llm:
        result.add(
            "LLM Gateway failover chain has at least one working tier",
            Status.PASS,
            f"Working: {', '.join(l.split(' (')[0] for l in working_llm)} — generate() will succeed even if other tiers are down",
        )
    else:
        result.add("LLM Gateway failover chain has at least one working tier", Status.FAIL, "ALL four LLM providers are unreachable or misconfigured — generate() will fail for every request")

    return result


if __name__ == "__main__":
    exit_with(run())
