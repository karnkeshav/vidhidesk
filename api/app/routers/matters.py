from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db import service_client

# TEMP TIMING INSTRUMENTATION (Auth Request Forensics Sprint, latency
# follow-up, 2026-08-11): see app/auth.py for the matching auth.get_user()
# timing and app/main.py for total-request timing. Remove once the
# sprint's before/after comparison is done.
_timing_logger = logging.getLogger("vidhidesk.timing")
from app.models.schemas import (
    MatterCreate,
    MatterOut,
    MatterUpdate,
    MessageCreate,
    MessageOut,
    MODULE_TASK_TYPE,
)
from app.services.llm_gateway import ProviderError, generate
from app.services.pii_mask import MaskMap, SupabaseMaskStore, mask_text

router = APIRouter(prefix="/api/matters", tags=["matters"])

# How many prior messages (user + assistant combined, not "turns") to
# send as conversation history on every new message. Small on purpose:
# this is a single-user tool with modest per-request latency budget, and
# every extra assistant turn in history costs a re-mask pass (see
# _build_history) on top of the tokens themselves.
MAX_HISTORY_MESSAGES = 6


import uuid


@router.post("", response_model=MatterOut, status_code=201)
def create_matter(body: MatterCreate, user: CurrentUser = Depends(get_current_user)):
    resolved_template_id = body.template_id
    if resolved_template_id:
        try:
            uuid.UUID(resolved_template_id)
        except ValueError:
            tpl_rows = (
                service_client()
                .table("templates")
                .select("id")
                .eq("template_key", resolved_template_id)
                .execute()
                .data
            )
            if tpl_rows:
                resolved_template_id = tpl_rows[0]["id"]

    row = {
        "user_id": user.id,
        "title": body.title,
        "client_name": body.client_name,
        "module": body.module,
    }
    if resolved_template_id:
        row["template_id"] = resolved_template_id
    if body.court_category:
        row["court_category"] = body.court_category
    if body.jurisdiction_state:
        row["jurisdiction_state"] = body.jurisdiction_state
    if body.cnr_number:
        row["cnr_number"] = body.cnr_number
    if body.case_number_formatted:
        row["case_number_formatted"] = body.case_number_formatted
    if body.litigation_stage:
        row["litigation_stage"] = body.litigation_stage
    if body.court_name:
        row["court_name"] = body.court_name
    if body.bench_name:
        row["bench_name"] = body.bench_name

    try:
        resp = user.db.table("matters").insert(row).execute()
    except Exception as exc:
        if "template_id" in str(exc) or "PGRST204" in str(exc):
            row.pop("template_id", None)
            resp = user.db.table("matters").insert(row).execute()
        else:
            raise exc

    data = resp.data[0]
    if "template_id" not in data or data["template_id"] is None:
        data["template_id"] = resolved_template_id
    return data


