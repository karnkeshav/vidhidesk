"""Court sync orchestration (Litigation Intelligence + eCourts, 27 Aug
2026). Wires app/services/court_data_gateway.py's provider calls into
court_case_tracking / hearings / court_sync_log. Runs with
service_client() (bypasses RLS) since it is invoked from
scripts/court_sync_scheduler.py (no authenticated request context, see
that script's own docstring) -- every write below sets organization_id/
matter_id explicitly rather than relying on RLS to scope it, and the
organization access check below is this module's OWN enforcement of
tenant isolation and the "expired orgs don't consume eCourts usage"
policy, not a substitute for RLS on the authenticated read paths (which
still apply normally to every other router).

Strict matching (spec Section 7): every sync is keyed by CNR via
court_case_tracking.matter_id -> cnr_number -- never by party name.
Manual override protection: a hearing whose source='manual_override' is
never touched by sync -- checked before every write, not just documented.
Idempotency: hearings are upserted by (matter_id, hearing date), never
blindly inserted -- a repeat sync on the same day updates the same row.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.court_data_gateway import (
    CourtDataGateway,
    CourtDataGatewayError,
    CourtDataNotConfiguredError,
    CourtDataNotFoundError,
    CourtDataQuotaExceededError,
)
from app.services.notifications import notify_hearing_listed

logger = logging.getLogger("vidhidesk.court_sync")

_PAUSED_STATUSES = frozenset({"suspended", "expired"})


class CourtSyncSkipped(Exception):
    """Not an error -- tracking disabled, no CNR, or org access paused.
    Distinguished from a real provider/sync failure so the caller (the
    scheduler script) can log/count these differently from actual errors."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(sc, *, organization_id: str, matter_id: str, cnr: str | None, operation: str, status: str, request_id: str | None = None, error_message: str | None = None) -> None:
    try:
        sc.table("court_sync_log").insert(
            {
                "organization_id": organization_id,
                "matter_id": matter_id,
                "cnr_number": cnr,
                "operation": operation,
                "status": status,
                "provider_request_id": request_id,
                "error_message": error_message,
            }
        ).execute()
    except Exception:
        logger.warning("court_sync: failed to write court_sync_log for matter_id=%s", matter_id, exc_info=True)


def _upsert_hearing_from_causelist(sc, *, matter: dict[str, Any], entry) -> tuple[dict[str, Any] | None, bool]:
    """Returns (hearing_row, was_created). Returns (None, False) if the
    only matching hearing is protected by manual_override -- the caller
    must not treat that as a failure, just as "left alone on purpose"."""
    if not entry.date:
        return None, False

    existing = sc.table("hearings").select("*").eq("matter_id", matter["id"]).execute().data or []
    match = next((h for h in existing if str(h.get("hearing_at", "")).startswith(entry.date)), None)

    if match and match.get("source") == "manual_override":
        logger.info("court_sync: hearing %s is manual_override, sync skipped for this hearing", match["id"])
        return None, False

    payload = {
        "matter_id": matter["id"],
        "organization_id": matter["organization_id"],
        "court": entry.court,
        "bench": entry.bench,
        "item_no": entry.court_no,
        "listing_details": entry.raw,
        "source": "ecourts",
        "source_synced_at": _now_iso(),
    }

    if match:
        updated = sc.table("hearings").update(payload).eq("id", match["id"]).execute().data
        return (updated[0] if updated else None), False

    payload.update(
        {
            "user_id": matter["user_id"],
            "hearing_at": f"{entry.date}T00:00:00+00:00",
            "title": f"Hearing — {matter.get('title', 'Matter')}",
            "case_no": matter.get("case_number_formatted"),
        }
    )
    inserted = sc.table("hearings").insert(payload).execute().data
    return (inserted[0] if inserted else None), True


