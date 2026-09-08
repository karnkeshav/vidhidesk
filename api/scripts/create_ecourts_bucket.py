"""One-off: provision the 'ecourts-documents' Supabase Storage bucket used
by app/services/court_sync.py::_cache_ecourts_file to cache eCourts order/
document files, avoiding repeat downloads from the live provider on every
view or test sync. Idempotent -- safe to re-run if the bucket already
exists (Supabase returns a 409, treated as success).

Run standalone: python scripts/create_ecourts_bucket.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import service_client  # noqa: E402

BUCKET_ID = "ecourts-documents"


def run() -> None:
    svc = service_client()
    try:
        svc.storage.create_bucket(BUCKET_ID, options={"public": True})
        print(f"Created bucket: {BUCKET_ID}")
    except Exception as exc:
        msg = str(exc)
        if "already exists" in msg.lower() or "duplicate" in msg.lower() or "409" in msg:
            print(f"Bucket already exists: {BUCKET_ID}")
        else:
            raise


if __name__ == "__main__":
    run()
