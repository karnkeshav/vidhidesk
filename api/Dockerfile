# Build context MUST be the repository root, not api/:
#   docker build -f api/Dockerfile .
#
# Why: api/app/services/contracts.py and api/app/routers/contracts.py both
# compute REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# (4 levels up from a file at api/app/services/<file>.py) and use it to
# locate templates/<...>.docx. That only resolves correctly if, inside the
# image, templates/ sits as a sibling of api/ at the same relative depth
# it has in the repo. This image preserves that layout under /app:
#   /app/api/app/services/contracts.py  -> 4 parents up -> /app
#   /app/templates                      (sibling of /app/api)
#   /app/corpus                         (sibling of /app/api, see note below)
#
# corpus/ is copied in because Phase 2B explicitly asked for it, but note:
# no runtime code path reads it (grep confirmed only the offline
# api/scripts/ingest_statutes.py script touches corpus/ PDFs — the live API
# reads already-ingested chunks from Supabase via app/services/retrieval.py).
# Also note corpus/*.pdf is .gitignored (only corpus/.gitkeep is tracked in
# git), so a build from a fresh `git clone` will copy an effectively empty
# corpus/ directory unless the PDFs are transferred separately.

FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (separate from the app-code COPY below) so
# `docker build` only re-runs pip install when requirements.txt actually
# changes, not on every code edit.
COPY api/requirements.txt /app/api/requirements.txt

# sentence-transformers pulls in an unpinned "torch", which PyPI's default
# index resolves to the CUDA build — installing 18 nvidia-*/cuda-* packages
# and triton on this GPU-less Oracle VM for no benefit (Phase 2C.1 measured
# this at ~2.5GB of unnecessary image weight and roughly 2.6x slower
# dependency installation). Installing the CPU-only wheel first, before the
# main requirements pass, satisfies sentence-transformers' unpinned "torch"
# requirement without ever touching the CUDA index — confirmed experimentally
# in Phase 2C.1: the subsequent requirements.txt install does not reinstall
# torch once this version is already present.
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Application code + the two runtime-relative asset directories it expects
# as siblings of api/ (see REPO_ROOT note above).
COPY api /app/api
COPY templates /app/templates
COPY corpus /app/corpus

# Runtime output directory for docxtpl-generated drafts
# (api/app/services/contracts.py: DRAFTS_DIR = .../api/generated_drafts).
# Created empty here — .dockerignore excludes any drafts already present
# in the build context. The eventual deployment should bind-mount/volume
# this path: /app/api/generated_drafts (NOT /app/generated_drafts — see
# Phase 2B report, the code path is 3 parents up from contracts.py, one
# level shallower than REPO_ROOT's 4).
RUN mkdir -p /app/api/generated_drafts

# app.main:app is a package inside api/, so uvicorn needs api/ as its
# working directory to resolve the "app" import.
WORKDIR /app/api

EXPOSE 8000

# No curl/wget in python:slim by default; avoid installing one just for
# this by using Python's own stdlib to hit the health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
