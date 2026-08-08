"""Part 5 — Environment Verification (Sprint 3.5.5B).

Checks the real .env files this process would actually load, for real:
required variables present and non-empty, no duplicate keys silently
shadowing each other, no obviously-placeholder values, and a couple of
sane-default checks (CORS wildcard, Supabase URL shape).

Run standalone: python scripts/verify_environment.py
Run as part of the full suite: python scripts/verify_project.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
WEB_ENV_FILE = REPO_ROOT / "web" / ".env.local"

# Required per api/app/config.py's Settings model.
REQUIRED_BACKEND_VARS = [
    "INDIAN_KANOON_API_TOKEN",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "SAMBANOVA_API_KEY",
    "CEREBRAS_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
]
# Required per web/src/lib/api.ts / web/src/lib/supabase.ts.
REQUIRED_FRONTEND_VARS = [
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_API_URL",
]

_PLACEHOLDER_RE = re.compile(r"(your[-_]?key|changeme|xxx+|placeholder|example\.com|<.*>|\btodo\b)", re.IGNORECASE)


def _parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Returns (last-value-wins dict, keys defined more than once).
    Deliberately does its own parsing rather than relying on
    python-dotenv, which silently takes the last value and gives no way
    to detect that a key was ever duplicated in the first place."""
    values: dict[str, str] = {}
    seen_counts: dict[str, int] = {}
    if not path.exists():
        return values, []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        seen_counts[key] = seen_counts.get(key, 0) + 1
        values[key] = val
    duplicates = sorted(k for k, n in seen_counts.items() if n > 1)
    return values, duplicates


def _check_file(result: VerificationResult, label: str, path: Path, required_vars: list[str]) -> None:
    if not path.exists():
        result.add(f"{label} exists", Status.FAIL, f"Not found at {path}")
        for var in required_vars:
            result.add(f"{label}: {var}", Status.FAIL, "Cannot check — file missing")
        return

    result.add(f"{label} exists", Status.PASS, str(path))
    values, duplicates = _parse_env_file(path)

    for var in required_vars:
        if var not in values:
            result.add(f"{label}: {var}", Status.FAIL, "Not defined in this file")
        elif not values[var]:
            result.add(f"{label}: {var}", Status.FAIL, "Defined but empty")
        elif _PLACEHOLDER_RE.search(values[var]):
            result.add(f"{label}: {var}", Status.FAIL, "Value matches a placeholder pattern — not a real credential")
        else:
            result.add(f"{label}: {var}", Status.PASS, f"{len(values[var])} chars, non-placeholder")

    if duplicates:
        result.add(
            f"{label}: duplicate keys",
            Status.WARN,
            f"Defined more than once (last value silently wins): {', '.join(duplicates)}",
        )
    else:
        result.add(f"{label}: duplicate keys", Status.PASS, "No duplicate keys found")


def run() -> VerificationResult:
    result = VerificationResult("Environment Verification (Part 5)")

    _check_file(result, "Backend (.env)", ENV_FILE, REQUIRED_BACKEND_VARS)
    _check_file(result, "Frontend (web/.env.local)", WEB_ENV_FILE, REQUIRED_FRONTEND_VARS)

    # Unsafe-defaults checks, via the real Settings loader (not a re-parse) —
    # this exercises the exact code path the running app uses.
    try:
        sys.path.insert(0, str(API_ROOT))
        from app.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        if "*" in settings.cors_origins:
            result.add("CORS origins — no wildcard", Status.FAIL, f"'*' present: {settings.cors_origins}")
        else:
            result.add("CORS origins — no wildcard", Status.PASS, str(settings.cors_origins))

        if settings.supabase_url and not settings.supabase_url.startswith("https://"):
            result.add("SUPABASE_URL shape", Status.FAIL, f"Does not start with https://: {settings.supabase_url!r}")
        elif settings.supabase_url:
            result.add("SUPABASE_URL shape", Status.PASS, "Starts with https://")
        else:
            result.add("SUPABASE_URL shape", Status.SKIP, "Not set — already flagged above")
    except Exception as exc:  # noqa: BLE001
        result.add("app.config.get_settings() loads cleanly", Status.FAIL, f"{type(exc).__name__}: {exc}")

    return result


if __name__ == "__main__":
    exit_with(run())
