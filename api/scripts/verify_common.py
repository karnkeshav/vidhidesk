"""Shared helpers for the scripts/verify_*.py infrastructure verification
framework (Sprint 3.5.5B). Every verify_*.py script runs real checks
against real infrastructure — no mocks, no simulated results, no
estimated numbers. A check that cannot be performed with the credentials
currently configured is reported as SKIP with the reason, never silently
omitted and never reported as PASS.

See docs/40_Operations/Infrastructure_Verification.md for how these
compose into `python scripts/verify_project.py`.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


_ICON = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "SKIP": "⏭️ "}


@dataclass
class Check:
    label: str
    status: Status
    detail: str = ""
    latency_ms: float | None = None


@dataclass
class VerificationResult:
    """One verify_*.py module's full set of checks. `overall` is derived,
    never set directly, so a script cannot accidentally report PASS while
    holding a FAIL check — this is the mechanism behind "never produce a
    false PASS": the aggregation rule lives in one place, not repeated
    (and potentially gotten wrong) in every script."""

    name: str
    checks: list[Check] = field(default_factory=list)

    def add(self, label: str, status: Status, detail: str = "", latency_ms: float | None = None) -> None:
        self.checks.append(Check(label, status, detail, latency_ms))

    @property
    def overall(self) -> Status:
        if any(c.status == Status.FAIL for c in self.checks):
            return Status.FAIL
        if any(c.status == Status.WARN for c in self.checks):
            return Status.WARN
        if all(c.status == Status.SKIP for c in self.checks) and self.checks:
            return Status.SKIP
        return Status.PASS

    def print_report(self) -> None:
        print(f"\n{'=' * 72}\n{self.name}\n{'=' * 72}")
        for c in self.checks:
            icon = _ICON[c.status.value]
            lat = f"  ({c.latency_ms:.1f}ms)" if c.latency_ms is not None else ""
            print(f"  {icon} {c.status.value:<5} {c.label}{lat}")
            if c.detail:
                for line in c.detail.splitlines():
                    print(f"           {line}")
        print(f"\n  Overall: {self.overall.value}")


def timed(fn):
    """Runs fn(), returns (value, elapsed_ms, exception_or_None). Never
    raises — the caller decides how a real exception becomes a FAIL check,
    with the real error message attached, not a generic failure."""
    t0 = time.perf_counter()
    try:
        value = fn()
        return value, (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure is a real, reportable finding
        return None, (time.perf_counter() - t0) * 1000, exc


def exit_with(result: VerificationResult) -> None:
    result.print_report()
    sys.exit(0 if result.overall in (Status.PASS, Status.SKIP) else 1)
