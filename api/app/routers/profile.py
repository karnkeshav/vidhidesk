from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError

from app.auth import CurrentUser, get_current_user
from app.db import service_client
from app.models.schemas import AdvocateProfile, AdvocateProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _extract_meta_profile(user: CurrentUser) -> dict[str, Any]:
    """Helper to convert Supabase auth user_metadata into an AdvocateProfile dict fallback."""
    meta = user.raw_user_meta_data or {}
    return {
        "user_id": user.id,
        "full_name": meta.get("full_name"),
        "designation": meta.get("designation") or "Advocate",
        "bar_number": meta.get("bar_number"),
        "enrollment_state": meta.get("enrollment_state"),
        "enrollment_year": meta.get("enrollment_year"),
        "primary_court": meta.get("primary_court"),
        "high_court_roll_no": meta.get("high_court_roll_no"),
        "aor_code": meta.get("aor_code"),
        "firm_name": meta.get("firm_name"),
        "phone": meta.get("phone"),
        "office_address": meta.get("office_address"),
        "avatar_url": meta.get("avatar_url"),
        "practice_areas": meta.get("practice_areas") or [],
        "states_of_practice": meta.get("states_of_practice") or [],
        "languages_spoken": meta.get("languages_spoken") or [],
        "rera_advocate_reg_no": meta.get("rera_advocate_reg_no"),
        "updated_at": None,
    }


@router.get("", response_model=AdvocateProfile)
def get_profile(user: CurrentUser = Depends(get_current_user)):
    """Fetch the canonical advocate profile for the authenticated user.
    Reads from advocate_profiles table first; falls back to user_metadata if table row does not exist yet.
    """
    db = user.db
    try:
        res = db.table("advocate_profiles").select("*").eq("user_id", user.id).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            row["user_id"] = str(row["user_id"])
            return AdvocateProfile(**row)
    except Exception:
        pass

    # Fallback to user_metadata
    return AdvocateProfile(**_extract_meta_profile(user))


@router.put("", response_model=AdvocateProfile)
def update_profile(
    body: AdvocateProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Upsert advocate profile details into public.advocate_profiles table
    and sync fallback metadata to Supabase auth user_metadata.
    """
    db = user.db

    # Prepare update dictionary with non-None values
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    update_data["user_id"] = user.id

    # 1. Attempt database upsert into advocate_profiles table
    profile_saved_row = None
    try:
        res = db.table("advocate_profiles").upsert(update_data, on_conflict="user_id").execute()
        if res.data and len(res.data) > 0:
            profile_saved_row = res.data[0]
    except Exception:
        pass

    # 2. Sync to auth.users.user_metadata so top header and auth state remain in sync
    try:
        svc = service_client()
        svc.auth.admin.update_user_by_id(user.id, {"user_metadata": update_data})
    except Exception:
        pass

    if profile_saved_row:
        profile_saved_row["user_id"] = str(profile_saved_row["user_id"])
        return AdvocateProfile(**profile_saved_row)

    # Return merged fallback profile
    merged_meta = _extract_meta_profile(user)
    merged_meta.update(update_data)
    return AdvocateProfile(**merged_meta)


@router.post("/avatar", response_model=AdvocateProfile)
async def upload_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload advocate avatar image (max 2MB, JPG/PNG/WEBP) to Supabase Storage
    and update profile avatar_url.
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Allowed formats: JPG, PNG, WEBP.",
        )

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit of 2MB.",
        )

    # Upload to avatars bucket in Supabase storage (or save storage URL)
    file_ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
    avatar_path = f"avatars/{user.id}.{file_ext}"

    try:
        svc = service_client()
        svc.storage.from_("avatars").upload(
            path=avatar_path,
            file=content,
            file_options={"content-type": file.content_type, "upsert": "true"},
        )
        avatar_url = svc.storage.from_("avatars").get_public_url(avatar_path)
    except Exception:
        # Fallback to data URL or relative avatar path if bucket upload fails
        avatar_url = f"/avatars/{user.id}.{file_ext}"

    # Update profile avatar_url
    return update_profile(AdvocateProfileUpdate(avatar_url=avatar_url), user=user)
