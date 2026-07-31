"""Mandatory PII-masking layer (CLAUDE.md Decision 4).

Because there is no local model, every prompt leaves the building to a
third-party LLM. Before that happens, party names, addresses, phone
numbers, and Aadhaar/PAN patterns are replaced with stable placeholders
(PARTY_A, ADDR_1, ...). The mapping never leaves this process — it is
persisted per-matter and used to restore the real values in the response.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from typing import Protocol

# --- Regex-detected PII (no caller input required) -------------------------
# Order matters: PHONE must be checked before AADHAAR. A +91-prefixed
# mobile number with no internal separator (+919876543210) is 12 digits
# after the '+' — indistinguishable from an Aadhaar number by digit count
# alone, so whichever pattern runs first wins. PHONE requires the leading
# digit (after an optional +91) to be 6-9, which Aadhaar numbers don't
# guarantee, so checking PHONE first correctly claims real mobile numbers
# and leaves genuine Aadhaar numbers (which usually start 1-5) for AADHAAR.
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
# 10 digits, first digit 6-9, optionally grouped 5+5 with one space/hyphen,
# optionally prefixed with +91 (with or without its own separator).
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{4}[-\s]?\d{5}(?!\d)")
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# (kind, regex) — checked in this order for every mask() call.
REGEX_KINDS: list[tuple[str, re.Pattern[str]]] = [
    ("PAN", PAN_RE),
    ("PHONE", PHONE_RE),
    ("AADHAAR", AADHAAR_RE),
    ("EMAIL", EMAIL_RE),
]

# Caller-supplied and auto-detected "named party" kinds get letter suffixes
# (PARTY_A) per CLAUDE.md's own example; regex-detected kinds get numeric
# suffixes (PAN_1). Companies are masked as PARTY too — an "Acme Pvt Ltd"
# is just as much a named party to a contract as a person is.
_LETTER_KINDS = {"PARTY"}


# --- Automatic entity detection ---------------------------------------------
# No explicit `entities` list is required for these — they run on every
# mask_text() call. This is what closes the gap that let "Ramesh Kumar"
# leak into an outbound prompt: previously PARTY/ADDR were *only* masked
# when a caller happened to pass them in explicitly.

_COMPANY_SUFFIXES = r"Pvt\.?\s*Ltd\.?|Private\s+Limited|LLP|Ltd\.?|Limited"
COMPANY_SUFFIX_RE = re.compile(
    rf"\b(?:[A-Z][\w&'.-]*\s+){{1,6}}(?:{_COMPANY_SUFFIXES})\b"
)

# Two-or-more consecutive Title-Case words — the primary personal-name
# candidate generator (see _detect_person_names for why spaCy alone isn't
# used as the gate). Generic capitalized phrases ("MG Road", "New Delhi")
# are filtered out afterward via spaCy's non-person entity labels, not by
# withholding acceptance here.
_TITLE_RUN_RE = re.compile(r"\b(?:[A-Z][a-zA-Z'-]*\s+){1,4}[A-Z][a-zA-Z'-]*\b")

_ADDRESS_KEYWORDS = (
    r"Road|Street|Marg|Nagar|Colony|Sector|Lane|Avenue|Chowk|Path|"
    r"Society|Layout|Extension|Phase|Enclave|Vihar|Puram|Gali"
)
ADDRESS_RE = re.compile(
    rf"\b\d{{1,5}}[A-Za-z]?,\s*[A-Za-z0-9.,'&\-\s]*?\b(?:{_ADDRESS_KEYWORDS})\b"
    rf"(?:[A-Za-z0-9.,'\-\s]{{0,40}})?(?:\d{{6}})?"
)

# --- Legal-terminology allowlist ---------------------------------------
# Court/tribunal names and statute references are public, structural legal
# vocabulary — never a matter's confidential party — but spaCy's small
# model doesn't reliably tag them as ORG/LAW (it missed "Consumer
# Protection Act" entirely in testing). These are matched deterministically
# and vetoed on any overlap with a candidate span, unlike the ratio-based
# spaCy veto below: a precise regex match doesn't need a tolerance margin.
_COURT_KEYWORDS_RE = re.compile(
    r"\b(?:Supreme Court|High Court|District Court|Sessions Court|Family Court|"
    r"District Commission|State Commission|National Commission|"
    r"District Consumer Disputes Redressal Commission|"
    r"State Consumer Disputes Redressal Commission|"
    r"National Consumer Disputes Redressal Commission|"
    r"Central Consumer Protection Authority|Debt Recovery Tribunal|"
    r"Income Tax Appellate Tribunal|National Company Law Tribunal|"
    r"National Green Tribunal)\b"
)

# "Consumer Protection Act 2019", "Carriage by Road Act, 2007", "the
# Indian Contract Act" (year optional).
_STATUTE_NAME_RE = re.compile(
    r"\b(?:[A-Z][\w&'-]*\s+){1,6}Act\b(?:,?\s*(?:1[89]\d{2}|20\d{2}))?"
)

# Common Indian legal/tax abbreviations lawyers type in running prose.
# Case-sensitive by design — these are always written in caps by
# convention, and case-insensitive matching would risk false hits on
# unrelated lowercase words. Longer forms (BNSS before BNS) don't
# strictly need ordering here since \b prevents BNS from matching inside
# BNSS anyway, but it's listed first for clarity.
_STATUTE_ABBREV_RE = re.compile(
    r"\b(?:CrPC|CPC|BNSS|BNS|IPC|BSA|NI Act|RERA|CGST|SGST|IGST|TDS|GST|"
    r"SEBI|RBI|FEMA|DPDP)\b"
)


# Words that must never be treated as a detected name: they're also our
# own regex-kind prefixes (PAN_1, AADHAAR_1, ...). Small NER models
# occasionally mistag the literal word "Aadhaar" (or "PAN", "Email") as a
# PERSON/ORG — if that were masked as e.g. PARTY_C, the case-insensitive
# substitution would match inside our own already-placed "AADHAAR_1"
# placeholder and corrupt it into "PARTY_C_1". Filtering these out at
# detection time closes that off at the root.
_RESERVED_KIND_WORDS = {"PAN", "PHONE", "AADHAAR", "EMAIL", "PARTY", "ADDR"}


def _is_reserved(value: str) -> bool:
    return value.strip().upper() in _RESERVED_KIND_WORDS


@functools.lru_cache(maxsize=1)
def _get_nlp():
    import spacy

    # Only tok2vec + ner are needed for entity spans — disabling the rest
    # cuts load time and per-call latency noticeably.
    return spacy.load(
        "en_core_web_sm", disable=["tagger", "parser", "attribute_ruler", "lemmatizer"]
    )


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans = sorted(spans)
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


# spaCy labels that veto a name candidate — places, organisations,
# statutes, dates, etc. NORP/LAW matter especially in legal text: "the
# Consumer Protection Act" or "Indian" must never be masked as a party.
_NON_PERSON_LABELS = {
    "GPE", "LOC", "FAC", "ORG", "DATE", "TIME", "EVENT", "LAW", "NORP",
    "LANGUAGE", "WORK_OF_ART", "PRODUCT", "MONEY", "QUANTITY", "ORDINAL",
    "CARDINAL", "PERCENT",
}


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _overlap_ratio(candidate: tuple[int, int], other: tuple[int, int]) -> float:
    start, end = max(candidate[0], other[0]), min(candidate[1], other[1])
    if end <= start:
        return 0.0
    candidate_len = candidate[1] - candidate[0]
    return (end - start) / candidate_len if candidate_len else 0.0


# A single mistagged token must not veto an otherwise-legitimate multi-word
# name — spaCy tagged just "Kesavananda" (not "Kesavananda Bharati") as
# GPE in testing, which under an any-overlap rule wiped out the whole
# candidate. Requiring the excluded span to cover most of the candidate
# fixes that false negative while still catching genuine full-span
# mistags like "The Supreme Court" -> ORG.
_SPACY_VETO_RATIO = 0.8


def _detect_person_names(text: str) -> list[str]:
    """Two-or-more consecutive Title-Case words are treated as a name
    candidate, filtered by two veto mechanisms:

    1. Deterministic legal-terminology allowlist (court/tribunal names,
       statute references, common Indian legal abbreviations) — any
       overlap vetoes, since these are precise regex matches with no need
       for a tolerance margin.
    2. spaCy's non-person entity labels (place, organisation, date, ...)
       — vetoes only when the excluded span covers most (>=80%) of the
       candidate, not on any overlap (see _SPACY_VETO_RATIO).

    This is deliberately biased toward recall over precision for
    genuinely unrecognised text. en_core_web_sm's PERSON recall on short,
    contextless sentences with Indian names is unreliable — it missed
    "Ramesh Kumar signed the notice." entirely in testing, only picking
    the name up when a PAN happened to sit nearby for context.
    Under-masking a live client's party name is the dangerous failure
    mode; over-masking a well-known case's party names is not (see the
    "no case-title allowlist" decision below) — it round-trips correctly
    via unmask_text.

    Known limitation: this misses genuine single-word (mononym) names and
    names with lowercase particles ("de Souza") — not addressed here.

    Deliberately NOT allowlisted: well-known case titles (e.g.
    "Kesavananda Bharati"). There's no maintainable finite list of
    citable precedents, and distinguishing "this is a cited precedent"
    from "this is the client's own dispute captioned as X v. Y" isn't
    reliably doable from text shape alone — the latter is exactly the
    scenario this layer exists to protect, so the safe default is to mask
    both and let unmask_text restore whichever one it was.
    """
    allowlist_spans = [
        (m.start(), m.end()) for m in _COURT_KEYWORDS_RE.finditer(text)
    ] + [
        (m.start(), m.end()) for m in _STATUTE_NAME_RE.finditer(text)
    ] + [
        (m.start(), m.end()) for m in _STATUTE_ABBREV_RE.finditer(text)
    ]

    doc = _get_nlp()(text)
    spacy_exclude_spans = [
        (e.start_char, e.end_char) for e in doc.ents if e.label_ in _NON_PERSON_LABELS
    ]

    accepted: list[tuple[int, int]] = []
    for m in _TITLE_RUN_RE.finditer(text):
        span = (m.start(), m.end())
        if _is_reserved(m.group(0)):
            continue
        if any(_spans_overlap(span, ex) for ex in allowlist_spans):
            continue
        if any(_overlap_ratio(span, ex) >= _SPACY_VETO_RATIO for ex in spacy_exclude_spans):
            continue
        accepted.append(span)

    merged = _merge_spans(accepted)
    return [text[start:end] for start, end in merged]


def _detect_companies(text: str) -> list[str]:
    return [
        m.group(0).strip()
        for m in COMPANY_SUFFIX_RE.finditer(text)
        if not _is_reserved(m.group(0))
    ]


def _detect_addresses(text: str) -> list[str]:
    return [m.group(0).strip().rstrip(",") for m in ADDRESS_RE.finditer(text)]


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


def _mask_value(masked: str, mask_map: MaskMap, kind: str, value: str) -> str:
    value = value.strip()
    if not value:
        return masked
    placeholder = mask_map.get_or_assign(kind, value)
    return re.sub(_escape(value), placeholder, masked, flags=re.IGNORECASE)


def mask_text(
    text: str,
    mask_map: MaskMap,
    entities: list[tuple[str, str]] | None = None,
) -> str:
    """Replace known and auto-detected PII with placeholders.

    `entities` is an ordered list of (kind, value) pairs the caller already
    knows are sensitive, e.g. [("PARTY", "Ramesh Kumar"), ("ADDR", "12, MG
    Road, Delhi")] — typically pulled from an intake form. These are masked
    first, taking priority over auto-detection.

    Everything else runs automatically on every call, no caller input
    required:
      - person names (Title-Case run detection, spaCy-filtered — see
        _detect_person_names)
      - company names carrying an Indian corporate suffix
        (Pvt Ltd / Private Limited / LLP / Ltd / Limited)
      - postal addresses (house/plot number + a recognised address keyword)
      - PAN, Aadhaar, email, phone numbers (regex)

    All detection runs against the original `text` so entity boundaries
    aren't thrown off by earlier substitutions; substitution itself is
    applied progressively against `masked`, so a value already consumed by
    an earlier, more specific match is simply not found again — not an
    error. This is also why PAN/phone/Aadhaar/email run *before* the NER
    pass: spaCy's small model occasionally mistags a PAN-shaped token
    (e.g. "ABCDE1234F") as a PERSON, and the structural regex should
    always win that fight.
    """
    masked = text

    for kind, value in entities or []:
        masked = _mask_value(masked, mask_map, kind, value)

    for kind, pattern in REGEX_KINDS:
        def _replace(m: re.Match[str], kind: str = kind) -> str:
            return mask_map.get_or_assign(kind, m.group(0))

        masked = pattern.sub(_replace, masked)

    for company in _detect_companies(text):
        masked = _mask_value(masked, mask_map, "PARTY", company)

    for person in _detect_person_names(text):
        masked = _mask_value(masked, mask_map, "PARTY", person)

    for address in _detect_addresses(text):
        masked = _mask_value(masked, mask_map, "ADDR", address)

    return masked


_PLACEHOLDER_RE = re.compile(r"\b[A-Z]+_[A-Z0-9]+\b")


def unmask_text(text: str, mask_map: MaskMap) -> str:
    """Restore real values for any placeholder the model echoed back."""

    def _restore(m: re.Match[str]) -> str:
        return mask_map.reverse.get(m.group(0), m.group(0))

    return _PLACEHOLDER_RE.sub(_restore, text)
