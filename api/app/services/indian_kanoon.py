"""Thin client for the Indian Kanoon API.

CLAUDE.md is explicit that this is a spike: "verify live behaviour in
Sprint 0 before relying on this." The endpoint shapes below follow the
publicly documented Indian Kanoon API (https://api.indiankanoon.org) —
notably that /search/, /doc/{id}/, and /docfragment/{id}/ are all POST
requests taking their parameters as query-string args, not a JSON body.
Confirm this against a real token via scripts/ik_spike.py before trusting
it in the Citation Verifier.
"""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("vidhidesk.indian_kanoon")

BASE_URL = "https://api.indiankanoon.org"


class IndianKanoonError(Exception):
    pass


class IndianKanoonClient:
    def __init__(self, settings: Settings | None = None, timeout: float = 30.0):
        self._settings = settings or get_settings()
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self._settings.indian_kanoon_api_token:
            raise IndianKanoonError(
                "INDIAN_KANOON_API_TOKEN is not set — cannot call the Indian Kanoon API"
            )
        return {"Authorization": f"Token {self._settings.indian_kanoon_api_token}"}

    def search(self, query: str, court: str | None = None, max_pages: int = 1) -> dict:
        """Search Indian Kanoon. Returns the raw response for page 0, plus
        `pages_fetched` and the concatenated `docs` across up to `max_pages`.

        `court` is appended to the query using IK's own query syntax (e.g.
        "doctypes: supremecourt") — confirm the exact filter tokens IK
        expects during the spike run; this is a best-effort default.
        """
        form_input = query if not court else f"{query} doctypes: {court}"
        all_docs: list[dict] = []
        pages_fetched = 0
        first_page_raw: dict = {}

        for pagenum in range(max_pages):
            resp = httpx.post(
                f"{BASE_URL}/search/",
                headers=self._headers(),
                params={"formInput": form_input, "pagenum": pagenum},
                timeout=self._timeout,
            )
            self._raise_for_status(resp)
            data = resp.json()
            if pagenum == 0:
                first_page_raw = data
            docs = data.get("docs", [])
            all_docs.extend(docs)
            pages_fetched += 1
            logger.info(
                "indian_kanoon.search query=%r court=%r pagenum=%d results=%d",
                query, court, pagenum, len(docs),
            )
            if not docs:
                break

        return {
            **first_page_raw,
            "docs": all_docs,
            "pages_fetched": pages_fetched,
        }

    def get_doc(self, doc_id: str, maxcites: int = 0, maxcitedby: int = 0) -> dict:
        resp = httpx.post(
            f"{BASE_URL}/doc/{doc_id}/",
            headers=self._headers(),
            params={"maxcites": maxcites, "maxcitedby": maxcitedby},
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        logger.info("indian_kanoon.get_doc doc_id=%s", doc_id)
        return resp.json()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.is_error:
            raise IndianKanoonError(
                f"Indian Kanoon API error {resp.status_code}: {resp.text[:500]}"
            )


def doc_url(doc_id: str) -> str:
    return f"https://indiankanoon.org/doc/{doc_id}/"
