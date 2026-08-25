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
# on the Oracle VM (default /home/ubuntu/vidhidesk -- verified against the
# real box; override with VIDHIDESK_REPO_DIR), with Docker installed and
# the invoking user in the `docker` group (no sudo used here -- as of the
# Oracle Migration Sprint's read-only audit, the `ubuntu` user is NOT yet
# in that group; see Phase 5 of that audit for the exact command to run
# manually before this script can work at all), and a repo-root .env file
# already present on the box -- created there directly, once, by hand.
# That .env is never committed to git and never copied by this script; it
# is read in place via `--env-file` at container start. See CLAUDE.md Hard
# Rule 6.

set -euo pipefail

SHA="${1:?Usage: oracle_deploy.sh <git-sha>}"
# Verified against the real Oracle box (Oracle Migration Sprint, read-only
# audit): the repo actually lives at /home/ubuntu/vidhidesk under the
# `ubuntu` user -- /opt/vidhidesk does not exist on this VM at all. Do not
# reintroduce that path; it would create exactly the "second repository
# location" this script's own invariants forbid.
REPO_DIR="${VIDHIDESK_REPO_DIR:-/home/ubuntu/vidhidesk}"
IMAGE_NAME="vidhidesk-api"
CONTAINER_NAME="vidhidesk-api"
CANDIDATE_PORT="${VIDHIDESK_CANDIDATE_PORT:-18000}"
PROD_PORT="${VIDHIDESK_PROD_PORT:-8000}"
DRAFTS_VOLUME="${VIDHIDESK_DRAFTS_VOLUME:-vidhidesk_generated_drafts}"
ENV_FILE="${REPO_DIR}/.env"
KEEP_IMAGES=5

# Deployment lock (Oracle Migration Sprint, hardening pass): protects the
# ENTIRE build/promote/rollback sequence below, not just the container
# swap -- a second deploy invocation must never manipulate containers
# while one is already in flight (two concurrent runs would race on the
# same container/image names, since nothing below is written to be safe
# under concurrent execution). This is a second, independent layer under
# the GitHub Actions `concurrency:` group in oracle-deploy.yml -- that
# stops a *stale* Actions job from starting a new SSH session in the
# first place, but does not by itself guarantee an already-dispatched SSH
# command on this box gets killed the moment its Actions job is
# cancelled. This lock is what actually enforces "only one deployment
# manipulates containers at a time" regardless of what happens on the
# Actions side.
#
# Chosen behavior: a BOUNDED WAIT (flock -w), not an immediate failure
# and not an unbounded wait. A brand-new invocation queues behind one
# already in progress (normal case: a second push landing while the
# first is still building/health-gating) and, once the lock frees up,
# proceeds -- so the box still converges to whichever SHA was requested
# most recently, rather than silently giving up. If the lock is still
# held after VIDHIDESK_LOCK_WAIT_SECONDS (default 10 minutes -- comfortably
# longer than a normal build+health-gate cycle), this invocation fails
# loudly rather than queuing forever behind a hung/crashed prior run;
# api/scripts/check_deployment_drift.py will then correctly report
# Oracle as stale until a human investigates the stuck lock holder.
LOCK_FILE="${VIDHIDESK_LOCK_FILE:-${REPO_DIR}/.deploy.lock}"
LOCK_WAIT_SECONDS="${VIDHIDESK_LOCK_WAIT_SECONDS:-600}"

exec 200>"$LOCK_FILE"
echo "==> Acquiring deployment lock ($LOCK_FILE, waiting up to ${LOCK_WAIT_SECONDS}s for any in-progress deployment)"
if ! flock -w "$LOCK_WAIT_SECONDS" 200; then
  echo "FATAL: could not acquire deployment lock within ${LOCK_WAIT_SECONDS}s -- another deployment appears to be running (or stuck holding $LOCK_FILE). Refusing to start a concurrent deployment." >&2
  exit 1
fi
echo "==> Lock acquired -- no other deployment is in progress. Proceeding with $SHA"

cd "$REPO_DIR"

echo "==> Fetching origin (never pulling -- avoids ambiguous merge state on this box)"
git fetch origin

echo "==> Verifying $SHA exists in fetched history before touching anything"
if ! git cat-file -e "${SHA}^{commit}" 2>/dev/null; then
  echo "FATAL: $SHA does not exist in this repository's history after fetch -- refusing to deploy an unknown/unreachable commit" >&2
  exit 1
fi

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

# Hardening (Oracle Migration Sprint): the old container above is already
# stopped/renamed to -previous at this point, so if THIS docker run fails
# outright -- not "starts but unhealthy," but fails to start at all (bad
# port bind, disk full, daemon hiccup) -- `set -e` would otherwise abort
# the script right here and leave zero vidhidesk-api containers running.
# Wrapping it in `if ! ...; then` keeps it inside a tested conditional,
# which bash's `set -e` does not treat as a script-ending failure, so the
# explicit rollback below actually gets to run instead of being skipped.
if ! docker run -d --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${PROD_PORT}:8000" \
  -v "${DRAFTS_VOLUME}:/app/api/generated_drafts" \
  --env-file "$ENV_FILE" \
  "${IMAGE_NAME}:${SHA}"; then
  echo "FATAL: docker run failed to start the new production container at all (not merely unhealthy) -- restoring previous container" >&2
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rename "${CONTAINER_NAME}-previous" "$CONTAINER_NAME" >/dev/null 2>&1
  docker start "$CONTAINER_NAME" >/dev/null 2>&1
  sleep 3
  if curl -fsS "http://127.0.0.1:${PROD_PORT}/health" >/dev/null 2>&1; then
    echo "==> Rolled back: previous container restarted and confirmed healthy" >&2
  else
    echo "FATAL: previous container was restarted but is NOT passing its own health check -- VidhiDesk may be down, manual intervention required on the box" >&2
  fi
  exit 1
fi

echo "==> Confirming promoted container is healthy on the real port"
sleep 3
if ! curl -fsS "http://127.0.0.1:${PROD_PORT}/health" >/dev/null 2>&1; then
  echo "FATAL: promoted container failed its own health check on the real port -- rolling back" >&2
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rename "${CONTAINER_NAME}-previous" "$CONTAINER_NAME" >/dev/null 2>&1
  docker start "$CONTAINER_NAME" >/dev/null 2>&1
  sleep 3
  if curl -fsS "http://127.0.0.1:${PROD_PORT}/health" >/dev/null 2>&1; then
    echo "==> Rolled back: previous container restarted and confirmed healthy" >&2
  else
    echo "FATAL: previous container was restarted but is NOT passing its own health check -- VidhiDesk may be down, manual intervention required on the box" >&2
  fi
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
