"""Auth dependency: validates the caller's Supabase JWT and hands back a
per-request, RLS-scoped Supabase client (see db.py) so every query the
route makes is enforced by Postgres RLS as that user — never the service
role.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException
from supabase import Client

from app.db import anon_client, user_client


@dataclass
class CurrentUser:
    id: str
    email: str | None
    db: Client


def get_current_user(authorization: str = Header(...)) -> CurrentUser:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        resp = anon_client().auth.get_user(token)
    except Exception as exc:  # noqa: BLE001 — any auth SDK error means "not authenticated"
        raise HTTPException(status_code=401, detail=f"Invalid session: {exc}") from exc

    if resp is None or resp.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return CurrentUser(id=resp.user.id, email=resp.user.email, db=user_client(token))
