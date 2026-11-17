"""In-process counters, logged as one JSON line per window (same approach as
lrb.core.cache.metrics). Labels are policy names only: never user ids or IPs,
which would explode metric cardinality. Events: allowed, rejected, penalty_blocked,
penalty_applied, concurrency_rejected, shadow_rejected, fallback_open,
fallback_closed, fallback_local, store_error, script_error, breaker_skip."""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger(__name__)
FLUSH_EVERY_EVENTS = 500
FLUSH_EVERY_SECONDS = 60.0

_lock = threading.Lock()
_total: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_window: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_events = 0
_started = time.monotonic()


def record(policy: str, event: str, n: int = 1) -> None:
    global _events, _started
    summary = None
    with _lock:
        _total[policy][event] += n
        _window[policy][event] += n
        _events += 1
        if _events >= FLUSH_EVERY_EVENTS or time.monotonic() - _started >= FLUSH_EVERY_SECONDS:
            summary = {k: dict(v) for k, v in _window.items()}
            _window.clear()
            _events = 0
            _started = time.monotonic()
    if summary:
        logger.info("ratelimit_metrics %s", json.dumps(summary, sort_keys=True))


def snapshot() -> dict[str, dict[str, int]]:
    with _lock:
        return {k: dict(v) for k, v in _total.items()}


def reset() -> None:
    global _events, _started
    with _lock:
        _total.clear(); _window.clear(); _events = 0; _started = time.monotonic()
