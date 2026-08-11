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
takes no arguments and is always identical, so it's cached the same way
now. user_client() is deliberately NOT cached here: it's keyed by a
per-request access token, and naively caching by token would grow
unbounded over the process lifetime with no eviction for
expired/revoked tokens -- a real memory/staleness risk, not just an
optimization left on the table. The shared-httpx-transport approach that
would let user_client() reuse a warm connection pool too, without
per-token caching, is intentionally deferred -- it changes transport
lifecycle and is only worth it if the two changes here don't move the
needle enough on their own.

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

from supabase import Client, ClientOptions, create_client

from app.config import get_settings

# See "PostgREST timeout defaults" above. Deliberately well under the
# frontend's 12s FETCH_TIMEOUT_MS (web/src/lib/api.ts) so a stalled
# Supabase call fails fast and observably on the backend instead of
# silently outliving the client's own timeout.
SUPABASE_POSTGREST_TIMEOUT_S = 5


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


@lru_cache
def anon_client() -> Client:
    """Unauthenticated client — only used to validate a bearer token via
    auth.get_user(), never to read/write tables. Always identical (no
    arguments), so — like service_client() — it's cached rather than
    rebuilt (with a fresh httpx connection pool) on every request."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_S),
    )
