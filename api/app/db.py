"""Supabase client factories.

Two flavours, matching CLAUDE.md's RLS requirement ("only the owning user
reads their matters"):

- `service_client()` — service-role key, bypasses RLS. Used only for
  operations on shared/reference data that isn't user-owned (citation
  cache, statute corpus, templates) or for trusted server-side writes.
- `user_client(access_token)` — anon key with the caller's JWT attached,
  so every query goes through Postgres RLS as that user. Used for all
  matter/message/draft/pii_mask access.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import get_settings


@lru_cache
def service_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def user_client(access_token: str) -> Client:
    settings = get_settings()
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"}),
    )
    return client


def anon_client() -> Client:
    """Unauthenticated client — only used to validate a bearer token via
    auth.get_user(), never to read/write tables."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)
