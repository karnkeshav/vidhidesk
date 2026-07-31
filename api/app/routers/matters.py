from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db import service_client
from app.models.schemas import MatterCreate, MatterOut, MessageCreate, MessageOut, MODULE_TASK_TYPE
from app.services.llm_gateway import ProviderError, generate
from app.services.pii_mask import MaskMap, SupabaseMaskStore, mask_text

router = APIRouter(prefix="/api/matters", tags=["matters"])

# How many prior messages (user + assistant combined, not "turns") to
# send as conversation history on every new message. Small on purpose:
# this is a single-user tool with modest per-request latency budget, and
# every extra assistant turn in history costs a re-mask pass (see
# _build_history) on top of the tokens themselves.
MAX_HISTORY_MESSAGES = 6


@router.post("", response_model=MatterOut, status_code=201)
def create_matter(body: MatterCreate, user: CurrentUser = Depends(get_current_user)):
    row = {
        "user_id": user.id,
        "title": body.title,
        "client_name": body.client_name,
        "module": body.module,
    }
    resp = user.db.table("matters").insert(row).execute()
    return resp.data[0]


@router.get("", response_model=list[MatterOut])
def list_matters(user: CurrentUser = Depends(get_current_user)):
    resp = (
        user.db.table("matters")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data


def _get_matter_or_404(user: CurrentUser, matter_id: str) -> dict:
    resp = user.db.table("matters").select("*").eq("id", matter_id).limit(1).execute()
    if not resp.data:
        # RLS makes another user's matter look identical to a missing one —
        # that's the point: no ownership-probing oracle.
        raise HTTPException(status_code=404, detail="Matter not found")
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
