"""Tests for the Citation Verifier state machine (TRD §3.3, Sprint 1).

Core guarantees under test:
  - a repeated lookup never re-calls the Indian Kanoon API (cache-first)
  - ik_doc_id is always the tid confirmed via a GET /doc/{id}/ fetch,
    never trusted straight off a /search/ hit
  - query construction is structured (party/year/court), never a raw
    concept phrase
  - first-pass -> retry-pass -> unverified state machine matches TRD §3.3
  - a citation only ever carries a doc id / URL when a real match was
    confirmed — never fabricated
"""

from app.services.citations import normalize_case_name, parse_case_name, verify_citation


class FakeIndianKanoonClient:
    """Records every call so tests can assert on cache-first behaviour and
    on exactly what queries were constructed."""

    def __init__(self, search_results: list[list[dict]] | None = None, docs: dict[str, dict] | None = None):
        # search_results: one list of hits per successive search() call,
        # consumed in order (so pass [first_pass_hits, retry_pass_hits]).
        self._search_results = list(search_results or [])
        self._docs = docs or {}
        self.search_calls: list[tuple[str, str | None]] = []
        self.get_doc_calls: list[str] = []

    def search(self, query: str, court: str | None = None, max_pages: int = 1) -> dict:
        self.search_calls.append((query, court))
        docs = self._search_results.pop(0) if self._search_results else []
        return {"docs": docs, "pages_fetched": 1}

    def get_doc(self, doc_id: str) -> dict:
        self.get_doc_calls.append(doc_id)
        if doc_id not in self._docs:
            raise KeyError(f"no fake doc registered for {doc_id!r}")
        return self._docs[doc_id]


class FakeQuery:
    def __init__(self, table: "FakeTable"):
        self._table = table
        self._filters: dict[str, object] = {}

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def eq(self, column: str, value) -> "FakeQuery":
        self._filters[column] = value
        return self

    def is_(self, column: str, _value: str) -> "FakeQuery":
        self._filters[column] = None
        return self

    def limit(self, _n: int) -> "FakeQuery":
        return self

    def execute(self) -> "FakeResponse":
        matches = [
            row
            for row in self._table.rows
            if all(row.get(col) == val for col, val in self._filters.items())
        ]
        return FakeResponse(matches)


class FakeInsert:
    def __init__(self, table: "FakeTable", record: dict):
        self._table = table
        self._record = record

    def execute(self) -> "FakeResponse":
        # case_name_normalized is no longer a DB-generated column (see
        # migration 0005) — it's a plain NOT NULL column the app must
        # populate itself. Mirror that here instead of silently computing
        # a fallback: a caller that forgets to set it should fail loudly,
        # the same way a real NOT NULL violation would.
        row = dict(self._record)
        if row.get("case_name_normalized") is None:
            raise ValueError(
                "case_name_normalized is required (NOT NULL) — the caller must "
                "compute it via normalize_case_name(), it is not auto-generated"
            )
        # Real schema: id uuid primary key default gen_random_uuid()
        # (migration 0001) — mirrored here so a recheck's later
        # .update(...).eq("id", cached_row["id"]) has something real to
        # match against, same as it would against production Postgres.
        row.setdefault("id", f"fake-id-{len(self._table.rows) + 1}")
        self._table.rows.append(row)
        return FakeResponse([row])


class FakeResponse:
    def __init__(self, data: list[dict]):
        self.data = data


class FakeUpdateQuery:
    """Sprint 3.6 Phase 5 (TICKET-17): supports the
    .update(record).eq("id", ...).execute() path verify_citation() now
    takes when rechecking a cached "unverified" row."""

    def __init__(self, table: "FakeTable", record: dict):
        self._table = table
        self._record = record
        self._filters: dict[str, object] = {}

    def eq(self, column: str, value) -> "FakeUpdateQuery":
        self._filters[column] = value
        return self

    def execute(self) -> FakeResponse:
        updated = []
        for row in self._table.rows:
            if all(row.get(col) == val for col, val in self._filters.items()):
                row.update(self._record)
                updated.append(row)
        return FakeResponse(updated)