def _upsert_causelist_row(sc, *, matter: dict[str, Any], cnr: str, entry, judges: list[str]) -> None:
    """Upserts one row into court_hearings_causelist, keyed by the table's
    own (matter_id, hearing_date) unique constraint. Deliberately writes
    ONLY fields CourtDataGateway has already verified against a real
    provider response: court/bench/list_type/date come from CauselistEntry
    (verified 2026-08-28), judges comes from this same sync's case_lookup
    call (verified 2026-09-06, see CourtDataGateway.case_lookup). It never
    writes court_advocates/case_advocate_links/interlocutory_applications
    -- those tables' provider field shapes are unverified (see
    scripts/ecourts_spike.py); guessing them was the cause of the earlier
    case_lookup envelope bug and is not repeated here."""
    if not entry.date:
        return

    existing = (
        sc.table("court_hearings_causelist")
        .select("*")
        .eq("matter_id", matter["id"])
        .eq("hearing_date", entry.date)
        .execute()
        .data
        or []
    )

    payload = {
        "organization_id": matter["organization_id"],
        "matter_id": matter["id"],
        "cnr_number": cnr,
        "hearing_date": entry.date,
        "bench_number": entry.bench,
        "judge_names": judges or None,
        "court_location": entry.court,
        "causelist_type": entry.list_type,
        "fetched_at": _now_iso(),
    }

    if existing:
        sc.table("court_hearings_causelist").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        sc.table("court_hearings_causelist").insert(payload).execute()


_IA_STATUS_MAP = {
    "PENDING": "PENDING",
    "GRANTED": "GRANTED",
    "ALLOWED": "GRANTED",
    "REJECTED": "REJECTED",
    "DISMISSED": "REJECTED",
    "WITHDRAWN": "WITHDRAWN",
}


def _normalize_ia_status(status_raw: str) -> str:
    """Only 'Pending' has been seen in a real response (see
    scripts/ecourts_spike.py output, 2026-09-07); the others are the
    plainest-possible guesses at what a resolved IA's status text might
    read, kept deliberately narrow. An unrecognized value defaults to
    PENDING (never crashes the whole sync over one status string) and is
    logged so a real example can correct this mapping later."""
    normalized = _IA_STATUS_MAP.get(status_raw.strip().upper())
    if normalized is None:
        logger.warning("court_sync: unrecognized interlocutory_applications status %r, defaulting to PENDING", status_raw)
        return "PENDING"
    return normalized


