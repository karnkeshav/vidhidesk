"""Deployment drift check (Oracle Migration Sprint, Phase 10).

Compares two things that must agree once Oracle is the production
backend:
  1. The latest commit SHA on GitHub's `main` branch (via the public
     GitHub REST API -- no auth needed for a public repo's own branch
     ref; pass an explicit SHA instead if this is ever rate-limited).
  2. What SHA Oracle's own GET /version endpoint reports it is actually
     running (see api/app/routers/version.py, api/Dockerfile's
     GIT_COMMIT_SHA build ARG).

This deliberately checks the *running* SHA, not Oracle's on-disk checked-
out SHA -- "what commit does a real client's request actually get served
by" is the fact that matters for "is production actually what we think it
is," and is also the only one of the two that's checkable without SSH.

UNEXECUTED / UNVERIFIED as of this draft -- has never been run against a
real Oracle instance, because none is reachable from this environment.
Written to the same verify_*.py contract (Status/VerificationResult,
scripts/verify_common.py) as the rest of api/scripts/ so it can be added
to verify_project.py and to .github/workflows/oracle-deploy.yml the same
way every other check in this repo is wired in, once Oracle is live.

Run standalone:
    python scripts/check_deployment_drift.py <expected_sha> <oracle_base_url>
Or via env vars (used by oracle-deploy.yml):
    EXPECTED_SHA=... ORACLE_BASE_URL=... python scripts/check_deployment_drift.py
Or with no expected SHA at all, to resolve main's current HEAD live:
    ORACLE_BASE_URL=... python scripts/check_deployment_drift.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with, timed  # noqa: E402

GITHUB_REPO = "karnkeshav/vidhidesk"


def _resolve_expected_sha(argv: list[str]) -> str | None:
    if len(argv) > 1 and argv[1]:
        return argv[1]
    return os.environ.get("EXPECTED_SHA") or None


def _resolve_base_url(argv: list[str]) -> str | None:
    if len(argv) > 2 and argv[2]:
        return argv[2]
    return os.environ.get("ORACLE_BASE_URL") or None


def run(expected_sha: str | None, base_url: str | None) -> VerificationResult:
    result = VerificationResult("Deployment Drift Check — GitHub main vs Oracle running SHA")

    if not expected_sha:
        github_ref, dt, err = timed(
            lambda: httpx.get(f"https://api.github.com/repos/{GITHUB_REPO}/commits/main", timeout=10.0)
        )
        if err is not None or github_ref.status_code != 200:
            detail = f"{err}" if err is not None else f"HTTP {github_ref.status_code}: {github_ref.text[:200]}"
            result.add(
                "Resolve GitHub main SHA",
                Status.FAIL,
                f"Could not resolve main's HEAD from the GitHub API: {detail}. "
                "Pass the expected SHA explicitly (argv[1] or EXPECTED_SHA) if this keeps "
                "failing (e.g. unauthenticated GitHub API rate limiting).",
                dt,
            )
            return result
        expected_sha = github_ref.json()["sha"]
        result.add("Resolve GitHub main SHA", Status.PASS, f"main HEAD = {expected_sha}", dt)
    else:
        result.add("Expected SHA (provided)", Status.PASS, expected_sha)

    if not base_url:
        result.add(
            "Oracle base URL",
            Status.FAIL,
            "No ORACLE_BASE_URL / argv[2] provided -- cannot check a target that isn't named. "
            "Expected to FAIL until Oracle is reachable over HTTPS (Phase 6, deploy/Caddyfile) "
            "and its real URL is known.",
        )
        return result

    version_url = f"{base_url.rstrip('/')}/version"
    version_resp, dt, err = timed(lambda: httpx.get(version_url, timeout=10.0))
    if err is not None:
        result.add(
            "GET /version on Oracle",
            Status.FAIL,
            f"Could not reach {version_url}: {type(err).__name__}: {err}",
            dt,
        )
        return result
    if version_resp.status_code != 200:
        result.add("GET /version on Oracle", Status.FAIL, f"HTTP {version_resp.status_code}: {version_resp.text[:200]}", dt)
        return result

    body = version_resp.json()
    running_sha = body.get("commit", "unknown")
    result.add("GET /version on Oracle", Status.PASS, f"HTTP 200: {body}", dt)

    if running_sha == "unknown":
        result.add(
            "Oracle running SHA is known",
            Status.FAIL,
            "GIT_COMMIT_SHA build ARG was not set when this image was built -- "
            "see api/Dockerfile and deploy/oracle_deploy.sh.",
        )
    elif running_sha != expected_sha:
        result.add(
            "GitHub main SHA == Oracle running SHA",
            Status.FAIL,
            f"DEPLOYMENT DRIFT DETECTED: GitHub main is at {expected_sha}, "
            f"Oracle is running {running_sha}. Either Oracle has not yet redeployed this "
            "commit (check the oracle-deploy.yml workflow run for this SHA), or a manual "
            "deploy landed a different commit than main's current HEAD.",
        )
    else:
        result.add("GitHub main SHA == Oracle running SHA", Status.PASS, running_sha)

    return result


if __name__ == "__main__":
    exit_with(run(_resolve_expected_sha(sys.argv), _resolve_base_url(sys.argv)))
