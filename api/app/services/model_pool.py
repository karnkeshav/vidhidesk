"""LEGAL_DRAFTING model pool (Phase 4.5).

Architectural rule: POOL FOR AVAILABILITY, CONSISTENCY FOR EXECUTION.

select_model() picks exactly ONE (provider, model) for an entire draft
session, before any clause generation begins. app.services.contracts.
generate_draft() calls this once and passes the result to every
clause's llm_gateway.generate() call (via its `selected_model`
parameter), so a single draft can never silently mix providers/models
across clauses the way the pre-Phase-4.5 per-call failover could.

This is deliberately NOT a live health-tracking system yet. `enabled`
is a static, hand-set flag reflecting the evidence gathered in Phase
4.4A's live diagnostic (see each entry's `reason` when disabled) --
not a dynamically probed value, and select_model() makes no network
call of its own. `status` distinguishes "evidence exists this model
works at the API level" (CANDIDATE) from "validated as good enough for
real legal drafting output" (PRODUCTION_VALIDATED) -- an HTTP 200 alone
never earns that label (Phase 4.4A Step 6's explicit warning); Phase
4.6's real-workload validation harness (api/scripts/
validate_model_pool_phase46.py) is what actually earned the two
PRODUCTION_VALIDATED entries below -- see each entry's comment for what
evidence backs it and, for the one entry NOT promoted, why.

Disabled entries are not permanent removals (unlike llm_gateway.py's
own dead-model removals for genuinely archived/404 models) -- each can
be re-enabled once its underlying condition (quota reset, billing fix,
quality validation) changes, without new code, by flipping `enabled`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.config import Settings, get_settings


class Capability(str, Enum):
    LEGAL_DRAFTING = "LEGAL_DRAFTING"


class ModelStatus(str, Enum):
    CANDIDATE = "candidate"
    PRODUCTION_VALIDATED = "production_validated"


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str
    capability: Capability
    priority: int
    enabled: bool
    status: ModelStatus = ModelStatus.CANDIDATE
    # Conservative default, not a provider-verified true limit -- Phase 4.5
    # has no per-model concurrency evidence beyond "2 simultaneous calls
    # didn't fail" for one model (Phase 4.3-R). Do not read this as a
    # discovered ceiling.
    concurrency_limit: int = 3
    timeout_s: float = 30.0
    # Reuses llm_gateway's existing per-call retry (tenacity, 2 attempts,
    # transient-network-errors-only) -- this field documents that fact,
    # it does not configure a separate/new retry mechanism.
    retry_policy: str = "existing (llm_gateway._retry_transient)"
    # Why disabled, when enabled=False. Also used, for an enabled entry,
    # to record why it was NOT promoted to PRODUCTION_VALIDATED despite
    # being reachable/tested (Phase 4.6) -- still empty for the common
    # case of an enabled CANDIDATE with no promotion decision made yet.
    reason: str = ""
    last_success: str | None = None
    last_failure: str | None = None
    failure_type: str | None = None
    quota_state: str | None = None


# Evidence-based registry (Phase 4.4A live diagnostic, this session).
_REGISTRY: list[ModelSpec] = [
    # Phase 4.6 (2026-08-20): real-workload validation harness run against
    # the real Gemini API (14/14 calls succeeded in a single full pass --
    # simple clause, PII masking, 5-clause structured draft, constrained
    # amendment). Clean, formal, coherent output throughout; zero raw PII
    # in any outbound prompt; zero reasoning-trace leakage; correctly
    # honored every negative drafting constraint tested (no fee-structure
    # leakage into recitals, no invented citations, amendment instructions
    # followed). Promoted on the strength of that single pass -- reliability
    # evidence is n=1 repeats, not the full 3x the phase's own rubric
    # prefers, because gemini-3.1-flash-lite's real daily free-tier quota
    # (20 requests/day/model, independently diagnosed in Phase 4.3-R) does
    # not allow more without risking exhausting it on this validation run
    # alone. See api/scripts/validate_model_pool_phase46.py output for the
    # full captured transcript.
    ModelSpec(
        provider="gemini", model="gemini-3.1-flash-lite",
        capability=Capability.LEGAL_DRAFTING, priority=1, enabled=True,
        status=ModelStatus.PRODUCTION_VALIDATED,
    ),
    # Phase 4.6 (2026-08-20): real-workload validation. All 4 test
    # categories passed cleanly at least once (14/14 calls); a 2nd repeat
    # of the structured-draft category hit a genuine Groq rate limit
    # (recorded, not retried -- see the harness's hard-stop behavior),
    # itself useful evidence that the locked-model "no cross-provider
    # failover mid-draft" invariant holds correctly under a real failure.
    # Zero raw PII in any outbound prompt, zero reasoning-trace leakage,
    # correct constraint-following on the constrained amendment. One minor
    # quality note: given an under-specified prompt (the NDA fixture's
    # recitals clause, which doesn't pass party names in this particular
    # template), this model emitted bracketed "[Party A]"-style fill-in
    # markers rather than a generic role label -- not a hallucination, but
    # a usability wrinkle worth watching, not a promotion blocker.
    ModelSpec(
        provider="groq", model="openai/gpt-oss-120b",
        capability=Capability.LEGAL_DRAFTING, priority=2, enabled=True,
        status=ModelStatus.PRODUCTION_VALIDATED,
    ),
    # Phase 4.6 (2026-08-20): NOT promoted despite a clean run this session
    # (recitals clause succeeded 3 separate times -- Test A, Test C, Test
    # D -- with no refusal, no reasoning leakage, correct constraint-
    # following). This directly CONFLICTS with an earlier ad hoc Phase 4.6
    # quality pass that found a reproducible refusal on this exact model
    # for the recitals clause. A single clean session does not overturn a
    # previously reported reproducible defect -- "do not promote a model
    # because a single request succeeded" applies here even though several
    # requests succeeded, since none of them specifically stress-tested the
    # earlier failure mode at any depth. Kept as CANDIDATE until a
    # dedicated, higher-repeat-count recheck targeting the recitals clause
    # specifically resolves the conflict one way or the other.
    ModelSpec(
        provider="groq", model="openai/gpt-oss-20b",
        capability=Capability.LEGAL_DRAFTING, priority=3, enabled=True,
        status=ModelStatus.CANDIDATE,
        reason="Phase 4.6: conflicting evidence on recitals-clause reliability "
               "(clean in this session's 3 attempts, but an earlier ad hoc pass "
               "found a reproducible refusal) -- needs a dedicated recheck before "
               "promotion, not a quality or availability problem otherwise.",
    ),
    ModelSpec(
        provider="sambanova", model="Meta-Llama-3.3-70B-Instruct",
        capability=Capability.LEGAL_DRAFTING, priority=4, enabled=False,
        reason="currently rate-limited (HTTP 429, high demand) / requires additional validation",
    ),
    ModelSpec(
        provider="gemini", model="gemini-2.5-flash",
        capability=Capability.LEGAL_DRAFTING, priority=5, enabled=False,
        reason="currently quota exhausted (HTTP 429, daily free-tier limit)",
    ),
    ModelSpec(
        provider="gemini", model="gemini-2.5-flash-lite",
        capability=Capability.LEGAL_DRAFTING, priority=6, enabled=False,
        reason="currently quota exhausted (HTTP 429, daily free-tier limit)",
    ),
    ModelSpec(
        provider="groq", model="qwen/qwen3.6-27b",
        capability=Capability.LEGAL_DRAFTING, priority=7, enabled=False,
        reason="reasoning-output quality issue (returns visible <think> trace instead of "
               "clean text) -- requires explicit validation before use",
    ),
    ModelSpec(
        provider="cerebras", model="gpt-oss-120b",
        capability=Capability.LEGAL_DRAFTING, priority=8, enabled=False,
        reason="HTTP 402 payment_required -- account billing issue, not code/model quality",
    ),
    ModelSpec(
        provider="cerebras", model="gemma-4-31b",
        capability=Capability.LEGAL_DRAFTING, priority=9, enabled=False,
        reason="HTTP 402 payment_required -- account billing issue, not code/model quality",
    ),
]

_PROVIDER_KEY_ATTR: dict[str, str] = {
    "gemini": "gemini_api_key",
    "groq": "groq_api_key",
    "sambanova": "sambanova_api_key",
    "cerebras": "cerebras_api_key",
}


class NoEligibleModelError(Exception):
    """Raised when no enabled, capability-matching, credentialed model exists."""


def _provider_key_present(provider: str, settings: Settings) -> bool:
    attr = _PROVIDER_KEY_ATTR.get(provider)
    return bool(attr and getattr(settings, attr, ""))


def select_model(
    capability: Capability,
    settings: Settings | None = None,
    pool: list[ModelSpec] | None = None,
) -> ModelSpec:
    """STAGE 1 (before-draft) selection: return the highest-priority
    enabled, capability-matching, credentialed model.

    Makes no network call -- purely a static filter over the registry, so
    it can never block on or retry against a live provider. `pool` is
    injectable so tests can exercise selection logic (including a
    "highest-priority candidate becomes unavailable, next one is picked"
    scenario) without touching the real registry or any live API --
    production callers omit it and get `_REGISTRY`.

    Raises NoEligibleModelError if nothing qualifies (e.g. every entry
    for this capability is disabled, or none of the enabled entries have
    a configured API key) -- callers (contracts.generate_draft()) let
    this propagate as a clean, immediate failure rather than attempting
    a draft with no usable model.
    """
    settings = settings or get_settings()
    candidates = pool if pool is not None else _REGISTRY
    eligible = [
        m for m in candidates
        if m.capability == capability and m.enabled and _provider_key_present(m.provider, settings)
    ]
    if not eligible:
        raise NoEligibleModelError(f"no eligible model available for capability={capability}")
    eligible.sort(key=lambda m: m.priority)
    return eligible[0]
