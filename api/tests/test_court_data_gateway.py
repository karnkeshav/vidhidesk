"""Tests for app/services/court_data_gateway.py -- mocks httpx.request
directly (no live provider call, ever). Covers: auth header, timeout,
retry-then-succeed, rate-limit backoff, persistent-error translation
(never leaking raw response text), and response normalization for all
three confirmed endpoints, including the causelist_batch fallback-key
parsing (its exact top-level container key was not independently
confirmed -- see the module's own docstring)."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.services.court_data_gateway import (
    CourtDataGateway,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
    CourtDataNotFoundError,
    CourtDataQuotaExceededError,
)


def _settings(key: str = "eci_live_test123") -> Settings:
    return Settings(ecourts_api_key=key)


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict, headers: dict | None = None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = str(json_data)

    def json(self):
        return self._json

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400


def test_missing_api_key_raises_not_configured():
    gw = CourtDataGateway(settings=_settings(key=""))
    with pytest.raises(CourtDataNotConfiguredError):
        gw.case_lookup("DLND020047882015")


def test_case_lookup_sends_bearer_header(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse(200, {
            "data": {
                "courtCaseData": {
                    "cnr": "DLND020047882015",
                    "courtName": "Test Court",
                    "judges": ["J. Test"],
                    "caseStatus": "Pending",
                    "petitioners": ["A"],
                    "respondents": ["B"],
                }
            }
        })

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.case_lookup("DLND020047882015")

    assert captured["headers"]["Authorization"] == "Bearer eci_live_test123"
    assert captured["method"] == "GET"
    assert "/api/partner/case/DLND020047882015" in captured["url"]
    assert result.court_name == "Test Court"
    assert result.judge == "J. Test"
    assert result.petitioners == ["A"]


def test_bulk_refresh_rejects_over_50_cnrs():
    gw = CourtDataGateway(settings=_settings())
    with pytest.raises(CourtDataGatewayError):
        gw.bulk_refresh([f"CNR{i}" for i in range(51)])


def test_bulk_refresh_normalizes_response(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        assert method == "POST"
        assert kwargs["json"] == {"cnrs": ["CNR1", "CNR2"]}
        return _FakeResponse(200, {"data": {"refreshed": ["CNR1"], "queued": ["CNR2"], "invalid": []}, "meta": {"request_id": "req-123"}})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.bulk_refresh(["CNR1", "CNR2"])

    assert result.refreshed == ["CNR1"]
    assert result.queued == ["CNR2"]
    assert result.request_id == "req-123"


def test_causelist_batch_rejects_over_100_cnrs():
    gw = CourtDataGateway(settings=_settings())
    with pytest.raises(CourtDataGatewayError):
        gw.causelist_batch([f"CNR{i}" for i in range(101)])


def test_causelist_batch_parses_data_key(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {
            "data": [
                {"cnr": "CNR1", "hasCauselist": True, "nextListing": {"court": "Court Hall 4", "courtType": "District", "listType": "Regular", "listingFor": "Arguments", "bench": "Bench A", "courtNo": "4", "date": "2026-08-28", "caseNumber": "CS 1/2026", "party": "A vs B"}}
            ]
        })

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.causelist_batch(["CNR1"])

    assert "CNR1" in result
    entry = result["CNR1"]
    assert entry.has_causelist is True
    assert entry.court == "Court Hall 4"
    assert entry.bench == "Bench A"
    assert entry.court_no == "4"
    assert entry.date == "2026-08-28"


def test_causelist_batch_falls_back_to_results_key(monkeypatch):
    """Fallback-key parsing (module docstring: the exact container key for
    this endpoint was not independently confirmed) -- must not crash on
    the alternate plausible shape."""
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {"results": [{"cnr": "CNR1", "hasCauselist": False}]})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.causelist_batch(["CNR1"])
    assert result["CNR1"].has_causelist is False


def test_causelist_batch_unrecognized_shape_returns_empty_not_crash(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {"something_else": "unexpected"})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.causelist_batch(["CNR1"])
    assert result == {}


def test_timeout_retries_then_raises(monkeypatch):
    call_count = {"n": 0}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        call_count["n"] += 1
        raise httpx.TimeoutException("simulated timeout")

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr("time.sleep", lambda s: None)  # don't actually wait in tests
    gw = CourtDataGateway(settings=_settings())

    with pytest.raises(CourtDataGatewayError):
        gw.case_lookup("CNR1")
    assert call_count["n"] == 3  # initial + 2 retries, per _MAX_RETRIES=2


def test_transient_5xx_retries_then_succeeds(monkeypatch):
    responses = [
        _FakeResponse(503, {"error": "unavailable"}),
        _FakeResponse(200, {"cnr": "CNR1", "petitioners": [], "respondents": []}),
    ]

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr("time.sleep", lambda s: None)
    gw = CourtDataGateway(settings=_settings())
    result = gw.case_lookup("CNR1")
    assert result.cnr == "CNR1"


def test_rate_limit_honors_retry_after_then_succeeds(monkeypatch):
    responses = [
        _FakeResponse(429, {"error": "rate limited"}, headers={"Retry-After": "0"}),
        _FakeResponse(200, {"cnr": "CNR1", "petitioners": [], "respondents": []}),
    ]
    sleep_calls = []

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    gw = CourtDataGateway(settings=_settings())
    result = gw.case_lookup("CNR1")

    assert result.cnr == "CNR1"
    assert sleep_calls == [0.0]


def test_case_search_sends_filters_as_query_params(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _FakeResponse(200, {"data": [], "meta": {}})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    gw.case_search(advocates=["Sharma"], case_numbers=["CS 1/2026"], page=2, page_size=50)

    assert captured["method"] == "GET"
    assert "/api/partner/search" in captured["url"]
    assert captured["params"]["advocates"] == ["Sharma"]
    assert captured["params"]["caseNumbers"] == ["CS 1/2026"]
    assert captured["params"]["page"] == 2
    assert captured["params"]["pageSize"] == 50


def test_case_search_caps_page_size(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["params"] = kwargs.get("params")
        return _FakeResponse(200, {"data": []})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    gw.case_search(query="test", page_size=9999)
    assert captured["params"]["pageSize"] == 200


def test_case_search_normalizes_response(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {
            "data": [
                {
                    "cnr": "DLND020047882015",
                    "caseNumber": "CS 1/2026",
                    "courtName": "Delhi HC",
                    "caseType": "WP_C",
                    "status": "Pending",
                    "petitioners": ["A"],
                    "respondents": ["B"],
                    "advocates": ["Sharma"],
                }
            ],
            "hasNextPage": False,
            "meta": {"request_id": "req-search-1", "total": 1},
        })

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.case_search(advocates=["Sharma"])

    assert len(result.items) == 1
    item = result.items[0]
    assert item.cnr == "DLND020047882015"
    assert item.case_number == "CS 1/2026"
    assert item.advocates == ["Sharma"]
    assert result.has_next_page is False
    assert result.request_id == "req-search-1"
    assert result.total == 1


def test_case_search_unrecognized_shape_returns_empty_not_crash(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {"something_else": "unexpected"})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())
    result = gw.case_search(query="test")
    assert result.items == []


def test_404_raises_the_specific_not_found_subclass_never_leaking_raw_text(monkeypatch):
    """Found in production (2026-09-07): a plain CourtDataGatewayError for
    a 404 was indistinguishable from a real outage by every caller,
    surfacing "unable to reach the provider" for what was actually just a
    CNR typo. CourtDataNotFoundError is a CourtDataGatewayError subclass
    (so any pre-existing broad `except CourtDataGatewayError` still
    catches it), but callers that care can now tell the two apart."""
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(404, {"meta": {"request_id": "req-404"}, "secret_internal_detail": "should never surface"})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())

    with pytest.raises(CourtDataNotFoundError) as exc_info:
        gw.case_lookup("CNR1")
    assert isinstance(exc_info.value, CourtDataGatewayError)
    assert "secret_internal_detail" not in str(exc_info.value)
    assert "req-404" in str(exc_info.value)


def test_non_404_persistent_error_raises_base_class_not_not_found(monkeypatch):
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(403, {"meta": {"request_id": "req-403"}})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())

    with pytest.raises(CourtDataGatewayError) as exc_info:
        gw.case_lookup("CNR1")
    assert not isinstance(exc_info.value, CourtDataNotFoundError)


def test_402_raises_the_specific_quota_exceeded_subclass(monkeypatch):
    """Found in production (2026-09-07): a real sync for a known-good CNR
    got a fresh 402 from the provider right after a burst of testing
    calls -- consistent with quota exhaustion, not an outage or a bad
    CNR. Same reasoning as the 404 fix above: a plain CourtDataGatewayError
    gave every caller no way to tell "your account needs billing
    attention" apart from "the provider is briefly down"."""
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        return _FakeResponse(402, {"meta": {"request_id": "req-402"}})

    monkeypatch.setattr(httpx, "request", fake_request)
    gw = CourtDataGateway(settings=_settings())

    with pytest.raises(CourtDataQuotaExceededError) as exc_info:
        gw.case_lookup("CNR1")
    assert isinstance(exc_info.value, CourtDataGatewayError)
    assert "req-402" in str(exc_info.value)