class FakeTable:
    def __init__(self):
        self.rows: list[dict] = []

    def select(self, *_args, **_kwargs) -> FakeQuery:
        return FakeQuery(self)

    def insert(self, record: dict) -> FakeInsert:
        return FakeInsert(self, record)

    def update(self, record: dict) -> FakeUpdateQuery:
        return FakeUpdateQuery(self, record)


class FakeSupabase:
    def __init__(self):
        self._tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        return self._tables.setdefault(name, FakeTable())


# --- parse_case_name ---------------------------------------------------------


def test_parse_case_name_splits_on_vs_and_extracts_year():
    party_a, party_b, year = parse_case_name("Kesavananda Bharati vs State of Kerala (1973)")
    assert party_a == "Kesavananda Bharati"
    assert party_b == "State of Kerala"
    assert year == 1973


def test_parse_case_name_handles_v_dot_and_versus():
    assert parse_case_name("Ramesh v. Suresh")[:2] == ("Ramesh", "Suresh")
    assert parse_case_name("Ramesh versus Suresh")[:2] == ("Ramesh", "Suresh")


def test_parse_case_name_falls_back_to_single_party_when_unparseable():
    party_a, party_b, year = parse_case_name("Some Random Statute Reference")
    assert party_a == "Some Random Statute Reference"
    assert party_b == ""


def test_parse_case_name_pulls_year_from_neutral_citation_if_absent_from_name():
    _, _, year = parse_case_name("Ramesh vs Suresh", neutral_citation="AIR 1973 SC 1461")
    assert year == 1973


def test_parse_case_name_handles_bare_v_no_period():
    """IK titles occasionally drop the period on "v" — must split the
    same as "vs"/"v."/"versus", not fall through to single-party."""
    assert parse_case_name("Ramesh Kumar v Sunita Sharma")[:2] == (
        "Ramesh Kumar", "Sunita Sharma",
    )


# --- normalize_case_name: the citations-table cache key ---------------------


def test_normalize_case_name_collapses_vs_variants_to_the_same_key():
    variants = [
        "Ramesh Kumar vs Sunita Sharma",
        "Ramesh Kumar vs. Sunita Sharma",
        "Ramesh Kumar v. Sunita Sharma",
        "Ramesh Kumar v Sunita Sharma",
        "Ramesh Kumar versus Sunita Sharma",
    ]
    normalized = {normalize_case_name(v) for v in variants}
    assert len(normalized) == 1


def test_normalize_case_name_strips_party_count_suffixes():
    with_suffix = normalize_case_name("Ramesh Kumar vs Sunita Sharma and Ors.")
    without_suffix = normalize_case_name("Ramesh Kumar vs Sunita Sharma")
    assert with_suffix == without_suffix

    for suffix_variant in [
        "Ramesh Kumar vs Sunita Sharma and Anr.",
        "Ramesh Kumar vs Sunita Sharma & Ors",
        "Ramesh Kumar vs Sunita Sharma and Another",
        "Ramesh Kumar vs Sunita Sharma and Others",
    ]:
        assert normalize_case_name(suffix_variant) == without_suffix


def test_normalize_case_name_strips_trailing_ellipsis_and_whitespace_noise():
    assert normalize_case_name("Ramesh Kumar vs Sunita Sharma...") == normalize_case_name(
        "Ramesh Kumar vs Sunita Sharma"
    )
    assert normalize_case_name("  Ramesh   Kumar  vs   Sunita  Sharma  ") == normalize_case_name(
        "Ramesh Kumar vs Sunita Sharma"
    )


def test_normalize_case_name_is_case_insensitive():
    assert normalize_case_name("RAMESH KUMAR VS SUNITA SHARMA") == normalize_case_name(
        "ramesh kumar vs sunita sharma"
    )


def test_normalize_case_name_real_world_noise_combo():
    """All four kinds of noise at once — the scenario that actually
    motivated this fix."""
    a = normalize_case_name("Ramesh Kumar and Anr. vs. Sunita Sharma and Ors...")
    b = normalize_case_name("ramesh kumar v sunita sharma")
    assert a == b


