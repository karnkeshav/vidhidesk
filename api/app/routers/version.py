"""GET /version — answers "what commit is actually running here", without
guessing from Git history or deploy metadata (Oracle Migration Sprint).

The commit SHA is injected at Docker build time (see api/Dockerfile's
GIT_COMMIT_SHA build ARG) and baked into the image as an environment
variable -- it is never hardcoded in source, and never read from `.git`
inside the running container (the image intentionally does not include
`.git` at all; only `api/`, `templates/`, `corpus/` are copied in, per the
Dockerfile's own comments). A local `uvicorn` run with no such env var set
reports "unknown" rather than fabricating a plausible-looking value.

Never returns anything beyond service name / commit / build id / a
human-set environment label -- no env vars, secrets, or credentials.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["version"])


@router.get("/version")
def version() -> dict[str, str]:
    return {
        "service": "vidhidesk-api",
        "commit": os.environ.get("GIT_COMMIT_SHA", "unknown"),
        "build": os.environ.get("BUILD_ID", "unknown"),
        "environment": os.environ.get("VIDHIDESK_ENVIRONMENT", "unknown"),
    }
