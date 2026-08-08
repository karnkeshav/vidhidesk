"""Part 3 — Storage Verification (Sprint 3.5.5B).

Checks the REAL Supabase Storage for this project: bucket existence,
then — only for buckets that exist — a real upload followed by a real
download of a small, harmless test object, verifying the bytes round-trip
correctly, followed by cleanup (delete the test object). Never attempts
upload/download against a bucket that doesn't exist (that's just a
restated "the bucket is missing" finding, not a new one), and never
creates a missing bucket itself — provisioning a bucket is a real,
consequential action on shared infrastructure that this verification
script does not have standing to take unprompted; see TICKET-10 in
docs/30_Implementation/Backlog.md.

Run standalone: python scripts/verify_storage.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult, exit_with, timed  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

# Buckets referenced in application code:
#   api/app/routers/profile.py::upload_avatar   -> "avatars"
#   api/app/routers/litigation.py::upload_evidence -> "evidence"
EXPECTED_BUCKETS = ["avatars", "evidence"]

_TEST_OBJECT_PREFIX = "verify-storage-smoketest"
_TEST_CONTENT = b"VidhiDesk verify_storage.py smoke test object - safe to delete."


def run() -> VerificationResult:
    result = VerificationResult("Storage Verification (Part 3)")

    try:
        from app.db import service_client  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        result.add("Import app.db", Status.FAIL, f"{type(exc).__name__}: {exc}")
        return result

    svc = service_client()

    buckets, dt, err = timed(lambda: svc.storage.list_buckets())
    if err:
        result.add("List storage buckets", Status.FAIL, f"{type(err).__name__}: {err}", dt)
        return result

    bucket_names = {b.name if hasattr(b, "name") else b.get("name") for b in buckets}
    result.add("List storage buckets", Status.PASS, f"{len(bucket_names)} bucket(s) found: {sorted(bucket_names) or '(none)'}", dt)

    for bucket in EXPECTED_BUCKETS:
        if bucket not in bucket_names:
            result.add(f"Bucket exists: {bucket}", Status.FAIL, "Not provisioned — see TICKET-10")
            result.add(f"Upload round-trip: {bucket}", Status.SKIP, "Bucket does not exist — nothing to test")
            result.add(f"Download round-trip: {bucket}", Status.SKIP, "Bucket does not exist — nothing to test")
            result.add(f"Permissions: {bucket}", Status.SKIP, "Bucket does not exist — nothing to test")
            continue

        result.add(f"Bucket exists: {bucket}", Status.PASS, "Provisioned")

        # Real upload/download/delete round-trip against a disposable,
        # clearly-named test object — never touches real evidence/avatar data.
        object_path = f"{_TEST_OBJECT_PREFIX}/{uuid.uuid4()}.txt"

        _, dt, err = timed(
            lambda: svc.storage.from_(bucket).upload(
                path=object_path, file=_TEST_CONTENT, file_options={"content-type": "text/plain"}
            )
        )
        if err:
            result.add(f"Upload round-trip: {bucket}", Status.FAIL, f"{type(err).__name__}: {err}", dt)
            continue
        result.add(f"Upload round-trip: {bucket}", Status.PASS, f"Uploaded {len(_TEST_CONTENT)} bytes to {object_path}", dt)

        downloaded, dt, err = timed(lambda: svc.storage.from_(bucket).download(object_path))
        if err:
            result.add(f"Download round-trip: {bucket}", Status.FAIL, f"{type(err).__name__}: {err}", dt)
        elif downloaded != _TEST_CONTENT:
            result.add(f"Download round-trip: {bucket}", Status.FAIL, "Downloaded bytes do not match uploaded bytes", dt)
        else:
            result.add(f"Download round-trip: {bucket}", Status.PASS, "Downloaded bytes match exactly", dt)

        public_url, dt, err = timed(lambda: svc.storage.from_(bucket).get_public_url(object_path))
        if err:
            result.add(f"Permissions: {bucket}", Status.WARN, f"get_public_url failed: {type(err).__name__}: {err}", dt)
        else:
            result.add(f"Permissions: {bucket}", Status.PASS, f"Public URL resolvable: {public_url}", dt)

        _, dt, err = timed(lambda: svc.storage.from_(bucket).remove([object_path]))
        if err:
            result.add(f"Cleanup: {bucket}", Status.WARN, f"Test object left behind — manual cleanup needed for {object_path}: {err}", dt)
        else:
            result.add(f"Cleanup: {bucket}", Status.PASS, "Test object removed", dt)

    return result


if __name__ == "__main__":
    exit_with(run())