# --- query construction: structured, never a concept phrase ----------------


def test_first_pass_query_is_structured_party_year_not_concept_phrase():
    ik = FakeIndianKanoonClient(search_results=[[]])
    db = FakeSupabase()

    verify_citation(
        "Kesavananda Bharati vs State of Kerala (1973)", court="supremecourt", ik_client=ik, db=db
    )

    assert len(ik.search_calls) >= 1
    first_query, first_court = ik.search_calls[0]
    assert first_query == "Kesavananda Bharati vs State of Kerala 1973"
    assert first_court == "supremecourt"
    # Never a concept phrase like "Carriage by Road Act damages".
    assert "damages" not in first_query.lower()
    assert "act" not in first_query.lower()


def test_retry_pass_query_drops_year_and_court():
    ik = FakeIndianKanoonClient(search_results=[[], []])
    db = FakeSupabase()

    verify_citation(
        "Kesavananda Bharati vs State of Kerala (1973)", court="supremecourt", ik_client=ik, db=db
    )

    assert len(ik.search_calls) == 2
    retry_query, retry_court = ik.search_calls[1]
    assert retry_query == "Kesavananda Bharati State of Kerala"
    assert retry_court is None


# --- tid confirmation via get_doc(), never trusting the search hit ---------


def test_ik_doc_id_comes_from_get_doc_tid_not_search_hit_docid():
    # The search hit's own "tid" is deliberately wrong/stale here — only
    # the get_doc() fetch's tid must end up in ik_doc_id.
    ik = FakeIndianKanoonClient(
        search_results=[[{"title": "Kesavananda Bharati vs State of Kerala", "tid": "999-wrong"}]],
        docs={"999-wrong": {"tid": "12345", "docsource": "Supreme Court", "publishdate": "1973-04-24"}},
    )
    db = FakeSupabase()

    result = verify_citation("Kesavananda Bharati vs State of Kerala (1973)", ik_client=ik, db=db)

    assert ik.get_doc_calls == ["999-wrong"]
    assert result.status == "verified"
    assert result.ik_doc_id == "12345"
    assert result.ik_url == "https://indiankanoon.org/doc/12345/"


def test_no_tid_in_doc_response_refuses_to_verify():
    """If get_doc() somehow returns no tid, we must not fabricate one —
    the citation falls through to unverified instead of half-verifying."""
    ik = FakeIndianKanoonClient(
        search_results=[
            [{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}],
            [{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}],
        ],
        docs={"1": {"docsource": "Delhi HC"}},  # no "tid" key
    )
    db = FakeSupabase()

    result = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)

    assert result.status == "unverified"
    assert result.ik_doc_id is None
    assert result.ik_url is None


# --- state machine: first-pass -> retry-pass -> unverified ------------------


def test_first_pass_match_short_circuits_retry_pass():
    ik = FakeIndianKanoonClient(
        search_results=[[{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}]],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    result = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)

    assert result.status == "verified"
    assert len(ik.search_calls) == 1  # retry-pass never ran


def test_first_pass_miss_falls_through_to_retry_pass_match():
    ik = FakeIndianKanoonClient(
        search_results=[
            [],  # first pass: nothing
            [{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}],  # retry pass: match
        ],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    result = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)

    assert result.status == "verified"
    assert len(ik.search_calls) == 2


def test_both_passes_miss_stores_unverified_with_no_url():
    ik = FakeIndianKanoonClient(search_results=[[], []])
    db = FakeSupabase()

    result = verify_citation("Zzqxvthorpe Nonexistent vs Fictional Litigant (2020)", ik_client=ik, db=db)

    assert result.status == "unverified"
    assert result.ik_doc_id is None
    assert result.ik_url is None
    assert len(ik.search_calls) == 2


def test_unparseable_single_party_name_skips_retry_pass():
    """No party_b to build a retry query from — don't bother, go straight
    to unverified after the first pass misses."""
    ik = FakeIndianKanoonClient(search_results=[[]])
    db = FakeSupabase()

    result = verify_citation("Some Random Statute Reference", ik_client=ik, db=db)

    assert result.status == "unverified"
    assert len(ik.search_calls) == 1


