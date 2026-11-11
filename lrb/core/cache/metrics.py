"""Cheap in-process cache counters, logged as one JSON line per window.

Each worker keeps its own counters and logs a summary every FLUSH_EVERY_EVENTS
events or FLUSH_EVERY_SECONDS seconds, whichever comes first. Your log pipeline
adds the workers together; no extra Redis traffic is needed.

Events per policy: hit, stale_hit, negative_hit, miss, bypass, loaded, load_ms,
lock_wait_timeout, refresh_enqueued, refresh_skipped, refresh_enqueue_failed,
refresh_ok, refresh_failed. Scope "_cache": error, breaker_skip.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

FLUSH_EVERY_EVENTS = 500
FLUSH_EVERY_SECONDS = 60.0
_LOOKUP_HITS = ("hit", "stale_hit", "negative_hit")

_clock = time.monotonic
_lock = threading.Lock()
_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_window: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_window_events = 0
_window_started = _clock()


def record(scope: str, event: str, n: int = 1) -> None:
    global _window_events, _window_started
    summary = None
    with _lock:
        _total[scope][event] += n
        _window[scope][event] += n
        _window_events += 1
        if _window_events >= FLUSH_EVERY_EVENTS or _clock() - _window_started >= FLUSH_EVERY_SECONDS:
            summary = _drain_window_locked()
            _window_started = _clock()
    if summary:
        logger.info("cache_metrics %s", json.dumps(summary, sort_keys=True))


def _drain_window_locked() -> dict[str, dict[str, float]]:
    global _window_events
    out: dict[str, dict[str, float]] = {}
    for scope, events in _window.items():
        row: dict[str, float] = dict(events)
        hits = sum(events.get(e, 0) for e in _LOOKUP_HITS)
        lookups = hits + events.get("miss", 0)
        if lookups:
            row["hit_ratio"] = round(hits / lookups, 3)
        out[scope] = row
    _window.clear()
    _window_events = 0
    return out


def snapshot() -> dict[str, dict[str, int]]:
    """Cumulative counters for this process (handy in a Django shell or a test)."""
    with _lock:
        return {scope: dict(events) for scope, events in _total.items()}


def reset() -> None:
    global _window_events, _window_started
    with _lock:
        _total.clear()
        _window.clear()
        _window_events = 0
        _window_started = _clock()
