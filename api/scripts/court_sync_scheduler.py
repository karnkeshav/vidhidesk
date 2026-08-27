"""eCourts sync scheduler entry point (Litigation Intelligence + eCourts,
27 Aug 2026). NOT a long-running process -- this is a single pass, meant
to be invoked periodically by an external scheduler (cron, GitHub Actions
schedule + SSH to the Oracle box, systemd timer, whatever the actual
deployment uses). This project has no in-process background-job
infrastructure (confirmed during the forensic review: no APScheduler/
Celery/queue anywhere in api/) and the smallest robust addition is a
script invoked externally, not a new always-running worker.

Run manually: `python scripts/court_sync_scheduler.py`
Configuration (all optional, see .env.example / app/config.py):
  ECOURTS_SYNC_START_HOUR / ECOURTS_SYNC_END_HOUR   -- local-hour window
  ECOURTS_SYNC_INTERVAL_MINUTES                      -- informational only
    here (a single pass does one sync round; the calling scheduler is
    responsible for actually spacing invocations this far apart -- this
    script does not sleep/loop internally, matching "do not add an
    uncontrolled polling process")
  ECOURTS_SYNC_LOOKAHEAD_DAYS                        -- only syncs matters
    whose court_case_tracking.next_hearing_date is within this many days
    (or unset/never-synced -- see _is_due below)

Idempotent and safe to invoke more often than configured: every sync
itself is idempotent (court_sync.sync_matter_court_data upserts, never
blindly inserts) and skipped/paused matters (tracking disabled, no CNR,
organization not active) raise CourtSyncSkipped rather than erroring.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone

from app.config import get_settings
from app.db import service_client
from app.services import court_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vidhidesk.court_sync_scheduler")


def _within_configured_hour_window(now: datetime, settings) -> bool:
    return settings.ecourts_sync_start_hour <= now.hour < settings.ecourts_sync_end_hour


def _is_due(tracking: dict, lookahead_days: int, today: date) -> bool:
    next_hearing = tracking.get("next_hearing_date")
    if not next_hearing:
        # No known next hearing yet -- worth an occasional sync to find
        # out if one has been listed. The caller's own invocation cadence
        # (external scheduler) bounds how often this actually happens;
        # this function doesn't rate-limit it further.
        return True
    try:
        hearing_date = date.fromisoformat(next_hearing)
    except ValueError:
        return True
    return (hearing_date - today).days <= lookahead_days


def run_once(*, force: bool = False) -> dict[str, int]:
    """One sync pass over every tracking-enabled matter due for a sync.
    `force=True` skips the hour-window check (used for manual/on-demand
    invocation, e.g. from a `--now` CLI flag) -- the per-matter org-access
    and tracking-enabled checks inside sync_matter_court_data still apply
    regardless."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if not force and not _within_configured_hour_window(now, settings):
        logger.info("court_sync_scheduler: outside configured sync window (%02d:00-%02d:00 UTC), skipping",
                    settings.ecourts_sync_start_hour, settings.ecourts_sync_end_hour)
        return {"synced": 0, "skipped": 0, "errors": 0}

    sc = service_client()
    all_tracking = court_sync.matters_due_for_sync(sc)
    due = [t for t in all_tracking if _is_due(t, settings.ecourts_sync_lookahead_days, now.date())]

    logger.info("court_sync_scheduler: %d tracking-enabled matter(s), %d due this pass", len(all_tracking), len(due))

    counts = {"synced": 0, "skipped": 0, "errors": 0}
    for tracking in due:
        matter_id = tracking["matter_id"]
        try:
            result = court_sync.sync_matter_court_data(matter_id, sc)
            counts["synced"] += 1
            logger.info("court_sync_scheduler: synced matter_id=%s hearing_created=%s", matter_id, result.get("hearing_created"))
        except court_sync.CourtSyncSkipped as exc:
            counts["skipped"] += 1
            logger.info("court_sync_scheduler: skipped matter_id=%s reason=%s", matter_id, exc)
        except Exception:
            counts["errors"] += 1
            logger.warning("court_sync_scheduler: sync failed for matter_id=%s", matter_id, exc_info=True)

    logger.info("court_sync_scheduler: pass complete synced=%d skipped=%d errors=%d", counts["synced"], counts["skipped"], counts["errors"])
    return counts


if __name__ == "__main__":
    force_run = "--now" in sys.argv
    run_once(force=force_run)