@router.get("", response_model=list[MatterOut])
def list_matters(user: CurrentUser = Depends(get_current_user)):
    _t0 = time.perf_counter()
    resp = (
        user.db.table("matters")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    _timing_logger.info(
        "timing matters.table_execute duration_ms=%.1f rows=%d",
        (time.perf_counter() - _t0) * 1000, len(resp.data or []),
    )
    return resp.data


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's matter look identical to a missing one —
        # that's the point: no ownership-probing oracle.
        raise HTTPException(status_code=404, detail="Matter not found")
    data = resp.data[0]
    if "template_id" not in data or data["template_id"] is None:
        drafts = service_client().table("draft_versions").select("template_id").eq("matter_id", matter_id).limit(1).execute().data
        if drafts and drafts[0].get("template_id"):
            data["template_id"] = drafts[0]["template_id"]
    return data


@router.get("/{matter_id}", response_model=MatterOut)
def get_matter(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    """Single-matter fetch — needed so the intake-form page can display
    (and, in form mode, live-update) a matter's title without fetching
    the entire matters list just to find one row."""
    return _get_matter_or_404(user, matter_id)


@router.patch("/{matter_id}", response_model=MatterOut)
def update_matter(matter_id: str, body: MatterUpdate, user: CurrentUser = Depends(get_current_user)):
    """Title-only update — backs the auto-generating-title UX: the intake
    form saves an inferred title as party names fill in (debounced
    client-side), and a manual click-to-edit override. RLS-scoped via
    user.db, same ownership guarantee as create_matter/list_matters."""
    _get_matter_or_404(user, matter_id)
    resp = user.db.table("matters").update({"title": body.title}).eq("id", matter_id).execute()
    return resp.data[0]


@router.get("/{matter_id}/messages", response_model=list[MessageOut])
def list_messages(matter_id: str, user: CurrentUser = Depends(get_current_user)):
    _get_matter_or_404(user, matter_id)
    resp = (
        user.db.table("messages")
        .select("*")
        .eq("matter_id", matter_id)
        .order("created_at")
        .execute()
    )
    return resp.data


def _fetch_recent_messages(user: CurrentUser, matter_id: str, limit: int) -> list[dict]:
    resp = (
        user.db.table("messages")
        .select("*")
        .eq("matter_id", matter_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(resp.data))  # chronological order


def _build_history(rows: list[dict], mask_map: MaskMap) -> list[dict]:
    """Turn stored message rows into masked {role, content} turns for the
    LLM gateway.

    User messages: use the persisted `masked_prompt` column — it's the
    exact text that already went out over the wire for that turn, so
    there's no reason to recompute it (and a fallback re-mask covers rows
    from before this column was populated).

    Assistant messages: `content` is deliberately stored unmasked (so the
    lawyer can read their own matter history in plain language) — sending
    that back to the LLM as-is would re-leak whatever names/PANs/etc. it
    contained. Re-masking through the same, already-loaded `mask_map`
    before it goes into history closes that off. This was one of two
    options (the other: persist a second, pre-masked copy of every
    assistant reply). Re-masking on the fly won by simplicity — no schema
    migration, no second column that could drift out of sync with the
    mask_map — at the cost of a few extra mask_text() calls per request
    (bounded by MAX_HISTORY_MESSAGES, so at most a handful of short
    re-masks, not a real latency concern for a single-user tool).
    """
    history: list[dict] = []
    for row in rows:
        if row["role"] == "user":
            content = row.get("masked_prompt") or mask_text(row["content"], mask_map)
            history.append({"role": "user", "content": content})
        elif row["role"] == "assistant":
            history.append({"role": "assistant", "content": mask_text(row["content"], mask_map)})
    return history


@router.post("/{matter_id}/messages", response_model=list[MessageOut], status_code=201)
def send_message(
    matter_id: str, body: MessageCreate, user: CurrentUser = Depends(get_current_user)
):
    """The 'hello matter' round trip: store the user message, mask it
    (with recent conversation history for context), send it through the
    LLM gateway, unmask the reply, store that too.
    Returns [user_message, assistant_message]."""
    matter = _get_matter_or_404(user, matter_id)

    # Fetched *before* inserting the current message, so it never
    # includes the message we're about to send — that goes in separately
    # as the current turn.
    prior_rows = _fetch_recent_messages(user, matter_id, MAX_HISTORY_MESSAGES)

    user_row = (
        user.db.table("messages")
        .insert({"matter_id": matter_id, "role": "user", "content": body.content})
        .execute()
        .data[0]
    )

    entities: list[tuple[str, str]] = [("PARTY", n) for n in body.party_names]
    entities += [("ADDR", a) for a in body.addresses]
    if matter.get("client_name"):
        entities.append(("PARTY", matter["client_name"]))

    mask_store = SupabaseMaskStore(service_client())
    mask_map = mask_store.load(matter_id)

    history = _build_history(prior_rows, mask_map)

    task_type = MODULE_TASK_TYPE.get(matter["module"], "chat")

    try:
        result = generate(
            body.content,
            task_type=task_type,
            mask_map=mask_map,
            entities=entities,
            history=history,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=502, detail=f"All LLM providers failed: {exc}"
        ) from exc

    mask_store.save(mask_map)

    assistant_row = (
        user.db.table("messages")
        .insert(
            {
                "matter_id": matter_id,
                "role": "assistant",
                "content": result.text,
                "model_used": f"{result.provider}/{result.model}",
                "masked_prompt": result.masked_prompt,
            }
        )
        .execute()
        .data[0]
    )

    return [user_row, assistant_row]
