"""Tests for the renderer-side citation hard gate (CLAUDE.md Hard Rule 1).

The one property that must never regress: an unverified citation can
never produce a hyperlink, no matter what fields happen to be populated
on the record. This is enforced in code, not in a prompt — these tests
exercise that code path directly.
"""

from app.services.citation_render import (
    UNVERIFIED_LABEL,
    render_citation,
    render_citation_by_lookup,
)
from app.services.citations import CitationRecord


def _record(**overrides) -> CitationRecord:
    defaults = dict(
        case_name="Kesavananda Bharati vs State of Kerala",
        neutral_citation=None,
        court="Supreme Court",
        status="unverified",
        ik_doc_id=None,
        ik_url=None,
        decided_on=None,
        stale=False,
        from_cache=True,
    )
    defaults.update(overrides)
    return CitationRecord(**defaults)


def test_unverified_citation_emits_no_hyperlink():
    result = render_citation(_record(status="unverified", ik_doc_id=None, ik_url=None))

    assert result.renderable is False
    assert result.url is None
    assert "<a href" not in result.html
    assert UNVERIFIED_LABEL in result.html


def test_unverified_citation_carries_the_exact_required_label():
    result = render_citation(_record(status="unverified"))

    assert result.label.endswith(UNVERIFIED_LABEL)
    assert "⚠ Unverified — confirm manually (may exist only on SCC/Manupatra)" in result.label


def test_verified_citation_with_doc_id_and_url_does_get_a_hyperlink():
    result = render_citation(
        _record(status="verified", ik_doc_id="12345", ik_url="https://indiankanoon.org/doc/12345/")
    )

    assert result.renderable is True
    assert result.url == "https://indiankanoon.org/doc/12345/"
    assert '<a href="https://indiankanoon.org/doc/12345/"' in result.html


def test_status_verified_but_missing_ik_doc_id_still_refuses_a_link():
    """Defensive: even a row that somehow has status='verified' but no
    ik_doc_id (shouldn't happen — the DB check constraint blocks it, but
    the renderer must not trust that alone) gets no hyperlink."""
    result = render_citation(_record(status="verified", ik_doc_id=None, ik_url=None))

    assert result.renderable is False
    assert "<a href" not in result.html


def test_status_verified_but_missing_url_still_refuses_a_link():
    result = render_citation(_record(status="verified", ik_doc_id="12345", ik_url=None))

    assert result.renderable is False
    assert "<a href" not in result.html


def test_stale_citation_is_downgraded_to_unverified_rendering():
    """A previously verified citation whose URL the nightly recheck found
    dead must render grey immediately — status alone isn't enough."""
    result = render_citation(
        _record(
            status="verified",
            ik_doc_id="12345",
            ik_url="https://indiankanoon.org/doc/12345/",
            stale=True,
        )
    )

    assert result.renderable is False
    assert "<a href" not in result.html
    assert UNVERIFIED_LABEL in result.html


def test_html_output_is_escaped_against_injection_via_case_name():
    malicious_name = '<script>alert(1)</script> vs State'
    result = render_citation(_record(case_name=malicious_name, status="unverified"))

    assert "<script>" not in result.html
    assert "&lt;script&gt;" in result.html


# --- lookup path: no citations row at all also refuses a link --------------


class _EmptyResponse:
    data: list = []


class _EmptyQuery:
    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def is_(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return _EmptyResponse()


class _EmptyTable:
    def select(self, *_a, **_k):
        return _EmptyQuery()


class _EmptyDb:
    def table(self, _name: str):
        return _EmptyTable()


def test_citation_with_no_row_at_all_refuses_a_link():
    result = render_citation_by_lookup("Some Never Verified Case vs Respondent", db=_EmptyDb())

    assert result.renderable is False
    assert "<a href" not in result.html
