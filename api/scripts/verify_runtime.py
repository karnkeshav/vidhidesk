"""Part 1/7 — Runtime Verification (Sprint 3.5.5B).

Unlike every other verify_*.py script, this one does not talk to
Supabase/LLM providers/storage directly — it talks to a RUNNING instance
of the VidhiDesk API itself (local `uvicorn` during development/CI, or
the real deployed Render instance in production), the way an actual
client would. This is the "is the deployed service actually healthy"
check, distinct from "is the infrastructure it depends on healthy"
(that's verify_database.py / verify_storage.py / verify_llm_providers.py).

Base URL is configurable via the RUNTIME_VERIFY_BASE_URL environment
variable; defaults to http://localhost:8000 for local/CI use against a
freshly-started `uvicorn app.main:app`. This script does NOT start the
server itself — start it separately (see
docs/40_Operations/Runtime_Health_Check.md) and point this at it.

Run standalone: python scripts/verify_runtime.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with, timed  # noqa: E402


def run(base_url: str | None = None) -> VerificationResult:
    """`base_url` is read fresh on every call (falling back to the
    RUNTIME_VERIFY_BASE_URL env var, then localhost:8000) rather than
    frozen as a module-level constant at import time — a caller like
    verify_project.py that starts its own ephemeral local server and sets
    the env var *after* importing this module needs that, otherwise the
    import-time value wins regardless of what's set later."""
    BASE_URL = base_url or os.environ.get("RUNTIME_VERIFY_BASE_URL", "http://localhost:8000")
    result = VerificationResult(f"Runtime Verification (Part 1/7) — {BASE_URL}")

    health, dt, err = timed(lambda: httpx.get(f"{BASE_URL}/health", timeout=5.0))
    if err is not None:
        result.add(
            "GET /health",
            Status.FAIL,
            f"Could not reach {BASE_URL}: {type(err).__name__}: {err}. "
            "Is the server running? See docs/40_Operations/Runtime_Health_Check.md.",
            dt,
        )
        # Every other check depends on the server being reachable at all —
        # no point attempting them and reporting a wall of identical
        # connection-refused failures.
        result.add("Remaining runtime checks", Status.SKIP, "Server unreachable — see GET /health above")
        return result

    if health.status_code != 200:
        result.add("GET /health", Status.FAIL, f"HTTP {health.status_code}: {health.text[:200]}", dt)
    else:
        body = health.json()
        result.add("GET /health", Status.PASS, f"HTTP 200: {body}", dt)
        if "not legal advice" not in body.get("notice", "").lower():
            result.add(
                "Health response carries the advocate-review disclaimer",
                Status.WARN,
                "CLAUDE.md Hard Rule 5 requires this notice on every screen — /health is a reasonable place to also carry it as a smoke-test surface, but it's not required to.",
            )
        else:
            result.add("Health response carries the advocate-review disclaimer", Status.PASS, "Present")

    openapi, dt, err = timed(lambda: httpx.get(f"{BASE_URL}/openapi.json", timeout=5.0))
    if err is not None or openapi.status_code != 200:
        result.add("GET /openapi.json", Status.FAIL, f"{err or f'HTTP {openapi.status_code}'}", dt)
    else:
        spec = openapi.json()
        n_paths = len(spec.get("paths", {}))
        result.add("GET /openapi.json", Status.PASS, f"{n_paths} routes registered", dt)

        # One representative real path per feature area — pulled from an
        # actual /openapi.json dump, not guessed from router prefixes.
        # (Most routers here share a generic prefix="/api" and namespace
        # by per-endpoint path instead, e.g. contracts.py has no
        # "/api/contracts" prefix at all — templates/drafts live directly
        # under "/api/templates" and "/api/matters/.../drafts".)
        expected_paths = {
            "Matter Engine": "/api/matters",
            "Litigation Parties": "/api/matters/{matter_id}/parties",
            "AI Case Analysis": "/api/matters/{matter_id}/case-analysis",
            "Limitation Engine": "/api/litigation/limitation-calculator",
            "Forum Advisor": "/api/litigation/forum-advisor",
            "Template/Contracts Engine": "/api/templates",
            "Advocate Profile": "/api/profile",
            "Citation Rendering": "/api/citations/render",
        }
        live_paths = set(spec.get("paths", {}))
        missing = {area: path for area, path in expected_paths.items() if path not in live_paths}
        if missing:
            result.add(
                "Expected feature routes registered",
                Status.FAIL,
                "Missing: " + "; ".join(f"{area} ({path})" for area, path in missing.items()),
            )
        else:
            result.add("Expected feature routes registered", Status.PASS, f"All {len(expected_paths)} representative feature routes present")

    # An unauthenticated request to a protected route should be rejected,
    # not silently served — a real, live check of the auth boundary, not
    # just a code-reading assumption.
    unauth, dt, err = timed(lambda: httpx.get(f"{BASE_URL}/api/matters", timeout=5.0))
    if err is not None:
        result.add("Unauthenticated request to /api/matters is rejected", Status.FAIL, f"Request failed outright: {err}", dt)
    elif unauth.status_code in (401, 403, 422):
        result.add("Unauthenticated request to /api/matters is rejected", Status.PASS, f"HTTP {unauth.status_code} as expected", dt)
    else:
        result.add(
            "Unauthenticated request to /api/matters is rejected",
            Status.FAIL,
            f"Expected 401/403/422, got HTTP {unauth.status_code} — possible auth bypass: {unauth.text[:200]}",
            dt,
        )

    return result


if __name__ == "__main__":
    exit_with(run())
