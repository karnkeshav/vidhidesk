"""Pure, deterministic checks used to score real-workload model
validation output (Phase 4.6).

No network calls, no side effects, no dependency on model_pool.py or
llm_gateway.py -- every function takes plain text/data in and returns a
bool/list, so this is fully unit-testable without touching a real
provider, a real draft, or even the model pool's own selection logic.

These are heuristics, not a certification of legal correctness or of
"good drafting" (Phase 4.6's rubric explicitly separates the two) --
they catch clear, mechanically-detectable defects (a raw PII value
making it into an outbound masked prompt, a placeholder token leaking
un-unmasked into final output, an obvious reasoning-trace/conversational
marker) so the Phase 4.6 validation harness doesn't have to hand-inspect
every draft for these specific, well-understood failure modes. Genuine
legal-drafting quality and coherence are still judged by a human reader
against the harness's captured output, same as Phase 4.6's own rubric
requires.
"""

from __future__ import annotations

import re

# Matches contracts placeholders exactly (PARTY_1, ADDR_2, PAN_1, ...) --
# same kind vocabulary as pii_mask.py's own _RESERVED_KIND_WORDS.
_PLACEHOLDER_RE = re.compile(r"\b(?:PARTY|ADDR|PAN|PHONE|AADHAAR|EMAIL)_[A-Z0-9]+\b")

# Substrings indicating the model leaked internal reasoning, a refusal,
# or conversational meta-commentary instead of clean drafted prose.
# Deliberately broad/best-effort -- a false positive here just prompts a
# human to double check that one line, it does not silently fail
# anything on its own (the harness always keeps the full raw text for
# manual review too).
_REASONING_LEAK_MARKERS = (
    "<think",
    "</think>",
    "as an ai",
    "as a language model",
    "i cannot ",
    "i can't ",
    "i'm sorry",
    "i am sorry",
    "let me think",
    "chain of thought",
    "here is the clause",
    "here's the clause",
    "sure, here",
    "i'd be happy",
    "certainly! here",
)


def contains_raw_value(text: str, raw_values: list[str]) -> list[str]:
    """Which of `raw_values` appear verbatim (case-sensitive substring)
    in `text`. Used against an OUTBOUND masked prompt -- expected: []
    (no raw PII should ever reach the provider)."""
    return [v for v in raw_values if v and v in text]


def has_leftover_placeholder(text: str) -> list[str]:
    """Any KIND_n-shaped placeholder token still present in `text`.
    Used against FINAL (post-unmask) output -- a non-empty result means
    unmask_text() failed to restore at least one placeholder because the
    model echoed it back in a form the masker's own replace pass didn't
    recognize (e.g. reformatted, split across a line break)."""
    return _PLACEHOLDER_RE.findall(text)


def has_reasoning_leakage(text: str) -> list[str]:
    """Any matched reasoning/refusal/conversational-leakage marker found
    in `text` (case-insensitive substring match). Non-empty means the
    model likely produced something other than clean drafted prose."""
    lowered = text.lower()
    return [marker for marker in _REASONING_LEAK_MARKERS if marker in lowered]


def distinct_value_to_placeholder_ratio(pii_rows: list[dict]) -> tuple[int, int]:
    """(distinct real_value count, distinct placeholder count) among mask
    rows. Equal counts means no two different real values collided onto
    the same placeholder, and no single real value was split across two
    placeholders."""
    real_values = {row["real_value"].strip().lower() for row in pii_rows}
    placeholders = {row["placeholder"] for row in pii_rows}
    return len(real_values), len(placeholders)
