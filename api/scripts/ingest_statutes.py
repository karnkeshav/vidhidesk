#!/usr/bin/env python3
"""Statute ingestion pipeline (Sprint 1, deliverable 1).

Walks /corpus/*.pdf, extracts text with PyMuPDF, chunks at section level,
embeds each chunk locally (BAAI/bge-small-en-v1.5 — free, no API cost,
per CLAUDE.md's embeddings choice), and upserts into statute_chunks
keyed on (act, section_no) so re-running the same PDF never creates
duplicates.

Run from /api:
    source .venv/bin/activate
    python scripts/ingest_statutes.py [pdf_path ...]

With no arguments, ingests every *.pdf under /corpus.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF  # noqa: E402

from app.db import service_client  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus"

# --- Act metadata (name + year) -------------------------------------------
# A bare act PDF's title page states the short title and year, but
# formatting is inconsistent across acts (and, for gazette-sourced PDFs,
# interleaved with mojibake Hindi text — see _is_noise_line below) — so
# ingestion is keyed off explicit per-file config rather than parsed out
# of the PDF header text.
ACT_CONFIG: dict[str, dict] = {
    "consumer_protection_act_2019.pdf": {
        "act": "Consumer Protection Act, 2019",
        "year": 2019,
    },
    "carriage_by_road_act_2007.pdf": {
        "act": "Carriage by Road Act, 2007",
        "year": 2007,
    },
    "indian_contract_act_1872.pdf": {
        "act": "Indian Contract Act, 1872",
        "year": 1872,
    },
    "indian_stamp_act_1899.pdf": {
        "act": "Indian Stamp Act, 1899",
        "year": 1899,
    },
    "registration_act_1908.pdf": {
        "act": "Registration Act, 1908",
        "year": 1908,
    },
    "transfer_of_property_act_1882.pdf": {
        "act": "Transfer of Property Act, 1882",
        "year": 1882,
    },
    # --- Sprint 3.6 Phase 1 corpus expansion (TICKET-16) ---------------
    "limitation_act_1963.pdf": {
        "act": "Limitation Act, 1963",
        "year": 1963,
    },
    "code_of_civil_procedure_1908.pdf": {
        "act": "Code of Civil Procedure, 1908",
        "year": 1908,
    },
    "specific_relief_act_1963.pdf": {
        "act": "Specific Relief Act, 1963",
        "year": 1963,
    },
    "indian_easements_act_1882.pdf": {
        "act": "Indian Easements Act, 1882",
        "year": 1882,
    },
    "real_estate_regulation_development_act_2016.pdf": {
        "act": "Real Estate (Regulation and Development) Act, 2016",
        "year": 2016,
    },
    "commercial_courts_act_2015.pdf": {
        "act": "Commercial Courts Act, 2015",
        "year": 2015,
    },
}


def _act_config_for(pdf_path: Path) -> dict:
    config = ACT_CONFIG.get(pdf_path.name)
    if config:
        return config
    # Fallback for PDFs the user drops in without registering them here:
    # derive a reasonable act name from the filename, leave year unset.
    stem = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    return {"act": stem.title(), "year": None}


@dataclass
class Chunk:
    act: str
    section_no: str
    year: int | None
    text: str


# --- Section-level chunking -------------------------------------------------
# Bare Acts from India Code follow a consistent convention: a numbered
# section header at the start of a line — "18. Complaint to State
# Commission.—(1) ..." (sometimes with no heading text before the first
# sub-section, e.g. "1. (1) This Act may be called...") — optionally with
# a trailing letter for inserted sections ("65A."). Sub-sections like
# "(1)", "(2)" appear *inside* a section's body — the (act, section_no)
# natural key operates at section level, so a subsection marker must
# never be mistaken for a new section boundary. Requiring the digits be
# followed immediately by ". " and then a capital letter, dash, or "("
# achieves that: "(2) It extends..." starts with "(", not a digit, so it
# can never match the boundary pattern in the first place.
# Sprint 3.6 Phase 1 (TICKET-16) extension: an inserted/amended provision
# is conventionally rendered "1[2. Pleading to state material facts...—...]"
# — a footnote-reference digit and "[" bracket glued directly in front of
# the real section/rule number, with no whitespace between them. The
# original pattern's `^\s*` line-start anchor never reaches the real
# number in that shape, silently merging the whole provision into whatever
# boundary preceded it (found via CPC Order VI Rule 2 and Order VIII Rule
# 1 both going missing/wrong during the First Schedule ingestion this
# sprint — not new to CPC, just newly exercised heavily enough by CPC's
# amendment-marker density to surface). The optional non-capturing
# `(?:\d{1,3}[A-Z]?\[)?` prefix absorbs that footnote marker without
# capturing it, so group(1) is always the real section/rule number either
# way.
_SECTION_BOUNDARY_RE = re.compile(
    r"(?m)^\s*(?:\d{1,3}[A-Z]?\[)?(\d{1,3}[A-Z]?)\.[ \t]+(?=[A-Z—–(])"
)

_ENACTING_CLAUSE_RE = re.compile(r"BE it enacted by Parliament", re.IGNORECASE)

# Gazette/running-header noise lines, stripped from chunk text before
# embedding. Two strategies: (1) known boilerplate phrases, and (2) a
# generic heuristic for the mojibake Hindi blocks that gazette PDFs embed
# (custom-font Hindi glyphs extract as Latin-range garbage) — real English
# legal prose always contains vowels; these garbled lines essentially
# never do.
_NOISE_LINE_RES = [
    re.compile(r"^\d{1,4}$"),  # bare page number
    re.compile(r"gazette of india", re.IGNORECASE),
    re.compile(r"extraordinary", re.IGNORECASE),
    re.compile(r"^\[?part\s+[ivx]+", re.IGNORECASE),
    re.compile(r"^registered no", re.IGNORECASE),
    re.compile(r"^ministry of law and justice", re.IGNORECASE),
    re.compile(r"^\(legislative department\)", re.IGNORECASE),
    re.compile(r"published\s+by\s+authority", re.IGNORECASE),
    re.compile(r"^no\.\s*\d+\]"),
    re.compile(r"^new delhi,", re.IGNORECASE),
]
_HAS_VOWEL_RE = re.compile(r"[aeiouAEIOU]")
_HAS_ALPHA_RE = re.compile(r"[a-zA-Z]")


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if any(p.search(stripped) for p in _NOISE_LINE_RES):
        return True
    # Vowel-less alphabetic line of any real length -> almost certainly a
    # mojibake Hindi fragment, not English legal prose.
    if len(stripped) >= 6 and _HAS_ALPHA_RE.search(stripped) and not _HAS_VOWEL_RE.search(stripped):
        return True
    return False


def _clean_chunk_text(raw: str, act: str) -> str:
    act_upper_variants = {act.upper(), f"THE {act.upper()}".replace(",", "")}
    lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        normalized = re.sub(r"[^\w\s]", "", stripped).upper().strip()
        if normalized in act_upper_variants:
            continue
        if _is_noise_line(line):
            continue
        lines.append(stripped)
    # Collapse the blank-line runs left behind by dropped noise lines.
    text = "\n".join(lines)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def chunk_sections(full_text: str, act: str, year: int | None) -> list[Chunk]:
    # The "Arrangement of Sections" table of contents repeats every
    # section number in the same "N. Title." shape as a real header, with
    # no body text — ingesting it would create a spurious short chunk per
    # section that competes with the real one on upsert. The enacting
    # clause ("BE it enacted by Parliament...") reliably marks the end of
    # front matter (title page + TOC) and the start of the actual Act
    # across every India Code bare act, so we simply start looking for
    # section boundaries after it.
    enacting_match = _ENACTING_CLAUSE_RE.search(full_text)
    body = full_text[enacting_match.end():] if enacting_match else full_text

    boundaries = list(_SECTION_BOUNDARY_RE.finditer(body))
    if not boundaries:
        return []

    chunks: list[Chunk] = []
    seen_sections: set[str] = set()
    for i, m in enumerate(boundaries):
        section_no = m.group(1)
        start = m.start()
        end = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(body)
        raw_section_text = body[start:end].strip()
        section_text = _clean_chunk_text(raw_section_text, act)

        if not section_text or len(section_text) < 20:
            continue
        # Keep the first (fuller) occurrence if a section number somehow
        # repeats — upsert on (act, section_no) means only one row
        # survives in the DB regardless, but this avoids a short/noise
        # chunk racing the real one within a single ingestion run.
        if section_no in seen_sections:
            continue
        seen_sections.add(section_no)

        chunks.append(Chunk(act=act, section_no=section_no, year=year, text=section_text))

    return chunks


# --- CPC First Schedule (Orders/Rules) — Sprint 3.6 Phase 1 extension ------
# CPC 1908 is the one act in this corpus with a second body of substantive
# text — the First Schedule's 51 Orders, each containing its own Rules —
# governed by a completely different numbering scheme ("ORDER VII" / "Rule
# 1") than the numbered-Section boundary regex above handles. Two real
# problems if this is ignored: (1) the Order VI/VII/VIII pleading-structure
# rules and Order XXXVIII/XXXIX injunction/attachment rules — exactly what
# pleading generation depends on — would simply never be ingested; (2) each
# Order's own Rule numbering restarts at 1, so a rule boundary looks
# identical in shape to a Section boundary ("1. Particulars to be contained
# in plaint.—...") — reusing chunk_sections()'s dedup-by-section_no as-is
# would either silently drop every Rule 1..N behind whichever Section 1..N
# was chunked first, or (worse) collide two unrelated chunks under the same
# key. Keying Schedule chunks as "Order VII Rule 1" rather than bare "1"
# avoids both failure modes without changing chunk_sections() or its
# dedup logic at all.
_ORDER_BOUNDARY_RE = re.compile(r"(?m)^ORDER\s+([IVXLCM]+[A-Z]?)\b")


def _find_schedule_body_start(text: str) -> int | None:
    """The First Schedule's real Rule text is preceded by an
    "Arrangement of Rules" table of contents earlier in the document,
    using the identical "ORDER <roman>" heading shape but title-only, no
    rule bodies. Distinguish the two by requiring an em-dash within the
    first 400 characters after "ORDER I" — every real bare-act rule body
    in this corpus's format carries one ("1. Who may be joined as
    plaintiffs.—All persons..."), the TOC listing never does (bare
    titles, no dash)."""
    for m in re.finditer(r"(?m)^ORDER\s+I\b", text):
        if "—" in text[m.start() : m.start() + 400]:
            return m.start()
    return None


def chunk_cpc_schedule(full_text: str, act: str, year: int | None) -> list[Chunk]:
    """Chunk the First Schedule's Orders/Rules, additive to (never
    replacing) chunk_sections()'s numbered-Section chunks for the same
    PDF. Returns [] harmlessly if the body marker isn't found rather than
    raising — a schema/format change in a future India Code re-download
    should degrade to "no Schedule content", not break Section
    ingestion, which chunk_sections() handles independently."""
    body_start = _find_schedule_body_start(full_text)
    if body_start is None:
        return []

    order_boundaries = list(_ORDER_BOUNDARY_RE.finditer(full_text, body_start))
    if not order_boundaries:
        return []

    chunks: list[Chunk] = []
    seen: set[str] = set()
    for i, om in enumerate(order_boundaries):
        order_no = om.group(1)
        order_start = om.start()
        order_end = order_boundaries[i + 1].start() if i + 1 < len(order_boundaries) else len(full_text)
        order_text = full_text[order_start:order_end]

        rule_boundaries = list(_SECTION_BOUNDARY_RE.finditer(order_text))
        for j, rm in enumerate(rule_boundaries):
            rule_no = rm.group(1)
            r_start = rm.start()
            r_end = rule_boundaries[j + 1].start() if j + 1 < len(rule_boundaries) else len(order_text)
            raw = order_text[r_start:r_end].strip()
            cleaned = _clean_chunk_text(raw, act)
            if not cleaned or len(cleaned) < 20:
                continue

            section_no = f"Order {order_no} Rule {rule_no}"
            if section_no in seen:
                continue
            seen.add(section_no)
            chunks.append(Chunk(act=act, section_no=section_no, year=year, text=cleaned))

    return chunks


# --- Embeddings + upsert -----------------------------------------------------

_model = None


def _get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model


def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    if not chunks:
        return []
    model = _get_embedding_model()
    # BAAI/bge-small-en-v1.5's own model card: no instruction prefix on
    # the document/passage side (only queries get one, at retrieval time
    # — see app/services/retrieval.py's QUERY_INSTRUCTION). This is the
    # opposite convention from e5-style models ("passage: "/"query: "
    # symmetric prefixes) — don't carry that pattern over by habit.
    texts = [c.text for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def upsert_chunks(chunks: list[Chunk], embeddings: list[list[float]], db=None) -> int:
    if not chunks:
        return 0
    db = db if db is not None else service_client()
    records = [
        {
            "act": c.act,
            "section_no": c.section_no,
            "year": c.year,
            "text": c.text,
            "embedding": emb,
        }
        for c, emb in zip(chunks, embeddings)
    ]
    db.table("statute_chunks").upsert(records, on_conflict="act,section_no").execute()
    return len(records)


def ingest_pdf(pdf_path: Path, db=None, dry_run: bool = False) -> list[Chunk]:
    config = _act_config_for(pdf_path)
    full_text = extract_text(pdf_path)
    chunks = chunk_sections(full_text, config["act"], config["year"])

    schedule_chunks: list[Chunk] = []
    if config["act"] == "Code of Civil Procedure, 1908":
        schedule_chunks = chunk_cpc_schedule(full_text, config["act"], config["year"])
        chunks = chunks + schedule_chunks

    print(f"{pdf_path.name}: {len(chunks)} chunk(s) for {config['act']!r}"
          + (f" ({len(chunks) - len(schedule_chunks)} Sections + {len(schedule_chunks)} First Schedule Order/Rule chunks)" if schedule_chunks else ""))
    for c in chunks[:3]:
        preview = c.text[:160].replace("\n", " ")
        print(f"  section {c.section_no}: {preview}...")

    if not dry_run:
        embeddings = embed_chunks(chunks)
        n = upsert_chunks(chunks, embeddings, db=db)
        print(f"  upserted {n} row(s) into statute_chunks")

    return chunks


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    pdf_paths = [Path(a) for a in args] if args else sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {CORPUS_DIR} and none given on the command line.")
        return 1

    total = 0
    for pdf_path in pdf_paths:
        chunks = ingest_pdf(pdf_path, dry_run=dry_run)
        total += len(chunks)

    print(f"\nDone. {total} chunk(s) across {len(pdf_paths)} PDF(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
