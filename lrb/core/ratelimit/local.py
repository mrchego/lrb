"""Emergency per-process limiter, used only while Redis is unavailable.

Not globally accurate: with N workers the real limit is up to N x higher. It exists
so an outage does not mean "no protection", never to replace Redis. Memory is bounded
(least-recently-used keys are dropped), so it cannot be used to exhaust RAM.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict

MAX_KEYS = 20_000


class LocalBuckets:
    def __init__(self, max_keys: int = MAX_KEYS, clock=time.monotonic):
        self._max = max_keys
        self._clock = clock
        self._lock = threading.Lock()
        self._data: OrderedDict[str, list[float]] = OrderedDict()

    def check(self, items: list[tuple[str, float, float, float]]) -> tuple[bool, float]:
        """items = [(key, capacity, refill_per_second, cost)]. All-or-nothing.
        Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            state, worst, ok = [], 0.0, True
            for key, cap, rate, cost in items:
                tokens, ts = self._data.get(key, (cap, now))
                tokens = min(cap, tokens + (now - ts) * rate)
                if tokens < cost:
                    ok = False
                    worst = max(worst, (cost - tokens) / rate)
                state.append((key, tokens, cost))
            if ok:
                for key, tokens, cost in state:
                    self._data[key] = [tokens - cost, now]
                    self._data.move_to_end(key)
                while len(self._data) > self._max:
                    self._data.popitem(last=False)
            return ok, worst

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


local_buckets = LocalBuckets()
