#!/usr/bin/env bash
#
# DRAFT / UNVERIFIED (Oracle Migration Sprint, Phase 5). Authored without
# SSH/Docker access to a real Oracle VM to run this against -- dry-run it
# manually on the actual box before wiring it into
# .github/workflows/oracle-deploy.yml.
#
# Invariants this script exists to uphold (Oracle Migration Sprint rules):
#   - Oracle is a deployment TARGET, never an independent dev repo: always
#     `git fetch` + `git checkout --detach <SHA>`, never `git pull` -- a
#     `pull` on a detached-HEAD box can produce an ambiguous merge state
#     that this script is specifically designed to avoid.
#   - Every deploy is traceable to an exact SHA: baked into the image via
#     api/Dockerfile's GIT_COMMIT_SHA build ARG, surfaced at GET /version.
#   - A failed health check must never take down a working prod container
#     -- the old container is only stopped after the new one proves
#     itself healthy on a throwaway port, and is only removed after the
#     new one *also* proves itself healthy on the real port.
#
# Usage: oracle_deploy.sh <git-sha>
#
# Assumes: this script runs FROM an already-cloned checkout of this repo
# on the Oracle VM (default /opt/vidhidesk, override with
# VIDHIDESK_REPO_DIR), with Docker installed and the invoking user in the
# `docker` group (no sudo used here), and a repo-root .env file already
# present on the box -- created there directly, once, by hand. That .env
# is never committed to git and never copied by this script; it is read
# in place via `--env-file` at container start. See CLAUDE.md Hard Rule 6.

set -euo pipefail

SHA="${1:?Usage: oracle_deploy.sh <git-sha>}"
REPO_DIR="${VIDHIDESK_REPO_DIR:-/opt/vidhidesk}"
IMAGE_NAME="vidhidesk-api"
CONTAINER_NAME="vidhidesk-api"
CANDIDATE_PORT="${VIDHIDESK_CANDIDATE_PORT:-18000}"
PROD_PORT="${VIDHIDESK_PROD_PORT:-8000}"
DRAFTS_VOLUME="${VIDHIDESK_DRAFTS_VOLUME:-vidhidesk_generated_drafts}"
ENV_FILE="${REPO_DIR}/.env"
KEEP_IMAGES=5

cd "$REPO_DIR"

echo "==> Fetching origin (never pulling -- avoids ambiguous merge state on this box)"
git fetch origin

echo "==> Checking out detached at $SHA"
git checkout --detach "$SHA"

ACTUAL_SHA="$(git rev-parse HEAD)"
if [ "$ACTUAL_SHA" != "$SHA" ]; then
  echo "FATAL: requested $SHA but HEAD is $ACTUAL_SHA after checkout" >&2
  exit 1
fi

echo "==> Building image tagged ${IMAGE_NAME}:${SHA}"
docker build -f api/Dockerfile --build-arg GIT_COMMIT_SHA="$SHA" -t "${IMAGE_NAME}:${SHA}" .

CANDIDATE_CONTAINER="${CONTAINER_NAME}-candidate"
docker rm -f "$CANDIDATE_CONTAINER" >/dev/null 2>&1 || true

echo "==> Starting candidate container on throwaway port ${CANDIDATE_PORT} for health-gating"
docker run -d --name "$CANDIDATE_CONTAINER" \
  -p "127.0.0.1:${CANDIDATE_PORT}:8000" \
  -v "${DRAFTS_VOLUME}:/app/api/generated_drafts" \
  --env-file "$ENV_FILE" \
  "${IMAGE_NAME}:${SHA}"

echo "==> Waiting for candidate to report healthy"
HEALTHY=0
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${CANDIDATE_PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 3
done

if [ "$HEALTHY" -ne 1 ]; then
  echo "FATAL: candidate container never became healthy -- leaving existing prod container untouched" >&2
  docker logs "$CANDIDATE_CONTAINER" --tail 100 || true
  docker rm -f "$CANDIDATE_CONTAINER" >/dev/null 2>&1 || true
  exit 1
fi

echo "==> Candidate healthy. Verifying its own /version reports the requested SHA"
REPORTED_SHA="$(curl -fsS "http://127.0.0.1:${CANDIDATE_PORT}/version" | python3 -c 'import json,sys; print(json.load(sys.stdin)["commit"])')"
if [ "$REPORTED_SHA" != "$SHA" ]; then
  echo "FATAL: candidate /version reports commit=$REPORTED_SHA, expected $SHA -- refusing to promote" >&2
  docker rm -f "$CANDIDATE_CONTAINER" >/dev/null 2>&1 || true
  exit 1
fi

echo "==> Promoting: stopping old prod container (kept, not removed yet, for rollback) and swapping candidate in"
docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker rename "$CONTAINER_NAME" "${CONTAINER_NAME}-previous" >/dev/null 2>&1 || true

docker rm -f "$CANDIDATE_CONTAINER" >/dev/null 2>&1
docker run -d --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${PROD_PORT}:8000" \
  -v "${DRAFTS_VOLUME}:/app/api/generated_drafts" \
  --env-file "$ENV_FILE" \
  "${IMAGE_NAME}:${SHA}"

echo "==> Confirming promoted container is healthy on the real port"
sleep 3
if ! curl -fsS "http://127.0.0.1:${PROD_PORT}/health" >/dev/null 2>&1; then
  echo "FATAL: promoted container failed its own health check on the real port -- rolling back" >&2
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rename "${CONTAINER_NAME}-previous" "$CONTAINER_NAME" >/dev/null 2>&1
  docker start "$CONTAINER_NAME" >/dev/null 2>&1
  echo "==> Rolled back: previous container restarted" >&2
  exit 1
fi

echo "==> Removing the previous container (its image is kept for manual rollback -- see below)"
docker rm -f "${CONTAINER_NAME}-previous" >/dev/null 2>&1 || true

echo "==> Pruning old images, keeping the ${KEEP_IMAGES} most recent for rollback"
docker images "$IMAGE_NAME" --format '{{.Tag}} {{.CreatedAt}}' \
  | sort -k2 -r \
  | awk -v keep="$KEEP_IMAGES" 'NR>keep {print $1}' \
  | xargs -r -I{} docker rmi "${IMAGE_NAME}:{}" || true

echo "==> Deploy complete: ${IMAGE_NAME}:${SHA} is live on port ${PROD_PORT}"
echo "==> Manual rollback if ever needed later: docker rm -f ${CONTAINER_NAME} && docker run -d --name ${CONTAINER_NAME} --restart unless-stopped -p ${PROD_PORT}:8000 -v ${DRAFTS_VOLUME}:/app/api/generated_drafts --env-file ${ENV_FILE} ${IMAGE_NAME}:<previous-sha>"
