from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db import service_client
from app.models.schemas import MatterCreate, MatterOut, MessageCreate, MessageOut, MODULE_TASK_TYPE
from app.services.llm_gateway import ProviderError, generate
from app.services.pii_mask import SupabaseMaskStore

router = APIRouter(prefix="/api/matters", tags=["matters"])


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


@router.post("/{matter_id}/messages", response_model=list[MessageOut], status_code=201)
def send_message(
    matter_id: str, body: MessageCreate, user: CurrentUser = Depends(get_current_user)
):
    """The 'hello matter' round trip: store the user message, mask it,
    send it through the LLM gateway, unmask the reply, store that too.
    Returns [user_message, assistant_message]."""
    matter = _get_matter_or_404(user, matter_id)

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

    task_type = MODULE_TASK_TYPE.get(matter["module"], "chat")

    try:
        result = generate(
            body.content, task_type=task_type, mask_map=mask_map, entities=entities
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
