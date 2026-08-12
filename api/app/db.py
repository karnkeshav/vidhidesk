"""Supabase client factories.

Two flavours, matching CLAUDE.md's RLS requirement ("only the owning user
reads their matters"):

- `service_client()` — service-role key, bypasses RLS. Used only for
  operations on shared/reference data that isn't user-owned (citation
  cache, statute corpus, templates) or for trusted server-side writes —
  including pii_masks, which carries no RLS policies at all (see
  migrations/0002_rls.sql) and is reachable only via this client.
- `user_client(access_token)` — anon key with the caller's JWT attached,
  so every query goes through Postgres RLS as that user. Used for all
  matter/message/draft access.

Auth Request Forensics Sprint, latency follow-up (2026-08-11): measured
against the real project, an uncached client pays ~1000ms on its first
Postgrest call vs. ~170ms on a warm/reused one (see the sprint's timing
investigation) -- yet only service_client() was ever cached. anon_client()
takes no arguments and is always identical, so it was briefly cached the
same way -- REVERTED the same day: production logs showed auth.get_user()
calls (the one thing sharing that cached client touches) taking 20-64
seconds under real traffic, clustered in a way consistent with requests
queuing behind a shared client, immediately after this went live. Not
conclusively reproduced locally (concurrent-thread repros against the
real Supabase project stayed fast), so the exact mechanism is unconfirmed
-- but it's the one variable changed in that path, and going back to a
fresh client per call is essentially free (~30-500ms) next to the
alternative. If auth.get_user() is still slow after this revert, that
points at something external (Render's outbound path to Supabase, or
Supabase's edge itself) rather than this client's lifecycle.
user_client() was never cached here in the first place: it's keyed by a
per-request access token, and naively caching by token would grow
unbounded over the process lifetime with no eviction for
expired/revoked tokens -- a real memory/staleness risk, not just an
optimization left on the table.

Both PostgREST timeout defaults (2026-08-11 finding): supabase-py's
ClientOptions defaults postgrest_client_timeout to 120 seconds -- far
looser than the frontend's own 12s fetch timeout (web/src/lib/api.ts),
so a slow/stalled Supabase response left the backend still working long
after the browser had given up, rather than failing fast. Set explicitly
below to bound worst-case backend latency well under the frontend's
ceiling.
"""

from __future__ import annotations

from functools import lru_cache

import httpx
from supabase import AsyncClient, Client, ClientOptions, create_async_client, create_client

from app.config import get_settings

# See "PostgREST timeout defaults" above. Deliberately well under the
# frontend's 12s FETCH_TIMEOUT_MS (web/src/lib/api.ts) so a stalled
# Supabase call fails fast and observably on the backend instead of
# silently outliving the client's own timeout.
SUPABASE_POSTGREST_TIMEOUT_S = 5

# Auth HTTP transport timeout for anon_client(). Dedicated short timeout
# (connect/read/write/pool) so an upstream Supabase Auth or Cloudflare edge
# stall fails fast on the backend within ~4s instead of blocking for 20-47s.
SUPABASE_AUTH_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=3.0)


@lru_cache
def service_client() -> Client:
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key,
        options=ClientOptions(postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_S),
    )


def user_client(access_token: str) -> Client:
    settings = get_settings()
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_S,
        ),
    )
    return client


def anon_client() -> Client:
    """Unauthenticated client — only used to validate a bearer token via
    auth.get_user(), never to read/write tables. NOT cached (see module
    docstring, "REVERTED the same day") -- was briefly a cached singleton
    like service_client(), reverted after production showed severe
    auth.get_user() slowdowns under concurrent traffic once it went live."""
    settings = get_settings()
    auth_httpx = httpx.Client(
        timeout=SUPABASE_AUTH_TIMEOUT,
        follow_redirects=True,
        http2=True,
    )
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_S,
            httpx_client=auth_httpx,
        ),
    )


async def async_anon_client() -> AsyncClient:
    """Unauthenticated async client factory — creates a dedicated AsyncClient
    used exclusively by get_current_user() with httpx.AsyncClient transport,
    allowing asyncio.wait_for() to enforce a true wall-clock deadline (~4s)."""
    settings = get_settings()
    auth_httpx = httpx.AsyncClient(
        timeout=SUPABASE_AUTH_TIMEOUT,
        follow_redirects=True,
        http2=True,
    )
    return await create_async_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_S,
            httpx_client=auth_httpx,
        ),
    )


