"""LLM Gateway: single generate() entrypoint with masked prompts and
provider failover (CLAUDE.md Decision 3):

    Gemini 2.5 Flash (free tier) -> Groq (Llama-3.3-70B) -> SambaNova -> Cerebras

Every call is masked before it leaves the process (Decision 4) and every
attempt is logged with provider + latency for auditability (Hard rule 4).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.config import Settings, get_settings
from app.services.pii_mask import MaskMap, mask_text, unmask_text

logger = logging.getLogger("vidhidesk.llm_gateway")

# Per-module system prompts (TRD §3.1). Every prompt carries the
# non-negotiable grounding instruction regardless of module.
_GROUNDING_INSTRUCTION = (
    "Cite only statutes or cases the retrieval context provides. "
    "Never invent a case name, citation, or section number. "
    "If you are not given a source for a claim, say so explicitly instead "
    "of guessing."
)

SYSTEM_PROMPTS: dict[str, str] = {
    "litigation_analyst": (
        "You are a litigation research analyst for an Indian advocate. "
        f"{_GROUNDING_INSTRUCTION}"
    ),
    "contract_drafter": (
        "You are a contract-drafting assistant for an Indian advocate. "
        "You fill bespoke clauses inside a fixed document skeleton — you "
        f"never invent document structure or boilerplate. {_GROUNDING_INSTRUCTION}"
    ),
    "rera_specialist": (
        "You are a RERA and real-estate specialist assisting an Indian "
        f"advocate. {_GROUNDING_INSTRUCTION}"
    ),
    "consulting_analyst": (
        "You are a general Indian-law consulting analyst identifying "
        f"applicable statutes, forum, and remedies. {_GROUNDING_INSTRUCTION}"
    ),
    "chat": (
        "You are VidhiDesk, an AI assistant for an Indian advocate. "
        f"{_GROUNDING_INSTRUCTION}"
    ),
}


class ProviderError(Exception):
    def __init__(self, provider: str, message: str, rate_limited: bool = False):
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.rate_limited = rate_limited


@dataclass
class GenerationResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    masked_prompt: str


# Transient network failures (timeout, connection reset) get one retry
# within the same provider before we fail over. Rate limits and 4xx/5xx
# responses fail over immediately — retrying a 429 against the same
# provider just burns more quota for no benefit.
_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type(httpx.TransportError),
)


@_retry_transient
def _call_gemini(
    settings: Settings, system_prompt: str, turns: list[tuple[str, str]]
) -> tuple[str, str]:
    model = "gemini-2.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    # Gemini uses "model" where OpenAI-style APIs use "assistant".
    contents = [
        {"role": "user" if role == "user" else "model", "parts": [{"text": content}]}
        for role, content in turns
    ]
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
    }
    resp = httpx.post(url, json=body, timeout=30.0)
    _raise_for_provider("gemini", resp)
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise ProviderError("gemini", f"unexpected response shape: {data}") from exc
    return text, model


@_retry_transient
def _call_openai_compatible(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    turns: list[tuple[str, str]],
) -> tuple[str, str]:
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": role, "content": content} for role, content in turns]
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages},
        timeout=30.0,
    )
    _raise_for_provider(provider, resp)
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ProviderError(provider, f"unexpected response shape: {data}") from exc
    return text, model


def _raise_for_provider(provider: str, resp: httpx.Response) -> None:
    if resp.status_code == 429:
        raise ProviderError(provider, "rate limited", rate_limited=True)
    if resp.is_error:
        raise ProviderError(provider, f"HTTP {resp.status_code}: {resp.text[:300]}")


def _providers(settings: Settings):
    """Ordered failover chain. Each entry is (name, callable(system_prompt, turns) -> (text, model))."""
    return [
        (
            "gemini",
            lambda sp, turns: _call_gemini(settings, sp, turns),
        ),
        (
            "groq",
            lambda sp, turns: _call_openai_compatible(
                "groq", "https://api.groq.com/openai/v1", settings.groq_api_key,
                "llama-3.3-70b-versatile", sp, turns,
            ),
        ),
        (
            "sambanova",
            lambda sp, turns: _call_openai_compatible(
                "sambanova", "https://api.sambanova.ai/v1", settings.sambanova_api_key,
                "Meta-Llama-3.3-70B-Instruct", sp, turns,
            ),
        ),
        (
            "cerebras",
            lambda sp, turns: _call_openai_compatible(
                "cerebras", "https://api.cerebras.ai/v1", settings.cerebras_api_key,
                "llama-3.3-70b", sp, turns,
            ),
        ),
    ]


def generate(
    prompt: str,
    task_type: str = "chat",
    *,
    mask_map: MaskMap | None = None,
    entities: list[tuple[str, str]] | None = None,
    settings: Settings | None = None,
    history: list[dict] | None = None,
) -> GenerationResult:
    """Mask -> call providers in failover order -> unmask.

    If `mask_map` is None, masking is skipped entirely (only acceptable for
    prompts that are already known to contain no client data, e.g. the
    IK spike script). Production callers must always pass a matter's
    MaskMap.

    `history` is prior conversation turns, each `{"role": "user"|
    "assistant", "content": str}` — the caller is responsible for making
    sure `content` is already masked (see app/routers/matters.py's
    _build_history) before it ever reaches this function. generate()
    itself only masks the *current* `prompt`; it has no way to verify a
    caller-supplied history entry is safe.
    """
    settings = settings or get_settings()
    system_prompt = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["chat"])

    masked_prompt = mask_text(prompt, mask_map, entities) if mask_map else prompt
    turns: list[tuple[str, str]] = [
        (h["role"], h["content"]) for h in (history or [])
    ] + [("user", masked_prompt)]

    last_error: Exception | None = None
    for provider_name, call in _providers(settings):
        start = time.monotonic()
        try:
            text, model = call(system_prompt, turns)
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "llm_gateway.generate provider=%s model=%s task_type=%s "
                "latency_ms=%d status=success",
                provider_name, model, task_type, latency_ms,
            )
            unmasked_text = unmask_text(text, mask_map) if mask_map else text
            return GenerationResult(
                text=unmasked_text,
                provider=provider_name,
                model=model,
                latency_ms=latency_ms,
                masked_prompt=masked_prompt,
            )
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure fails over
            latency_ms = int((time.monotonic() - start) * 1000)
            reason = str(exc)
            logger.warning(
                "llm_gateway.generate provider=%s task_type=%s latency_ms=%d "
                "status=error reason=%s",
                provider_name, task_type, latency_ms, reason,
            )
            last_error = exc
            continue

    raise ProviderError(
        "all", f"all providers failed; last error: {last_error}"
    ) from last_error
