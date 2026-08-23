"""RERA Phase 2A: bounded-wait ML model warm-up at FastAPI startup.

Root cause under test (see app/main.py's _warm_up_ml_models docstring):
RERA Phase 1's live investigation found the pre-existing synchronous,
unbounded warm-up (spaCy + sentence-transformers, added 2026-08-18) could
block ALL routes -- not just RERA's -- for several minutes on a cold
machine when the embedding model's HuggingFace Hub freshness check was
slow. These tests verify the bounded-wait fix without waiting anywhere
near real model-load durations: every loader here is a fast fake.
"""
from __future__ import annotations

import logging
import threading
import time

import pytest

from app import main as app_main


def _immediate_loader():
    return "ok"


def _slow_loader(started: threading.Event, release: threading.Event):
    def _loader():
        started.set()
        release.wait(timeout=5.0)  # released explicitly by the test, or times out safely
        return "ok-but-slow"
    return _loader


def _raising_loader():
    raise RuntimeError("simulated model load failure")


def test_fast_loaders_complete_without_hitting_the_timeout(monkeypatch):
    monkeypatch.setattr(app_main, "_WARM_UP_TIMEOUT_S", 5.0)
    monkeypatch.setattr(app_main.pii_mask_service, "_get_nlp", _immediate_loader)
    monkeypatch.setattr(app_main.retrieval_service, "_get_embedding_model", _immediate_loader)

    t0 = time.monotonic()
    app_main._warm_up_ml_models()
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"fast loaders should not take anywhere near the timeout, took {elapsed:.2f}s"


def test_slow_loader_does_not_block_startup_past_the_timeout(monkeypatch, caplog):
    """The core Phase 2A fix: a loader slower than _WARM_UP_TIMEOUT_S must
    not make _warm_up_ml_models() itself block that long -- it returns at
    the cap and logs a warning, exactly the behavior that turns an
    unbounded multi-minute hang into a small, fixed ceiling."""
    monkeypatch.setattr(app_main, "_WARM_UP_TIMEOUT_S", 0.3)
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(app_main.pii_mask_service, "_get_nlp", _immediate_loader)
    monkeypatch.setattr(app_main.retrieval_service, "_get_embedding_model", _slow_loader(started, release))

    t0 = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="vidhidesk.startup"):
        app_main._warm_up_ml_models()
    elapsed = time.monotonic() - t0

    assert started.is_set(), "the slow loader should have actually started running"
    assert elapsed < 2.0, f"startup should return near the 0.3s cap, not wait for the slow loader, took {elapsed:.2f}s"
    assert any("warm_up_still_running" in r.message for r in caplog.records), (
        "expected a warm_up_still_running warning for the loader that didn't finish in time"
    )
    release.set()  # let the background thread finish cleanly rather than leaking past the test


def test_raising_loader_is_caught_and_logged_not_propagated(monkeypatch, caplog):
    """Preserves the pre-existing (2026-08-18) fallback semantics: a
    warm-up failure must never crash startup, and the model is still
    available via the ordinary lazy-load path on first real use."""
    monkeypatch.setattr(app_main, "_WARM_UP_TIMEOUT_S", 5.0)
    monkeypatch.setattr(app_main.pii_mask_service, "_get_nlp", _raising_loader)
    monkeypatch.setattr(app_main.retrieval_service, "_get_embedding_model", _immediate_loader)

    with caplog.at_level(logging.ERROR, logger="vidhidesk.startup"):
        app_main._warm_up_ml_models()  # must not raise

    assert any("warm_up_failed" in r.message and "spacy_pii_model" in r.message for r in caplog.records)


def test_loaders_run_sequentially_not_concurrently(monkeypatch):
    """RERA Phase 2J regression: Phase 2A's original design (max_workers=2,
    both loaders in flight at once) OOM-killed the Render free-tier
    instance (512Mi) on every boot -- live-confirmed via Render's events
    API (oomKilled, exit 137, repeating ~every 2 minutes) the first time
    this code was actually deployed. Serializing the two loads
    (max_workers=1) keeps peak memory to one model's load spike at a
    time; total resident memory once both are loaded is unchanged, only
    the peak during loading is. This asserts the two loaders never have
    overlapping execution windows."""
    monkeypatch.setattr(app_main, "_WARM_UP_TIMEOUT_S", 5.0)

    a_running = threading.Event()
    b_running = threading.Event()
    overlap = threading.Event()

    def _loader_a():
        a_running.set()
        time.sleep(0.2)
        if b_running.is_set():
            overlap.set()
        a_running.clear()
        return "a"

    def _loader_b():
        b_running.set()
        if a_running.is_set():
            overlap.set()
        time.sleep(0.2)
        b_running.clear()
        return "b"

    monkeypatch.setattr(app_main.pii_mask_service, "_get_nlp", _loader_a)
    monkeypatch.setattr(app_main.retrieval_service, "_get_embedding_model", _loader_b)

    t0 = time.monotonic()
    app_main._warm_up_ml_models()
    elapsed = time.monotonic() - t0

    assert not overlap.is_set(), "loaders must not run concurrently -- concurrent loading OOM-killed the free-tier instance in production"
    assert elapsed >= 0.4, f"two 0.2s loaders should sum to ~0.4s when sequential, not overlap; took {elapsed:.2f}s"
