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
  GET  /api/partner/case/{cnr}           -- full case detail by CNR; response
                                             shape confirmed 2026-09-06 against
                                             a real CNR (see case_lookup()) --
                                             case fields are nested under
                                             data["data"]["courtCaseData"],
                                             not top-level as originally
                                             assumed from the blog posts
  POST /api/partner/case/bulk-refresh    -- up to 50 CNRs, queues a re-scrape;
                                             wait 30+s before re-fetching case
                                             detail; safe to call repeatedly
                                             within 15s (provider-side dedup)
  POST /api/partner/causelist/cnr/batch  -- 1-100 CNRs, tells whether each is
                                             listed and where/when/what
  GET  /api/partner/search               -- search by advocate name, case
                                             number, party name, court, case
                                             type, etc. (added 4 Sep 2026 --
                                             see case_search() docstring for
                                             this endpoint's own, separate
                                             verification caveat)

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
_MAX_SEARCH_PAGE_SIZE = 200  # provider docs: "max 200 for partners"


class CourtDataGatewayError(Exception):
    """Raised for any provider call that could not be completed. Callers
    (court_sync.py) must never expose str(exc) verbatim to the frontend --
    it may echo response text; translate to a generic sync_status/
    last_error message instead."""


class CourtDataNotConfiguredError(CourtDataGatewayError):
    """ECOURTS_API_KEY is not set."""


class CourtDataNotFoundError(CourtDataGatewayError):
    """The provider returned 404 for a given CNR -- the CNR doesn't exist
    (typo, wrong court code, or a case eCourts simply doesn't have on
    record), NOT a connectivity/outage problem. Found in production
    (2026-09-07): a real user's genuine CNR typo surfaced as "Unable to
    reach the eCourts provider right now" -- true for a 5xx/timeout, but
    actively misleading for a 404, which every caller was previously
    treating identically to a real outage."""


@dataclass
class InterlocutoryApplicationEntry:
    """One entry from courtCaseData.interlocutoryApplications -- confirmed
    against a real response (CNR DLHC010163362026, see
    scripts/ecourts_spike.py output, 2026-09-07): {regNo, remark, filedBy,
    filingDate, status}. `remark` is NOT surfaced here -- in the one
    confirmed sample its value was itself a date string ("20-04-2026"),
    not a description, so its actual meaning is unverified; callers must
    not guess it means "relief sought" or anything else."""

    application_number: str
    filed_by: str
    filing_date: str
    status_raw: str
    raw: dict[str, Any]


@dataclass
class CourtCaseDetail:
    cnr: str
    court_name: str | None
    judge: str | None
    judges: list[str]
    status: str | None
    petitioners: list[str]
    respondents: list[str]
    # Confirmed against the same real response as judges/petitioners/
    # respondents above (petitionerAdvocates/respondentAdvocates,
    # 2026-09-07) -- plain advocate name strings, no bar_council_id/
    # phone/email in this response.
    petitioner_advocates: list[str]
    respondent_advocates: list[str]
    interlocutory_applications: list[InterlocutoryApplicationEntry]
    # courtCaseData.nextHearingDate -- confirmed against the same real
    # response as the fields above (2026-09-07). This is the case's own
    # scheduled next hearing, distinct from causelist_batch's "next
    # listing" (CauselistEntry.date, which is what's on an imminent
    # causelist specifically); court_sync.py uses causelist's date when
    # present and falls back to this one otherwise.
    next_hearing_date: str | None
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


@dataclass
class CaseSearchItem:
    cnr: str | None
    case_number: str | None
    court_name: str | None
    case_type: str | None
    status: str | None
    petitioners: list[str]
    respondents: list[str]
    advocates: list[str]
    raw: dict[str, Any]


