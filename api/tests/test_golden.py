"""Golden test harness (Sprint 1, Deliverable 5).

Exercises the real, live pieces — hybrid retrieval against the 129
statute chunks actually ingested in Supabase, and real LLM completions
via the gateway — while mocking only the Indian Kanoon client. The
corpus has no case-law data, so every citation the LLM produces here is
fabricated by construction; the point of this suite is to prove the
Citation Verifier's UNVERIFIED path and the renderer's hard gate hold up
against that, not to test IK itself (that's Sprint 2, against real case
names). Hitting the real IK API with fabricated names would burn real
quota for zero signal — hence the mock.

Two kinds of assertion here, deliberately different in weight:
  - Citation-gate correctness (no live <a href> for anything unverified,
    no citation silently dropped) is a hard, safety-critical invariant —
    asserted per pattern.
  - Recall@3 is a *measured* metric, not a pass/fail gate. With 5 golden
    patterns and no tuning yet, failing the whole suite over a retrieval
    miss would be noise, not signal — misses are reported in detail
    instead (requirement 6) so a human can tell a retrieval failure from
    a wrong section number in the golden JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services.citation_render import render_citation
from app.services.citations import verify_citation
from app.services.llm_gateway import generate

GOLDEN_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "golden_tests.json"


# --- Mocked IK client: always a miss, by design (see module docstring) -----


class _NeverMatchesIndianKanoonClient:
    def search(self, query: str, court: str | None = None, max_pages: int = 1) -> dict:
        return {"docs": [], "pages_fetched": 1}

    def get_doc(self, doc_id: str, maxcites: int = 0, maxcitedby: int = 0) -> dict:
        raise AssertionError(
            "get_doc() should never be called — search() never returns a match, "
            "so nothing should ever reach the doc-fetch confirmation step"
        )


# --- Minimal in-memory citations table, isolated from the live DB ----------
# verify_citation() writes here instead of the real Supabase citations
# table — this suite fabricates citation names by design and shouldn't
# pollute the live cache with them.


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: dict[str, object] = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def is_(self, col, _val):
        self._filters[col] = None
        return self

    def limit(self, _n):
        return self

    def execute(self):
        matches = [r for r in self._rows if all(r.get(c) == v for c, v in self._filters.items())]

        class R:
            data = matches

        return R()


class _FakeInsert:
    def __init__(self, table: "_FakeCitationsTable", record: dict):
        self._table = table
        self._record = record

    def execute(self):
        self._table.rows.append(dict(self._record))

        class R:
            data = [self._record]

        return R()


class _FakeCitationsTable:
    def __init__(self):
        self.rows: list[dict] = []

    def select(self, *_a, **_k):
        return _FakeQuery(self.rows)

    def insert(self, record):
        return _FakeInsert(self, record)


class _FakeCitationsDB:
    def __init__(self):
        self._citations = _FakeCitationsTable()

    def table(self, name: str):
        assert name == "citations"
        return self._citations


# --- Citation extraction from free-form LLM text ----------------------------
# Line-anchored, not a single global scan: an earlier version used a
# character class containing "." for party names (to allow abbreviations
# like "S.K. Transport Co.") combined with a non-greedy match and a
# "stop at the next period" lookahead — which meant the non-greedy engine
# was satisfied the instant it hit the FIRST embedded period in an
# abbreviated name ("P.K. Enterprises" got truncated to "P.K"). Matching
# per line against an unambiguous end-of-line anchor sidesteps that: the
# prompt asks for one citation per line, so there's no need to guess
# where a citation ends mid-string.
_CITATION_LINE_RE = re.compile(
    r"^\s*[*\-•]?\s*(.+?)\s+(?:vs\.?|versus|v\.)\s+(.+?)\s*(?:\((\d{4})\))?\s*\.?\s*$",
    re.IGNORECASE,
)


def _extract_citations(text: str) -> list[str]:
    citations = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _CITATION_LINE_RE.match(line)
        if not m:
            continue
        party_a, party_b, year = m.group(1).strip(" *-"), m.group(2).strip(), m.group(3)
        # Guard against a stray prose sentence containing " v. " matching
        # as a false positive: a real citation line is short and both
        # sides look like proper names (start with a capital letter).
        if not (party_a[:1].isupper() and party_b[:1].isupper()):
            continue
        if len(party_a) > 80 or len(party_b) > 80:
            continue
        name = f"{party_a} v. {party_b}"
        if year:
            name += f" ({year})"
        citations.append(name)
    return citations


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture(scope="module")
def golden_patterns():
    return json.loads(GOLDEN_PATH.read_text())


@pytest.fixture
def api_client():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="golden-test-user", email="golden@example.com", db=None
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- The suite ---------------------------------------------------------------


def test_golden_patterns(golden_patterns, api_client):
    rows = []
    misses = []
    hard_failures = []

    for pattern in golden_patterns:
        pattern_id = pattern["id"]
        expected_pairs = {
            (act, section)
            for act, sections in pattern["expected_sections"].items()
            for section in sections
        }

        # --- Recall@3 -----------------------------------------------------
        resp = api_client.post(
            "/api/retrieve",
            json={"facts": pattern["facts"], "top_k": 3},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200, f"{pattern_id}: /api/retrieve returned {resp.status_code}: {resp.text}"
        retrieved = resp.json()
        retrieved_pairs = [(r["act"], r["section_no"]) for r in retrieved]
        hit_pairs = expected_pairs & set(retrieved_pairs)
        recall_hit = bool(hit_pairs)

        if not recall_hit:
            misses.append({"id": pattern_id, "expected": sorted(expected_pairs), "retrieved": retrieved_pairs})

        # --- Citations exercise --------------------------------------------
        # The straightforward phrasing here ("cite 2-3 case law precedents")
        # was tried first and the model correctly refused on 3/5 patterns,
        # citing its own system-prompt instruction against inventing case
        # law without retrieval context — which is the system working as
        # designed, but leaves nothing for this test to exercise. Framing
        # the request as an explicit illustrative/hypothetical exercise
        # gets past that honestly (it's not asking the model to deceive a
        # real user — there is no real user here) and reliably produces
        # parseable output. The Verifier doesn't care why a citation is
        # fabricated, only that it correctly resolves to UNVERIFIED.
        prompt = (
            f"Facts: {pattern['facts']}\n\n"
            "For this drafting exercise, give a short (2-3 sentence) answer, then "
            "list 2-3 illustrative example case citations of the kind that would "
            "typically support this position — even if hypothetical or from memory — "
            "in the format 'Party A v. Party B (Year)', one per line, under a "
            "'Citations:' heading. This is a drafting exercise to test a downstream "
            "citation-verification system, not legal advice that will be relied on "
            "directly."
        )
        result = generate(prompt, task_type="consulting_analyst")
        extracted = _extract_citations(result.text)

        fake_db = _FakeCitationsDB()
        ik = _NeverMatchesIndianKanoonClient()
        verified_count = 0
        flagged_count = 0
        for case_name in extracted:
            record = verify_citation(case_name, ik_client=ik, db=fake_db)
            rendered = render_citation(record)
            if record.status == "verified":
                verified_count += 1
            if not rendered.renderable:
                flagged_count += 1
                if "<a href" in rendered.html:
                    hard_failures.append(
                        f"{pattern_id}: unverified citation {case_name!r} rendered with a live link"
                    )
            elif "<a href" not in rendered.html:
                hard_failures.append(
                    f"{pattern_id}: citation {case_name!r} marked renderable but produced no <a href>"
                )

        if len(extracted) != flagged_count + verified_count:
            hard_failures.append(
                f"{pattern_id}: {len(extracted)} citation(s) produced but only "
                f"{flagged_count + verified_count} accounted for (verified+flagged) — silent drop"
            )

        rows.append(
            {
                "pattern_id": pattern_id,
                "domain": pattern["domain"],
                "top_expected_hit": ", ".join(f"{a} §{s}" for a, s in sorted(hit_pairs)) or "MISS",
                "recall@3": "HIT" if recall_hit else "MISS",
                "citations_produced": len(extracted),
                "citations_verified": verified_count,
                "citations_flagged": flagged_count,
                "notes": "" if extracted else "LLM produced no extractable citations",
            }
        )

    # --- Report ------------------------------------------------------------
    header = "|pattern_id|domain|top_expected_hit|recall@3|citations_produced|citations_verified|citations_flagged|notes|"
    sep = "|" + "|".join(["---"] * 8) + "|"
    print("\n" + header)
    print(sep)
    for r in rows:
        print(
            f"|{r['pattern_id']}|{r['domain']}|{r['top_expected_hit']}|{r['recall@3']}|"
            f"{r['citations_produced']}|{r['citations_verified']}|{r['citations_flagged']}|{r['notes']}|"
        )

    hit_count = sum(1 for r in rows if r["recall@3"] == "HIT")
    print(f"\nOverall recall@3: {hit_count}/{len(rows)}")

    if misses:
        print("\n--- Retrieval misses (for diagnosis: retrieval bug vs. golden-test error) ---")
        for m in misses:
            print(f"{m['id']}: expected {m['expected']}, retrieved {m['retrieved']}")

    # Hard, safety-critical assertions — the citation gate must never regress.
    assert not hard_failures, "\n".join(hard_failures)