# --- cache-first: never re-call the API for a known citation ---------------


def test_cache_hit_never_calls_the_api():
    ik = FakeIndianKanoonClient(
        search_results=[[{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}]],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    first = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)
    assert first.from_cache is False
    assert len(ik.search_calls) == 1

    second = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)
    assert second.from_cache is True
    assert second.ik_doc_id == "1"
    assert len(ik.search_calls) == 1  # unchanged — no repeat API call


def test_cache_key_distinguishes_by_neutral_citation():
    """Same case name, different neutral citations (e.g. reported in two
    different reporters) — must not collide in the cache."""
    # Each call misses both passes (first-pass + retry-pass), so two
    # distinct verify_citation() calls make 4 search calls total — the
    # property under test is that it's 4, not 2 (i.e. the second call
    # wasn't a cache hit that skipped searching entirely).
    ik = FakeIndianKanoonClient(search_results=[[], [], [], []])
    db = FakeSupabase()

    verify_citation("Ramesh Kumar vs Sunita Sharma", neutral_citation="2020 SCC 1", ik_client=ik, db=db)
    verify_citation("Ramesh Kumar vs Sunita Sharma", neutral_citation="2020 AIR 5", ik_client=ik, db=db)

    assert len(ik.search_calls) == 4  # both were genuine cache misses


# --- Sprint 3.6 Phase 5 (TICKET-17/18): reliability improvements ------------


def test_match_confidence_is_recorded_on_a_verified_citation():
    """_best_match()'s own word-overlap score (previously computed and
    discarded) is now persisted, not just a bare verified/unverified bool."""
    ik = FakeIndianKanoonClient(
        search_results=[[{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}]],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    result = verify_citation("Ramesh Kumar vs Sunita Sharma (2020)", ik_client=ik, db=db)

    assert result.status == "verified"
    assert result.match_confidence is not None
    assert 0.0 <= result.match_confidence <= 1.0


def test_cached_unverified_citation_gets_one_fresh_live_recheck_not_trusted_forever():
    """Regression test for TICKET-17: a real Supreme Court case
    (Anathula Sudhakar v. P. Buchi Reddy) came back "unverified" during the
    Sprint 3.5.6 certification round, then "verified" on an immediate
    independent retry with the identical case name — live IK search
    ranking is non-deterministic call-to-call. Before this sprint,
    verify_citation() cached the first "unverified" result and returned it
    forever on every subsequent call for the same case name, with no way
    to ever recover. It must now re-attempt live verification on a cached
    "unverified" hit rather than trusting a single past negative forever."""
    ik = FakeIndianKanoonClient(
        # First call: both passes miss (transient ranking miss).
        search_results=[[], [], [{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}]],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    first = verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)
    assert first.status == "unverified"
    assert first.from_cache is False
    assert len(ik.search_calls) == 2  # first-pass + retry-pass, both missed

    # Second call: cached row is "unverified" — must NOT short-circuit on
    # the stale cache; must make at least one more live attempt.
    second = verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)
    assert second.status == "verified"
    assert second.ik_doc_id == "1"
    assert second.recheck_count == 1
    assert len(ik.search_calls) == 3  # one more live attempt was made, not skipped

    # The cache row was updated in place, not duplicated.
    assert len(db.table("citations").rows) == 1


def test_cached_verified_citation_never_rechecked():
    """The other half of TICKET-17's fix: a "verified" cache hit must
    still short-circuit exactly as before — only "unverified" hits are
    untrusted-by-default now, not every cache hit."""
    ik = FakeIndianKanoonClient(
        search_results=[[{"title": "Ramesh Kumar vs Sunita Sharma", "tid": "1"}]],
        docs={"1": {"tid": "1", "docsource": "Delhi HC", "publishdate": "2020-01-01"}},
    )
    db = FakeSupabase()

    verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)
    verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)
    verify_citation("Ramesh Kumar vs Sunita Sharma", ik_client=ik, db=db)

    assert len(ik.search_calls) == 1  # unchanged across all 3 calls
