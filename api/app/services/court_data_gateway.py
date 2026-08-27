"""Court Data Gateway -- thin, centralized client for the eCourtsIndia
partner API (Litigation Intelligence + eCourts, 27 Aug 2026).

Direct fetch of https://ecourtsindia.com/api/docs returned HTTP 403
(bot-blocked) during this session -- the three endpoints and shapes below
were confirmed via ecourtsindia.com's own public blog posts and
search-indexed documentation excerpts, retrieved 27 Aug 2026, NOT
invented. Field names not explicitly confirmed in those excerpts are
read defensively (see causelist_batch's fallback key lookup below) and
this client degrades to an empty/partial result rather than crashing or
guessing when a response doesn't match what was documented. RE-VERIFY
every shape here against a live response with a real key before treating
any field as guaranteed present -- see scripts/ecourts_spike.py.

Confirmed base URL and auth: https://webapi.ecourtsindia.com,
`Authorization: Bearer <ECOURTS_API_KEY>` (key format `eci_live_...`).
Every response carries `meta.request_id` on both success and error.

Confirmed endpoints used here:
  GET  /api/partner/case/{cnr}           -- full case detail by CNR
  POST /api/partner/case/bulk-refresh    -- up to 50 CNRs, queues a re-scrape;
                                             wait 30+s before re-fetching case
                                             detail; safe to call repeatedly
                                             within 15s (provider-side dedup)
  POST /api/partner/causelist/cnr/batch  -- 1-100 CNRs, tells whether each is
                                             listed and where/when/what

NEVER call this from the frontend -- only app/routers/court_tracking.py
and app/services/court_sync.py reach for this class. ECOURTS_API_KEY is
read from Settings only, never logged, never returned in any response
this module produces.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("vidhidesk.court_data_gateway")

BASE_URL = "https://webapi.ecourtsindia.com"
_DEFAULT_TIMEOUT_S = 20.0
_MAX_RETRIES = 2
_RETRY_BACKOFF_S = [1.0, 3.0]

_MAX_BULK_REFRESH_CNRS = 50
_MAX_CAUSELIST_CNRS = 100


class CourtDataGatewayError(Exception):
    """Raised for any provider call that could not be completed. Callers
    (court_sync.py) must never expose str(exc) verbatim to the frontend --
    it may echo response text; translate to a generic sync_status/
    last_error message instead."""


class CourtDataNotConfiguredError(CourtDataGatewayError):
    """ECOURTS_API_KEY is not set."""


@dataclass
class CourtCaseDetail:
    cnr: str
    court_name: str | None
    judge: str | None
    status: str | None
    petitioners: list[str]
    respondents: list[str]
    raw: dict[str, Any]


@dataclass
class CauselistEntry:
    cnr: str
    has_causelist: bool
    court: str | None
    court_type: str | None
    list_type: str | None
    listing_for: str | None
    bench: str | None
    court_no: str | None
    date: str | None
    raw: dict[str, Any]


@dataclass
class BulkRefreshResult:
    refreshed: list[str]
    queued: list[str]
    invalid: list[str]
    request_id: str | None


class CourtDataGateway:
    """Centralizes every eCourtsIndia call: auth header, timeout, retry
    on transient failure (network error, 5xx, 429 with backoff),
    response normalization into the dataclasses above. A malformed or
    unexpectedly-shaped provider response degrades to an empty/partial
    result (logged) rather than raising -- only a genuine transport/auth/
    persistent-error failure raises CourtDataGatewayError."""

    def __init__(self, settings: Settings | None = None, timeout: float = _DEFAULT_TIMEOUT_S):
        self._settings = settings or get_settings()
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self._settings.ecourts_api_key:
            raise CourtDataNotConfiguredError("ECOURTS_API_KEY is not set -- cannot call the eCourts API")
        return {"Authorization": f"Bearer {self._settings.ecourts_api_key}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = self._headers()
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            backoff = _RETRY_BACKOFF_S[min(attempt, len(_RETRY_BACKOFF_S) - 1)]
            try:
                resp = httpx.request(method, f"{BASE_URL}{path}", headers=headers, timeout=self._timeout, **kwargs)
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("court_data_gateway timeout method=%s path=%s attempt=%d", method, path, attempt)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("court_data_gateway network error method=%s path=%s attempt=%d: %s", method, path, attempt, exc)
            else:
                if resp.status_code == 429 and attempt < _MAX_RETRIES:
                    retry_after = float(resp.headers.get("Retry-After", backoff))
                    logger.warning("court_data_gateway rate-limited path=%s retry_after=%.1fs", path, retry_after)
                    time.sleep(retry_after)
                    continue
                if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                    time.sleep(backoff)
                    continue
                if resp.is_error:
                    request_id = None
                    try:
                        request_id = resp.json().get("meta", {}).get("request_id")
                    except Exception:
                        pass
                    logger.warning(
                        "court_data_gateway provider error status=%d path=%s request_id=%s",
                        resp.status_code, path, request_id,
                    )
                    raise CourtDataGatewayError(f"eCourts API returned {resp.status_code} (request_id={request_id})")
                return resp
            if attempt < _MAX_RETRIES:
                time.sleep(backoff)
        raise CourtDataGatewayError(f"eCourts API unreachable after {_MAX_RETRIES + 1} attempts") from last_exc

    def case_lookup(self, cnr: str) -> CourtCaseDetail:
        resp = self._request("GET", f"/api/partner/case/{cnr}")
        data = resp.json()
        return CourtCaseDetail(
            cnr=data.get("cnr", cnr),
            court_name=data.get("courtName"),
            judge=data.get("judge"),
            status=data.get("status"),
            petitioners=list(data.get("petitioners") or []),
            respondents=list(data.get("respondents") or []),
            raw=data,
        )

    def bulk_refresh(self, cnrs: list[str]) -> BulkRefreshResult:
        if not cnrs:
            return BulkRefreshResult(refreshed=[], queued=[], invalid=[], request_id=None)
        if len(cnrs) > _MAX_BULK_REFRESH_CNRS:
            raise CourtDataGatewayError(f"bulk_refresh supports at most {_MAX_BULK_REFRESH_CNRS} CNRs per call")
        resp = self._request("POST", "/api/partner/case/bulk-refresh", json={"cnrs": cnrs})
        body = resp.json()
        data = body.get("data", {}) or {}
        return BulkRefreshResult(
            refreshed=list(data.get("refreshed") or []),
            queued=list(data.get("queued") or []),
            invalid=list(data.get("invalid") or []),
            request_id=(body.get("meta") or {}).get("request_id"),
        )

    def causelist_batch(self, cnrs: list[str]) -> dict[str, CauselistEntry]:
        if not cnrs:
            return {}
        if len(cnrs) > _MAX_CAUSELIST_CNRS:
            raise CourtDataGatewayError(f"causelist_batch supports at most {_MAX_CAUSELIST_CNRS} CNRs per call")
        resp = self._request("POST", "/api/partner/causelist/cnr/batch", json={"cnrs": cnrs})
        body = resp.json()
        # Top-level array key not independently confirmed -- documented
        # excerpts describe the per-item fields but not this container's
        # exact name. Tries both plausible keys; an unrecognized shape
        # yields an empty result (logged), never a guess.
        items = body.get("data") or body.get("results") or []
        if not isinstance(items, list):
            logger.warning("court_data_gateway causelist_batch: unrecognized response shape, no items parsed")
            return {}

        results: dict[str, CauselistEntry] = {}
        for item in items:
            cnr = item.get("cnr")
            if not cnr:
                continue
            next_listing = item.get("nextListing") or {}
            results[cnr] = CauselistEntry(
                cnr=cnr,
                has_causelist=bool(item.get("hasCauselist")),
                court=next_listing.get("court"),
                court_type=next_listing.get("courtType"),
                list_type=next_listing.get("listType"),
                listing_for=next_listing.get("listingFor"),
                bench=next_listing.get("bench"),
                court_no=next_listing.get("courtNo"),
                date=next_listing.get("date"),
                raw=item,
            )
        return results
