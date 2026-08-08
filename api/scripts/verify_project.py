"""Sprint 3.5.5B — Part 6: the single command a developer runs to know
whether VidhiDesk is actually healthy, end to end:

    python scripts/verify_project.py

This orchestrates every other verify_*.py module (each independently
runnable — see their own docstrings) plus the backend pytest suite, and
produces one consolidated report. The aggregation rule is fixed and
cannot be overridden by any individual section: if ANY section reports
FAIL, the overall status is FAIL. A WARN-only run still exits non-zero
(this is intentionally stricter than "just check the exit code is 0" —
see the summary table's own Status column, not just the final line, if
you need to distinguish "broken" from "needs attention"). There is no
code path that produces an overall PASS while a section underneath it
failed — see verify_common.VerificationResult.overall.

Sections that need a live server (verify_runtime.py) start their own
local `uvicorn` instance on an ephemeral port and tear it down when
done — nothing here talks to a production deployment unless you set
RUNTIME_VERIFY_BASE_URL yourself before running.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_common import Status, VerificationResult  # noqa: E402

import verify_environment  # noqa: E402
import verify_database  # noqa: E402
import verify_storage  # noqa: E402
import verify_llm_providers  # noqa: E402
import verify_migrations  # noqa: E402
import verify_runtime  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_runtime_check() -> VerificationResult:
    """Starts a local uvicorn instance, runs verify_runtime against it,
    always tears it down. If the server never comes up, reports FAIL
    with the real reason rather than silently skipping this section."""
    port = _free_port()
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--port", str(port)],
        cwd=str(API_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 15
        healthy = False
        last_err = None
        while time.time() < deadline:
            try:
                import httpx

                r = httpx.get(f"{base_url}/health", timeout=1.0)
                if r.status_code == 200:
                    healthy = True
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            time.sleep(0.5)

        if not healthy:
            result = VerificationResult("Runtime Verification (Part 1/7)")
            stderr = proc.stderr.read().decode(errors="replace")[-1000:] if proc.stderr else ""
            result.add(
                "Start local uvicorn instance for testing",
                Status.FAIL,
                f"Server did not become healthy within 15s. Last error: {last_err}. stderr tail: {stderr}",
            )
            return result

        return verify_runtime.run(base_url=base_url)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _run_pytest() -> tuple[Status, str]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=str(API_ROOT),
        capture_output=True,
        text=True,
    )
    dt = (time.perf_counter() - t0) * 1000
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "(no output)"
    status = Status.PASS if proc.returncode == 0 else Status.FAIL
    return status, f"{tail}  ({dt / 1000:.1f}s)"


def main() -> int:
    sections: list[VerificationResult] = []

    print("Running verify_environment.py ...")
    sections.append(verify_environment.run())

    print("Running verify_migrations.py (static file checks) ...")
    sections.append(verify_migrations.run())

    print("Running verify_database.py (live schema checks) ...")
    sections.append(verify_database.run())

    print("Running verify_storage.py ...")
    sections.append(verify_storage.run())

    print("Running verify_llm_providers.py ...")
    sections.append(verify_llm_providers.run())

    print("Running verify_runtime.py against a freshly-started local instance ...")
    sections.append(_run_runtime_check())

    print("Running backend pytest suite ...")
    test_status, test_detail = _run_pytest()

    for s in sections:
        s.print_report()

    # --- Consolidated Health Report (Part 6) --------------------------------
    print("\n" + "=" * 34)
    print("VIDHIDESK HEALTH REPORT")
    print("=" * 34 + "\n")

    name_map = {
        "Environment Verification (Part 5)": "Environment",
        "Migration File Verification (Part 2, static)": "Migrations (file hygiene)",
        "Database Verification (Part 2)": "Database (live schema)",
        "Storage Verification (Part 3)": "Storage",
        "LLM & Citation Provider Verification (Part 4)": "Providers",
    }

    overall_fail = False
    for s in sections:
        label = name_map.get(s.name, s.name)
        if s.name.startswith("Runtime Verification"):
            label = "Runtime"
        print(f"{label}\n{s.overall.value}\n")
        if s.overall == Status.FAIL:
            overall_fail = True

    print(f"Tests\n{test_detail}\n")
    if test_status == Status.FAIL:
        overall_fail = True

    validation_ready = not overall_fail
    print("Validation Ready")
    print("YES" if validation_ready else "NO")
    print("\n" + "=" * 34)

    if overall_fail:
        print("\nOVERALL STATUS: FAIL — see section reports above for exact evidence.")
    else:
        # Even an all-PASS run can still carry WARNs; say so rather than
        # implying a spotless result when there wasn't one.
        any_warn = any(s.overall == Status.WARN for s in sections)
        print(f"\nOVERALL STATUS: {'PASS WITH WARNINGS' if any_warn else 'PASS'} — see section reports above.")

    return 1 if overall_fail else 0


if __name__ == "__main__":
    sys.exit(main())