def _upsert_case_advocates(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Finds-or-creates a court_advocates row per unique name (global
    directory, see 0026's migration note), then upserts the matter-scoped
    case_advocate_links row -- built from petitioner_advocates/
    respondent_advocates, confirmed against a real response (see
    CourtDataGateway.case_lookup's own comment)."""
    today = _now_iso()[:10]
    pairs = [(name, "PETITIONER_COUNSEL") for name in case_detail.petitioner_advocates]
    pairs += [(name, "RESPONDENT_COUNSEL") for name in case_detail.respondent_advocates]

    for raw_name, role in pairs:
        name = raw_name.strip()
        if not name:
            continue

        existing_advocates = sc.table("court_advocates").select("*").eq("name", name).execute().data or []
        if existing_advocates:
            advocate = existing_advocates[0]
            advocate_id = advocate["id"]
            sc.table("court_advocates").update(
                {"case_count": advocate.get("case_count", 1) + 1, "last_seen_date": today}
            ).eq("id", advocate_id).execute()
        else:
            inserted = (
                sc.table("court_advocates")
                .insert({"name": name, "case_count": 1, "first_seen_in_case": today, "last_seen_date": today})
                .execute()
                .data
            )
            advocate_id = inserted[0]["id"] if inserted else None
        if not advocate_id:
            continue

        existing_links = (
            sc.table("case_advocate_links")
            .select("*")
            .eq("advocate_id", advocate_id)
            .eq("matter_id", matter["id"])
            .execute()
            .data
            or []
        )
        if existing_links:
            sc.table("case_advocate_links").update(
                {"cnr_number": cnr, "role": role, "last_appeared": today}
            ).eq("id", existing_links[0]["id"]).execute()
        else:
            sc.table("case_advocate_links").insert(
                {
                    "organization_id": matter["organization_id"],
                    "advocate_id": advocate_id,
                    "matter_id": matter["id"],
                    "cnr_number": cnr,
                    "role": role,
                    "first_appeared": today,
                    "last_appeared": today,
                }
            ).execute()


def _upsert_interlocutory_applications(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Upserts interlocutory_applications rows keyed by the table's own
    (matter_id, application_number) unique constraint, from entries
    CourtDataGateway.case_lookup already confirmed and validated (see
    InterlocutoryApplicationEntry). Deliberately leaves relief_sought/
    last_update_date null -- see that dataclass's own comment on why
    'remark' isn't mapped to either."""
    for entry in case_detail.interlocutory_applications:
        existing = (
            sc.table("interlocutory_applications")
            .select("*")
            .eq("matter_id", matter["id"])
            .eq("application_number", entry.application_number)
            .execute()
            .data
            or []
        )
        payload = {
            "cnr_number": cnr,
            "filed_by": entry.filed_by,
            "filing_date": entry.filing_date,
            "current_status": _normalize_ia_status(entry.status_raw),
        }
        if existing:
            sc.table("interlocutory_applications").update(payload).eq("id", existing[0]["id"]).execute()
        else:
            sc.table("interlocutory_applications").insert(
                {
                    "organization_id": matter["organization_id"],
                    "matter_id": matter["id"],
                    "application_number": entry.application_number,
                    **payload,
                }
            ).execute()


_ABSOLUTE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_ECOURTS_STORAGE_BUCKET = "ecourts-documents"


def _cache_ecourts_file(
    sc,
    *,
    organization_id: str,
    matter_id: str,
    cnr: str,
    url: str,
    gateway: CourtDataGateway | None = None,
) -> str | None:
    """Downloads an eCourts-hosted file once and caches it in Supabase
    Storage, so that repeat views (and repeat test/dev syncs against the
    same CNR) never re-hit the live provider for a file already fetched.

    Handles:
      1. Absolute URLs (scheme http/https) -- fetched directly via HTTP GET.
      2. Bare order filenames returned by eCourts (e.g. "order-1.pdf", CNR
         DLHC010163362026) -- fetched via the confirmed partner API endpoint
         GET /api/partner/case/{cnr}/order/{filename} with Bearer auth.

    Best-effort throughout: any failure (network, storage) logs and
    returns None rather than raising -- callers must keep the original
    value in that case, never lose the reference entirely."""
    if not url:
        return None

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit("/", 1)[-1].split("?")[0]) or "file"
    dir_path = f"{organization_id}/{matter_id}/{cnr}"
    storage_path = f"{dir_path}/{safe_name}"

    try:
        existing = sc.storage.from_(_ECOURTS_STORAGE_BUCKET).list(dir_path)
        for entry in existing or []:
            name = entry.get("name") if isinstance(entry, dict) else getattr(entry, "name", None)
            if name == safe_name:
                # Already cached from a previous sync -- reuse it rather
                # than re-downloading from eCourts or re-uploading.
                return sc.storage.from_(_ECOURTS_STORAGE_BUCKET).get_public_url(storage_path)
    except Exception as exc:
        logger.warning("court_sync: could not list cached eCourts files at %s: %s", dir_path, exc)
        # Fall through and attempt a fresh download/upload below.

    content: bytes | None = None
    content_type = "application/pdf"

    if _ABSOLUTE_URL_RE.match(url):
        try:
            resp = httpx.get(url, timeout=20.0, follow_redirects=True)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("content-type", "application/octet-stream")
        except Exception as exc:
            logger.warning("court_sync: failed to download eCourts file url=%s cnr=%s: %s", url, cnr, exc)
            return None
    else:
        gw = gateway or CourtDataGateway()
        try:
            content = gw.download_order(cnr, safe_name)
        except Exception as exc:
            logger.warning("court_sync: failed to download eCourts order bare file=%s cnr=%s: %s", url, cnr, exc)
            return None

    if not content:
        return None

    try:
        sc.storage.from_(_ECOURTS_STORAGE_BUCKET).upload(
            path=storage_path, file=content, file_options={"content-type": content_type}
        )
        return sc.storage.from_(_ECOURTS_STORAGE_BUCKET).get_public_url(storage_path)
    except Exception as exc:
        logger.warning("court_sync: failed to cache eCourts file to storage path=%s: %s", storage_path, exc)
        return None


def _cache_ecourts_files_for_case(
    sc,
    *,
    organization_id: str,
    matter_id: str,
    cnr: str,
    case_detail,
    gateway: CourtDataGateway | None = None,
) -> None:
    """Mutates case_detail.interim_orders/filed_documents IN PLACE,
    replacing any file reference (absolute URL or eCourts partner order
    filename) with its cached Supabase Storage URL. Called once per sync,
    before any persistence, so both the court_case_tracking columns and
    the `orders` table (_upsert_ecourts_orders, below) end up pointing
    at the cached copy."""
    for order in case_detail.interim_orders:
        url = order.get("order_url") or order.get("orderUrl")
        cached = _cache_ecourts_file(
            sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, url=url, gateway=gateway
        )
        if cached:
            order["order_url"] = cached

    for doc in case_detail.filed_documents:
        if not isinstance(doc, dict):
            continue
        for key, value in list(doc.items()):
            if isinstance(value, str) and _ABSOLUTE_URL_RE.match(value):
                cached = _cache_ecourts_file(
                    sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, url=value, gateway=gateway
                )
                if cached:
                    doc[key] = cached


def _upsert_ecourts_orders(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Upserts eCourts interim orders into the `orders` table (migration 0025).
    Keyed by (matter_id, file_url) or (matter_id, order_date, source='ecourts'),
    avoiding duplicating orders across repeated syncs."""
    for order in case_detail.interim_orders:
        order_url = order.get("order_url") or order.get("orderUrl")
        order_date = order.get("order_date") or order.get("orderDate")
        description = order.get("description") or "eCourts Interim Order"
        if not order_url and not order_date:
            continue

        existing_orders = (
            sc.table("orders")
            .select("*")
            .eq("matter_id", matter["id"])
            .execute()
            .data
            or []
        )
        match = next(
            (
                o
                for o in existing_orders
                if (order_url and o.get("file_url") == order_url)
                or (order_date and o.get("order_date") == order_date and o.get("source") == "ecourts")
            ),
            None,
        )
        payload = {
            "organization_id": matter["organization_id"],
            "matter_id": matter["id"],
            "order_date": order_date,
            "court": case_detail.court_name,
            "raw_text": description,
            "file_url": order_url,
            "source": "ecourts",
            "status": "active",
        }
        if match:
            sc.table("orders").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("orders").insert(payload).execute()


def _upsert_litigation_parties(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Synchronizes eCourts petitioners and respondents into the matter's
    litigation_parties table (migration 0013) so the Case Overview and AI
    Case Analysis are immediately grounded with real party names without
    manual re-entry. Idempotent across repeated syncs."""
    existing_parties = (
        sc.table("litigation_parties")
        .select("*")
        .eq("matter_id", matter["id"])
        .execute()
        .data
        or []
    )
    existing_by_name = {
        (p.get("party_name", "").strip().lower(), p.get("party_type", "").strip().lower()): p
        for p in existing_parties
    }

    petitioner_adv = ", ".join(case_detail.petitioner_advocates) if case_detail.petitioner_advocates else None
    for idx, pet in enumerate(case_detail.petitioners):
        name = pet.strip()
        if not name:
            continue
        key = (name.lower(), "petitioner")
        if key not in existing_by_name:
            sc.table("litigation_parties").insert(
                {
                    "matter_id": matter["id"],
                    "party_type": "Petitioner",
                    "party_name": name,
                    "party_number": idx + 1,
                    "advocate_name": petitioner_adv if idx == 0 else None,
                }
            ).execute()

    respondent_adv = ", ".join(case_detail.respondent_advocates) if case_detail.respondent_advocates else None
    for idx, resp in enumerate(case_detail.respondents):
        name = resp.strip()
        if not name:
            continue
        key = (name.lower(), "respondent")
        if key not in existing_by_name:
            sc.table("litigation_parties").insert(
                {
                    "matter_id": matter["id"],
                    "party_type": "Respondent",
                    "party_name": name,
                    "party_number": idx + 1,
                    "advocate_name": respondent_adv if idx == 0 else None,
                }
            ).execute()


def _upsert_litigation_facts_and_evidence(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Populates the evidentiary timeline (public.litigation_facts_evidence,
    migrations 0013 & 0014) from eCourts case milestones, FIR details,
    interlocutory applications, and watermarked court order PDFs.

    This bridges procedural court sync into the matter's Facts & Exhibits
    tab, enabling the AI Case Analysis and Limitation Engine to reason over
    ground-truth court documents and procedural milestones immediately.
    Idempotent across repeated syncs."""
    existing_facts = (
        sc.table("litigation_facts_evidence")
        .select("*")
        .eq("matter_id", matter["id"])
        .execute()
        .data
        or []
    )

    case_data = (case_detail.raw.get("data", {}) or {}).get("courtCaseData", {}) or {}

    # 1. FIR Details
    fir = case_data.get("firDetails")
    if isinstance(fir, dict) and fir.get("caseNumber"):
        case_no = str(fir.get("caseNumber")).strip()
        ps = str(fir.get("policeStation") or "").strip()
        yr = str(fir.get("year") or "").strip()
        fir_doc_title = f"FIR No. {case_no}" + (f" ({ps})" if ps else "")
        fir_summary = f"FIR No. {case_no} registered at Police Station {ps or 'N/A'}" + (f", Year {yr}" if yr else "")

        match = next(
            (
                f
                for f in existing_facts
                if f.get("exhibit_number") == "Ex. FIR"
                or (f.get("document_title") and case_no in f.get("document_title"))
                or (f.get("fact_summary") and case_no in f.get("fact_summary") and "FIR" in f.get("fact_summary"))
            ),
            None,
        )
        payload = {
            "matter_id": matter["id"],
            "fact_summary": fir_summary,
            "exhibit_number": "Ex. FIR",
            "document_title": fir_doc_title,
            "relevance_notes": "Underlying Police Station FIR recorded in eCourts metadata",
        }
        if match:
            sc.table("litigation_facts_evidence").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("litigation_facts_evidence").insert(payload).execute()

    # 2. Case Institution / Filing milestone
    filing_date = case_data.get("filingDate")
    case_type = case_data.get("caseTypeRaw") or case_data.get("caseType") or "Case"
    reg_no = case_data.get("registrationNumber")
    filing_no = case_data.get("filingNumber")
    if filing_date:
        filing_doc_title = f"Case Filing: {case_type} {reg_no or ''}".strip()
        filing_summary = f"{case_type} instituted in {case_detail.court_name or 'Court'}" + (
            f" (Filing No. {filing_no})" if filing_no else ""
        ) + (f", Registered as {reg_no}" if reg_no else "")
        match = next(
            (
                f
                for f in existing_facts
                if f.get("exhibit_number") == "Ex. Petition"
                or (f.get("document_title") and f.get("document_title").startswith("Case Filing"))
            ),
            None,
        )
        payload = {
            "matter_id": matter["id"],
            "event_date": filing_date,
            "fact_summary": filing_summary,
            "exhibit_number": "Ex. Petition",
            "document_title": filing_doc_title,
            "relevance_notes": f"Case institution milestone recorded on eCourts (CNR: {cnr})",
        }
        if match:
            sc.table("litigation_facts_evidence").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("litigation_facts_evidence").insert(payload).execute()

    # 3. Interlocutory Applications (IAs)
    for idx, ia in enumerate(case_detail.interlocutory_applications):
        ia_num = ia.application_number
        doc_title = f"Application {ia_num}"
        summary = f"Interlocutory Application {ia_num} filed by {ia.filed_by}" + (
            f" (Status: {ia.status_raw})" if ia.status_raw else ""
        )
        match = next(
            (
                f
                for f in existing_facts
                if (f.get("document_title") == doc_title)
                or (f.get("fact_summary") and ia_num in f.get("fact_summary"))
                or (f.get("exhibit_number") == f"Ex. IA-{idx + 1}")
            ),
            None,
        )
        payload = {
            "matter_id": matter["id"],
            "event_date": ia.filing_date,
            "fact_summary": summary,
            "exhibit_number": f"Ex. IA-{idx + 1}",
            "document_title": doc_title,
            "relevance_notes": f"Interlocutory application recorded on eCourts (Status: {ia.status_raw})",
        }
        if match:
            sc.table("litigation_facts_evidence").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("litigation_facts_evidence").insert(payload).execute()

    # 4. Court Orders & Judgments (with True Copy PDFs)
    for idx, order in enumerate(case_detail.interim_orders):
        order_date = order.get("order_date") or order.get("orderDate")
        order_url = order.get("order_url") or order.get("orderUrl")
        desc = order.get("description") or "Court Order"
        doc_title = f"Court Order dated {order_date}" if order_date else "Court Order"
        safe_file_name = order_url.rsplit("/", 1)[-1].split("?")[0] if order_url else None
        order_summary = (
            f"Court order passed by {case_detail.court_name or 'Court'}"
            + (f" on {order_date}" if order_date else "")
            + (f" ({desc})" if desc and desc != "Court Order" else "")
        )

        match = next(
            (
                f
                for f in existing_facts
                if (order_url and f.get("file_url") == order_url)
                or (
                    order_date
                    and f.get("event_date") == order_date
                    and (
                        f.get("exhibit_number") == f"Ex. Order-{idx + 1}"
                        or (f.get("document_title") or "").startswith("Court Order")
                    )
                )
            ),
            None,
        )
        payload = {
            "matter_id": matter["id"],
            "event_date": order_date,
            "fact_summary": order_summary,
            "exhibit_number": f"Ex. Order-{idx + 1}",
            "document_title": doc_title,
            "relevance_notes": "Official True Copy order downloaded and cached from eCourts",
            "file_url": order_url,
            "file_name": safe_file_name,
            "mime_type": "application/pdf" if order_url else None,
        }
        if match:
            sc.table("litigation_facts_evidence").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("litigation_facts_evidence").insert(payload).execute()

    # 5. Filed Documents
    for idx, doc in enumerate(case_detail.filed_documents):
        if not isinstance(doc, dict):
            continue
        title = doc.get("document_title") or doc.get("title") or doc.get("fileName") or f"Filed Document {idx + 1}"
        doc_url = doc.get("file_url") or doc.get("url") or doc.get("documentUrl")
        match = next(
            (
                f
                for f in existing_facts
                if (doc_url and f.get("file_url") == doc_url) or f.get("document_title") == title
            ),
            None,
        )
        payload = {
            "matter_id": matter["id"],
            "fact_summary": f"Document filed in court: {title}",
            "exhibit_number": f"Ex. Doc-{idx + 1}",
            "document_title": title,
            "relevance_notes": "Document filed on record in eCourts",
            "file_url": doc_url,
            "file_name": doc_url.rsplit("/", 1)[-1].split("?")[0] if doc_url else None,
            "mime_type": "application/pdf" if doc_url else None,
        }
        if match:
            sc.table("litigation_facts_evidence").update(payload).eq("id", match["id"]).execute()
        else:
            sc.table("litigation_facts_evidence").insert(payload).execute()


def _upsert_hearings_from_case_detail(sc, *, matter: dict[str, Any], cnr: str, case_detail) -> None:
    """Upserts scheduled and historical hearing entries into `hearings`
    from case_detail (next_hearing_date, firstHearingDate, historyOfCaseHearings).
    Ensures that the Hearing Docket and Calendar show scheduled court
    appearances immediately upon sync without waiting for the 24-hour
    causelist window. Idempotent across repeated syncs."""
    case_data = (case_detail.raw.get("data", {}) or {}).get("courtCaseData", {}) or {}

    hearing_candidates = []
    if case_detail.next_hearing_date:
        hearing_candidates.append(
            {
                "date": str(case_detail.next_hearing_date)[:10],
                "title": f"Hearing — {matter.get('title', 'Matter')}",
            }
        )

    first_date = case_data.get("firstHearingDate")
    if first_date and str(first_date)[:10] != str(case_detail.next_hearing_date or "")[:10]:
        hearing_candidates.append(
            {
                "date": str(first_date)[:10],
                "title": f"First Hearing — {matter.get('title', 'Matter')}",
            }
        )

    for h in case_data.get("historyOfCaseHearings") or []:
        if isinstance(h, dict):
            h_date = h.get("hearingDate") or h.get("date") or h.get("businessDate")
            if h_date:
                d_str = str(h_date)[:10]
                if not any(c["date"] == d_str for c in hearing_candidates):
                    hearing_candidates.append(
                        {
                            "date": d_str,
                            "title": f"Hearing ({d_str}) — {matter.get('title', 'Matter')}",
                        }
                    )

    for item in hearing_candidates:
        date_str = item["date"]
        if not date_str:
            continue

        existing = sc.table("hearings").select("*").eq("matter_id", matter["id"]).execute().data or []
        match = next((h for h in existing if str(h.get("hearing_at", "")).startswith(date_str)), None)

        if match and match.get("source") == "manual_override":
            continue

        payload = {
            "matter_id": matter["id"],
            "organization_id": matter["organization_id"],
            "court": case_detail.court_name,
            "bench": case_detail.judge,
            "source": "ecourts",
            "source_synced_at": _now_iso(),
        }
        if match:
            sc.table("hearings").update(payload).eq("id", match["id"]).execute()
        else:
            payload.update(
                {
                    "user_id": matter["user_id"],
                    "hearing_at": f"{date_str}T10:00:00+00:00",
                    "title": item["title"],
                    "case_no": matter.get("case_number_formatted"),
                }
            )
            sc.table("hearings").insert(payload).execute()


def sync_matter_court_data(matter_id: str, sc) -> dict[str, Any]:
    """Full sync for one matter. `sc` is a service_client() instance --
    the caller (scheduler script) is responsible for supplying it; this
    function never constructs its own, to keep it testable against a
    fake."""
    tracking_rows = (
        sc.table("court_case_tracking").select("*").eq("matter_id", matter_id).limit(1).execute().data
    )
    if not tracking_rows or not tracking_rows[0].get("tracking_enabled"):
        raise CourtSyncSkipped("tracking not enabled for this matter")
    tracking = tracking_rows[0]

    cnr = tracking.get("cnr_number")
    if not cnr:
        raise CourtSyncSkipped("no CNR set for this matter")

    matter_rows = sc.table("matters").select("*").eq("id", matter_id).limit(1).execute().data
    if not matter_rows:
        raise CourtSyncSkipped(f"matter {matter_id} not found")
    matter = matter_rows[0]
    organization_id = matter["organization_id"]

    org_rows = sc.table("organizations").select("access_enabled,subscription_status").eq("id", organization_id).limit(1).execute().data
    if not org_rows or not org_rows[0]["access_enabled"] or org_rows[0]["subscription_status"] in _PAUSED_STATUSES:
        # Policy (spec Section 8): expired/suspended orgs do not consume
        # eCourts API usage. Cached historical data (tracking row, past
        # hearings) is left exactly as-is -- only the outbound call is skipped.
        raise CourtSyncSkipped(f"organization {organization_id} access is not active")

    sc.table("court_case_tracking").update({"sync_status": "syncing"}).eq("id", tracking["id"]).execute()

    gateway = CourtDataGateway()
    try:
        case_detail = gateway.case_lookup(cnr)
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="case_lookup", status="success")
        try:
            _cache_ecourts_files_for_case(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, case_detail=case_detail, gateway=gateway)
        except Exception:
            # File caching is a pure optimization -- never block persisting
            # the case_lookup result we already have if it fails.
            logger.exception("court_sync: failed to cache eCourts files for matter_id=%s", matter_id)
        try:
            _upsert_case_advocates(sc, matter=matter, cnr=cnr, case_detail=case_detail)
            _upsert_interlocutory_applications(sc, matter=matter, cnr=cnr, case_detail=case_detail)
            _upsert_ecourts_orders(sc, matter=matter, cnr=cnr, case_detail=case_detail)
            _upsert_litigation_parties(sc, matter=matter, cnr=cnr, case_detail=case_detail)
            _upsert_litigation_facts_and_evidence(sc, matter=matter, cnr=cnr, case_detail=case_detail)
            _upsert_hearings_from_case_detail(sc, matter=matter, cnr=cnr, case_detail=case_detail)
        except Exception:
            # Same partial-success posture as the causelist_batch failure
            # below: advocate/IA/order/facts/hearings persistence failing must never discard
            # the case_lookup result we already have, or block the rest of
            # sync (causelist upserts, tracking row update).
            logger.exception("court_sync: failed to persist advocates/IAs/orders/parties/facts/hearings for matter_id=%s", matter_id)
    except CourtDataNotConfiguredError:
        raise
    except CourtDataGatewayError as exc:
        # provider_metadata is explicitly cleared here, not left as-is: a
        # matter whose CNR changes and then fails to look up would
        # otherwise keep serving the PREVIOUS (different) case's cached
        # data under the new CNR -- found by testing two real CNRs against
        # the same matter, where the second (failed) lookup left the first
        # case's petitioner/court/FIR data sitting there mislabeled under
        # the new, never-successfully-looked-up CNR.
        #
        # 404/402 each get their OWN last_error text -- found in production
        # (2026-09-07, same day for both): a genuine CNR typo, and
        # separately a real quota/billing exhaustion, both surfaced as the
        # same generic "Case lookup failed" / router 502 "unable to reach
        # the provider", sending the user chasing a connectivity problem
        # that didn't exist in either case. See those exceptions' own
        # docstrings.
        if isinstance(exc, CourtDataNotFoundError):
            last_error = "CNR not found on eCourts. Double-check the CNR and try again."
        elif isinstance(exc, CourtDataQuotaExceededError):
            last_error = "eCourts API quota/billing issue (402 from the provider). Check the eCourts account's plan/billing status."
        else:
            last_error = "Case lookup failed. See sync log for detail."
        sc.table("court_case_tracking").update(
            {
                "sync_status": "error",
                "last_error": last_error,
                "last_synced_at": _now_iso(),
                "provider_metadata": None,
            }
        ).eq("id", tracking["id"]).execute()
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="case_lookup", status="error", error_message=str(exc))
        raise

    hearing_created = False
    hearing_row: dict[str, Any] | None = None
    # Prefer causelist_batch's 'nextListing'.date (an imminent, actually-
    # listed hearing) over case_detail.next_hearing_date (the case's own
    # scheduled next-hearing field, courtCaseData.nextHearingDate) -- both
    # confirmed fields, see their own dataclasses' comments. Was never
    # actually written before this fix, despite existing since 0025
    # (court_case_tracking.next_hearing_date), found while wiring up the
    # case-details UI -- and a real end-to-end run (2026-09-07) surfaced
    # that causelist alone leaves it null far more often than not (a case
    # only shows up on causelist_batch right around the listing itself),
    # which is why the case_detail fallback was added the same day.
    next_hearing_date: str | None = case_detail.next_hearing_date
    try:
        causelist = gateway.causelist_batch([cnr])
        entry = causelist.get(cnr)
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="causelist_batch", status="success")
        if entry and entry.has_causelist:
            hearing_row, hearing_created = _upsert_hearing_from_causelist(sc, matter=matter, entry=entry)
            _upsert_causelist_row(sc, matter=matter, cnr=cnr, entry=entry, judges=case_detail.judges)
            if entry.date:
                next_hearing_date = entry.date
    except CourtDataGatewayError as exc:
        # A causelist failure does not invalidate the case_lookup we
        # already have -- log it, keep going, surface a partial success.
        _log(sc, organization_id=organization_id, matter_id=matter_id, cnr=cnr, operation="causelist_batch", status="error", error_message=str(exc))

    tracking_payload = {
        "sync_status": "synced",
        "last_error": None,
        "last_synced_at": _now_iso(),
        "provider_metadata": case_detail.raw,
        # Same already-verified fields case_detail carries -- stored
        # separately so a caller (case-details UI) never has to parse
        # provider_metadata's raw envelope itself, see 0028's migration
        # note.
        "court_name": case_detail.court_name,
        "judge": case_detail.judge,
        "case_status": case_detail.status,
        "petitioners": case_detail.petitioners,
        "respondents": case_detail.respondents,
        "next_hearing_date": next_hearing_date,
    }
    try:
        sc.table("court_case_tracking").update(
            {
                **tracking_payload,
                "interim_orders": case_detail.interim_orders,
                "filed_documents": case_detail.filed_documents,
            }
        ).eq("id", tracking["id"]).execute()
    except Exception:
        sc.table("court_case_tracking").update(tracking_payload).eq("id", tracking["id"]).execute()

    if hearing_row:
        notify_hearing_listed(
            sc,
            organization_id=organization_id,
            user_id=matter["user_id"],
            matter_id=matter_id,
            matter_title=matter.get("title", "Matter"),
            hearing_date=str(hearing_row.get("hearing_at", ""))[:10],
            court=hearing_row.get("court"),
            bench=hearing_row.get("bench"),
            item_no=hearing_row.get("item_no"),
        )

    return {
        "status": "synced",
        "matter_id": matter_id,
        "hearing_id": hearing_row["id"] if hearing_row else None,
        "hearing_created": hearing_created,
    }


def matters_due_for_sync(sc) -> list[dict[str, Any]]:
    """Every tracking-enabled matter -- the scheduler script itself
    decides the lookahead window (spec Section 8: "configurable sync
    window/interval/lookahead") by filtering on next_hearing_date after
    calling this; kept here as a plain, un-filtered list so that decision
    stays in one place (the script), not duplicated into this module."""
    return sc.table("court_case_tracking").select("*").eq("tracking_enabled", True).execute().data or []
