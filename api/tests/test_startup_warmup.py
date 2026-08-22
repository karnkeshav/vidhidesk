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


def test_both_loaders_run_concurrently_not_sequentially(monkeypatch):
    """Bounded wait only helps if the two loaders actually run in
    parallel -- if they still ran sequentially, a single slow loader would
    still consume the full timeout budget before the second one even
    starts. Two loaders that each sleep briefly must together take close
    to ONE sleep duration, not the sum of both."""
    monkeypatch.setattr(app_main, "_WARM_UP_TIMEOUT_S", 5.0)

    def _sleepy(tag):
        def _loader():
            time.sleep(0.4)
            return tag
        return _loader

    monkeypatch.setattr(app_main.pii_mask_service, "_get_nlp", _sleepy("a"))
    monkeypatch.setattr(app_main.retrieval_service, "_get_embedding_model", _sleepy("b"))

    t0 = time.monotonic()
    app_main._warm_up_ml_models()
    elapsed = time.monotonic() - t0

    assert elapsed < 0.8, f"two 0.4s loaders should overlap (~0.4s total), not sum to ~0.8s+; took {elapsed:.2f}s"
