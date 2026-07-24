"""Mandatory PII-masking layer (CLAUDE.md Decision 4).

Because there is no local model, every prompt leaves the building to a
third-party LLM. Before that happens, party names, addresses, phone
numbers, and Aadhaar/PAN patterns are replaced with stable placeholders
(PARTY_A, ADDR_1, ...). The mapping never leaves this process — it is
persisted per-matter and used to restore the real values in the response.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

# --- Regex-detected PII (no caller input required) -------------------------
# Order matters: more specific patterns first so e.g. a PAN isn't partially
# re-matched by a looser pattern.
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)")

# (kind, regex) — checked in this order for every mask() call.
REGEX_KINDS: list[tuple[str, re.Pattern[str]]] = [
    ("PAN", PAN_RE),
    ("AADHAAR", AADHAAR_RE),
    ("EMAIL", EMAIL_RE),
    ("PHONE", PHONE_RE),
]

# Caller-supplied entity kinds get letter suffixes (PARTY_A) per CLAUDE.md's
# own example; regex-detected kinds get numeric suffixes (PAN_1).
_LETTER_KINDS = {"PARTY"}


def _next_suffix(mask_map: "MaskMap", kind: str) -> str:
    n = mask_map.counters.get(kind, 0) + 1
    mask_map.counters[kind] = n
    if kind in _LETTER_KINDS:
        # A, B, C, ... Z, AA, AB, ... (won't realistically exceed Z in practice)
        letters = ""
        i = n
        while i > 0:
            i, rem = divmod(i - 1, 26)
            letters = chr(65 + rem) + letters
        return letters
    return str(n)


@dataclass
class MaskMap:
    """Per-matter mapping between real values and stable placeholders."""

    matter_id: str
    forward: dict[str, str] = field(default_factory=dict)  # normalized real value -> placeholder
    reverse: dict[str, str] = field(default_factory=dict)  # placeholder -> real value
    counters: dict[str, int] = field(default_factory=dict)  # kind -> last-used index

    def get_or_assign(self, kind: str, real_value: str) -> str:
        key = real_value.strip().lower()
        placeholder = self.forward.get(key)
        if placeholder:
            return placeholder
        placeholder = f"{kind}_{_next_suffix(self, kind)}"
        self.forward[key] = placeholder
        self.reverse[placeholder] = real_value
        return placeholder


class MaskStore(Protocol):
    def load(self, matter_id: str) -> MaskMap: ...
    def save(self, mask_map: MaskMap) -> None: ...


class InMemoryMaskStore:
    """Test/dev store. Production uses SupabaseMaskStore below."""

    def __init__(self) -> None:
        self._maps: dict[str, MaskMap] = {}

    def load(self, matter_id: str) -> MaskMap:
        return self._maps.get(matter_id) or MaskMap(matter_id=matter_id)

    def save(self, mask_map: MaskMap) -> None:
        self._maps[mask_map.matter_id] = mask_map


class SupabaseMaskStore:
    """Persists the mask map in the pii_masks table via the service-role
    client. Never sent to the LLM; never exposed to the frontend (see
    migrations/0002_rls.sql — no policy grants client access to this
    table at all)."""

    def __init__(self, db) -> None:  # db: supabase.Client, service-role
        self._db = db

    def load(self, matter_id: str) -> MaskMap:
        rows = (
            self._db.table("pii_masks")
            .select("placeholder,real_value,kind")
            .eq("matter_id", matter_id)
            .execute()
            .data
        )
        mm = MaskMap(matter_id=matter_id)
        for row in rows:
            placeholder, real_value, kind = row["placeholder"], row["real_value"], row["kind"]
            mm.forward[real_value.strip().lower()] = placeholder
            mm.reverse[placeholder] = real_value
            suffix = placeholder[len(kind) + 1 :]
            if kind in _LETTER_KINDS:
                idx = 0
                for ch in suffix:
                    idx = idx * 26 + (ord(ch) - 64)
            else:
                idx = int(suffix) if suffix.isdigit() else 0
            mm.counters[kind] = max(mm.counters.get(kind, 0), idx)
        return mm

    def save(self, mask_map: MaskMap) -> None:
        existing = {
            row["placeholder"]
            for row in self._db.table("pii_masks")
            .select("placeholder")
            .eq("matter_id", mask_map.matter_id)
            .execute()
            .data
        }
        new_rows = [
            {
                "matter_id": mask_map.matter_id,
                "placeholder": placeholder,
                "real_value": real_value,
                "kind": placeholder.rsplit("_", 1)[0],
            }
            for placeholder, real_value in mask_map.reverse.items()
            if placeholder not in existing
        ]
        if new_rows:
            self._db.table("pii_masks").insert(new_rows).execute()


_WORD_BOUNDARY_SAFE = re.compile(r"[.*+?^${}()|[\]\\]")


def _escape(value: str) -> str:
    return _WORD_BOUNDARY_SAFE.sub(lambda m: "\\" + m.group(0), value)


def mask_text(
    text: str,
    mask_map: MaskMap,
    entities: list[tuple[str, str]] | None = None,
) -> str:
    """Replace known entities and regex-detected PII with placeholders.

    `entities` is an ordered list of (kind, value) pairs the caller already
    knows are sensitive, e.g. [("PARTY", "Ramesh Kumar"), ("ADDR", "12, MG
    Road, Delhi")]. Regex kinds (PAN/Aadhaar/email/phone) are detected
    automatically regardless of `entities`.
    """
    masked = text

    for kind, value in entities or []:
        if not value or not value.strip():
            continue
        placeholder = mask_map.get_or_assign(kind, value)
        masked = re.sub(
            _escape(value.strip()), placeholder, masked, flags=re.IGNORECASE
        )

    for kind, pattern in REGEX_KINDS:
        def _replace(m: re.Match[str], kind: str = kind) -> str:
            return mask_map.get_or_assign(kind, m.group(0))

        masked = pattern.sub(_replace, masked)

    return masked


_PLACEHOLDER_RE = re.compile(r"\b[A-Z]+_[A-Z0-9]+\b")


def unmask_text(text: str, mask_map: MaskMap) -> str:
    """Restore real values for any placeholder the model echoed back."""

    def _restore(m: re.Match[str]) -> str:
        return mask_map.reverse.get(m.group(0), m.group(0))

    return _PLACEHOLDER_RE.sub(_restore, text)