@dataclass
class CaseSearchResult:
    items: list[CaseSearchItem]
    total: int | None
    has_next_page: bool | None
    request_id: str | None
    raw: dict[str, Any]


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
                    if resp.status_code == 404:
                        raise CourtDataNotFoundError(f"eCourts API returned 404 (request_id={request_id})")
                    raise CourtDataGatewayError(f"eCourts API returned {resp.status_code} (request_id={request_id})")
                return resp
            if attempt < _MAX_RETRIES:
                time.sleep(backoff)
        raise CourtDataGatewayError(f"eCourts API unreachable after {_MAX_RETRIES + 1} attempts") from last_exc

    def case_lookup(self, cnr: str) -> CourtCaseDetail:
        resp = self._request("GET", f"/api/partner/case/{cnr}")
        data = resp.json()
        # Confirmed against a real, live response (2026-09-06, real CNR
        # DLHC010163362026, a genuine pending Delhi HC bail application) --
        # the blog-post-derived flat shape this module's docstring warned
        # was unverified was wrong: case fields are nested under
        # data["data"]["courtCaseData"], "judge" is actually a "judges"
        # list, and "status" is actually "caseStatus". This was invisible
        # until GET /api/court-lookup-preview (the first caller to read
        # these typed fields rather than storing case_detail.raw wholesale)
        # went live and returned an all-null preview for a case with real,
        # rich data on record.
        case_data = (data.get("data") or {}).get("courtCaseData") or {}
        judges = case_data.get("judges") or []

        ia_entries: list[InterlocutoryApplicationEntry] = []
        for item in case_data.get("interlocutoryApplications") or []:
            if not isinstance(item, dict):
                continue
            reg_no = item.get("regNo")
            filed_by = item.get("filedBy")
            filing_date = item.get("filingDate")
            status = item.get("status")
            # All four required by the DB (interlocutory_applications has
            # NOT NULL application_number/filed_by/filing_date/
            # current_status) -- an entry missing any of them is dropped
            # rather than written with a fabricated placeholder.
            if not (reg_no and filed_by and filing_date and status):
                logger.warning("court_data_gateway case_lookup: dropping incomplete interlocutoryApplications entry for cnr=%s", cnr)
                continue
            ia_entries.append(
                InterlocutoryApplicationEntry(
                    application_number=str(reg_no).strip(),
                    filed_by=str(filed_by).strip(),
                    filing_date=str(filing_date),
                    status_raw=str(status),
                    raw=item,
                )
            )

        return CourtCaseDetail(
            cnr=case_data.get("cnr", cnr),
            court_name=case_data.get("courtName"),
            judge=", ".join(judges) if judges else None,
            judges=list(judges),
            status=case_data.get("caseStatus"),
            petitioners=list(case_data.get("petitioners") or []),
            respondents=list(case_data.get("respondents") or []),
            petitioner_advocates=list(case_data.get("petitionerAdvocates") or []),
            respondent_advocates=list(case_data.get("respondentAdvocates") or []),
            interlocutory_applications=ia_entries,
            next_hearing_date=case_data.get("nextHearingDate"),
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

    def case_search(
        self,
        *,
        query: str | None = None,
        advocates: list[str] | None = None,
        judges: list[str] | None = None,
        petitioners: list[str] | None = None,
        respondents: list[str] | None = None,
        case_numbers: list[str] | None = None,
        court_codes: list[str] | None = None,
        case_types: list[str] | None = None,
        case_statuses: list[str] | None = None,
        filing_years: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> CaseSearchResult:
        """GET /api/partner/search -- find a case (and its CNR) by advocate
        name, case number, party name, court, or case type, when the CNR
        itself isn't already known. This is a lookup helper only: it never
        persists anything, unlike case_lookup/bulk_refresh/causelist_batch.

        Unlike the three endpoints above, this one was NOT reconstructed
        from ecourtsindia.com's public blog excerpts within this codebase's
        own prior verification pass -- ecourtsindia.com/api/docs still
        403s to automated fetches (see module docstring), and a live
        authenticated test call was blocked by this session's own tooling
        permissions before this method was written. Parameter names
        (advocates, judges, petitioners, respondents, caseNumbers,
        courtCodes, caseTypes, caseStatuses, filingYears, page, pageSize)
        come from two independent eCourtsIndia developer-blog posts dated
        16 Apr 2026 and 18 May 2026 that agree on these names, but neither
        is the provider's own reference doc. RE-VERIFY against a live
        response before trusting this: a wrong param name fails silently
        as zero matches, not as an error, which this client cannot detect
        on its own -- see GET /api/partner/search/capabilities (documented
        as free) for the provider's own authoritative field catalog.
        """
        page_size = min(page_size, _MAX_SEARCH_PAGE_SIZE)
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if query:
            params["query"] = query
        if advocates:
            params["advocates"] = advocates
        if judges:
            params["judges"] = judges
        if petitioners:
            params["petitioners"] = petitioners
        if respondents:
            params["respondents"] = respondents
        if case_numbers:
            params["caseNumbers"] = case_numbers
        if court_codes:
            params["courtCodes"] = court_codes
        if case_types:
            params["caseTypes"] = case_types
        if case_statuses:
            params["caseStatuses"] = case_statuses
        if filing_years:
            params["filingYears"] = filing_years

        resp = self._request("GET", "/api/partner/search", params=params)
        body = resp.json()
        items_raw = body.get("data") or body.get("results") or body.get("items") or []
        if not isinstance(items_raw, list):
            logger.warning("court_data_gateway case_search: unrecognized response shape, no items parsed")
            items_raw = []

        items: list[CaseSearchItem] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            items.append(
                CaseSearchItem(
                    cnr=item.get("cnr"),
                    case_number=item.get("caseNumber") or item.get("case_number"),
                    court_name=item.get("courtName") or item.get("court_name"),
                    case_type=item.get("caseType") or item.get("case_type"),
                    status=item.get("status"),
                    petitioners=list(item.get("petitioners") or []),
                    respondents=list(item.get("respondents") or []),
                    advocates=list(item.get("advocates") or []),
                    raw=item,
                )
            )

        meta = body.get("meta") or {}
        return CaseSearchResult(
            items=items,
            total=body.get("total") if isinstance(body.get("total"), int) else meta.get("total"),
            has_next_page=body.get("hasNextPage"),
            request_id=meta.get("request_id"),
            raw=body,
        )
