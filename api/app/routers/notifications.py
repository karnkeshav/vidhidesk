"""In-app notifications (Litigation Intelligence + eCourts, 27 Aug 2026).
Read-only + mark-read for the frontend -- creation only ever happens via
app/services/notifications.py, called from court_sync.py/hearing_brief.py
with service_client() (notifications has no authenticated-role INSERT
policy, 0025_litigation_intelligence_ecourts.sql)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUser, get_current_user
from app.models.schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(user: CurrentUser = Depends(get_current_user)):
    res = user.db.table("notifications").select("*").order("created_at", desc=True).limit(50).execute()
    return res.data or []


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: str, user: CurrentUser = Depends(get_current_user)):
    existing = user.db.table("notifications").select("id").eq("id", notification_id).limit(1).execute().data
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    updated = (
        user.db.table("notifications")
        .update({"read_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", notification_id)
        .execute()
    )
    return updated.data[0]
