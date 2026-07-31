"""Renderer-side citation hard gate (CLAUDE.md Hard Rule 1).

    The renderer must refuse to display a live hyperlink for any case
    citation unless a verified Indian Kanoon doc_id exists in the
    citations table. Unverified citations render grey with the label
    "Unverified — confirm manually (may exist only on SCC/Manupatra)".
    No exceptions.

This is the single place that decision gets made. The frontend never
inspects a citations row itself and builds its own <a href> — it calls
POST /api/citations/render (see app/routers/citations.py) and renders
exactly what comes back. That's what "enforce in code, not in an LLM
prompt" means in practice: there is exactly one function capable of
producing a `renderable=True` result, and it requires a live row with
status='verified', a non-null ik_doc_id/ik_url, and not stale (a citation
whose URL the nightly recheck job found dead is downgraded to the grey
rendering immediately, without waiting for `status` to change).
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from app.db import service_client
from app.services.citations import CitationRecord

UNVERIFIED_LABEL = "⚠ Unverified — confirm manually (may exist only on SCC/Manupatra)"


@dataclass
class CitationRender:
    renderable: bool
    url: str | None
    label: str
    html: str  # pre-rendered, escaped snippet — never build markup from raw fields elsewhere


def render_citation(record: CitationRecord) -> CitationRender:
    is_verified_and_fresh = (
        record.status == "verified"
        and not record.stale
        and bool(record.ik_doc_id)
        and bool(record.ik_url)
    )
    if is_verified_and_fresh:
        label = record.case_name
        url = record.ik_url
        safe_label = html.escape(label)
        safe_url = html.escape(url, quote=True)
        return CitationRender(
            renderable=True,
            url=url,
            label=label,
            html=f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>',
        )

    label = f"{record.case_name} — {UNVERIFIED_LABEL}"
    safe_label = html.escape(label)
    return CitationRender(
        renderable=False,
        url=None,
        label=label,
        html=f'<span class="citation-unverified">{safe_label}</span>',
    )


def render_citation_by_lookup(
    case_name: str,
    neutral_citation: str | None = None,
    *,
    db=None,
) -> CitationRender:
    """Read-only: renders whatever is currently cached, never calls the IK
    API. A citation with no row at all — never verified, never even
    attempted — renders unverified, same as an explicit unverified row.
    """
    db = db if db is not None else service_client()

    case_name_normalized = case_name.strip().lower()
    query = db.table("citations").select("*").eq("case_name_normalized", case_name_normalized)
    query = (
        query.eq("neutral_citation", neutral_citation)
        if neutral_citation
        else query.is_("neutral_citation", "null")
    )
    resp = query.limit(1).execute()

    if not resp.data:
        return render_citation(
            CitationRecord(
                case_name=case_name,
                neutral_citation=neutral_citation,
                court=None,
                status="unverified",
                ik_doc_id=None,
                ik_url=None,
                decided_on=None,
                stale=False,
                from_cache=False,
            )
        )

    row = resp.data[0]
    return render_citation(
        CitationRecord(
            case_name=row["case_name"],
            neutral_citation=row.get("neutral_citation"),
            court=row.get("court"),
            status=row["status"],
            ik_doc_id=row.get("ik_doc_id"),
            ik_url=row.get("ik_url"),
            decided_on=row.get("decided_on"),
            stale=bool(row.get("stale", False)),
            from_cache=True,
        )
    )
