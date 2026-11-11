"""Circuit breaker for the cache connection.

Without it, a dead Redis costs every cache call a full socket timeout (1 s),
so one request that makes four cache calls takes four seconds longer. After
`failure_threshold` failures in a row the breaker OPENS: cache calls return
instantly as misses and the app talks only to the database. After `cooldown`
seconds ONE call is let through as a probe (HALF_OPEN). If it works, the
breaker closes again; if not, it re-opens.

State is per process. That is intentional: each worker learns for itself.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> str:
        return self._state

    def allow(self) -> bool:
        with self._lock:
            if self._state == CLOSED:
                return True
            if self._state == OPEN:
                if self._clock() - self._opened_at < self._cooldown:
                    return False
                self._state = HALF_OPEN
                self._probe_in_flight = True
                logger.warning("cache circuit HALF_OPEN: sending one probe to Redis")
                return True
            # HALF_OPEN: exactly one probe at a time
            if self._probe_in_flight:
                return False
            self._probe_in_flight = True
            return True

    def record_success(self) -> None:
        with self._lock:
            if self._state == HALF_OPEN:
                logger.info("cache circuit CLOSED: Redis is back")
            self._state = CLOSED
            self._failures = 0
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._probe_in_flight = False
            if self._state == HALF_OPEN:
                self._open_locked("probe failed")
                return
            self._failures += 1
            if self._state == CLOSED and self._failures >= self._threshold:
                self._open_locked(f"{self._failures} consecutive failures")

    def abort_probe(self) -> None:
        """A non-Redis error (e.g. an unserializable value) ended a probe: free the slot."""
        with self._lock:
            self._probe_in_flight = False

    def reset(self) -> None:
        with self._lock:
            self._state = CLOSED
            self._failures = 0
            self._probe_in_flight = False

    def _open_locked(self, reason: str) -> None:
        self._state = OPEN
        self._opened_at = self._clock()
        logger.error(
            "cache circuit OPEN (%s): skipping Redis for %.0fs, serving from the database",
            reason,
            self._cooldown,
        )


breaker = CircuitBreaker()



# The big picture: What problem does this solve?
# Imagine your app has a cache (Redis) that it talks to before hitting the database. The cache is usually fast — like a shortcut. But what if Redis dies?

# Every time your app asks Redis something, it waits for a reply. If Redis is dead, it waits... and waits... until a timeout (about 1 second). Then it gives up.

# Now imagine one request that makes 4 cache calls. Each one times out after 1 second. That request now takes 4 extra seconds. Bad!

# Multiply that by hundreds of requests. Your app grinds to a halt — not because your app is broken, but because it keeps waiting on a dead Redis.

# The solution: a circuit breaker
# Think of the circuit breaker in your house. When there's a short circuit, it flips off and stops electricity from flowing — protecting the house from fire. Later, you flip it back on to see if the problem is fixed.

# This code does the same thing for your cache:

# After 5 failures in a row, it "flips off" (state = OPEN).

# While OPEN, cache calls return instantly as "misses" — no waiting. The app just uses the database.

# After 10 seconds, it lets one call through as a test (state = HALF_OPEN).

# If that test works, it "flips back on" (state = CLOSED).

# If the test fails, it flips off again for another 10 seconds.

# Result: Instead of every request waiting 1 second on a dead Redis, requests are instant. The app stays fast.

# The three states
# State	Meaning	What happens to cache calls
# CLOSED	Normal. Redis is working.	All calls go through.
# OPEN	Redis is dead. We gave up.	Calls return instantly as misses — no waiting.
# HALF_OPEN	Testing if Redis is back.	One call is let through as a probe. Others return instantly.
# Think of it like a door:

# CLOSED = door open, everyone walks through.

# OPEN = door shut, nobody gets in (but they don't wait — they just turn around instantly).

# HALF_OPEN = door cracked open, one person goes in to check if it's safe.

# Reading the code piece by piece
# The constants
# python
# CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"
# These are just three names for the three states. Instead of writing "closed" everywhere (and risking typos), we use CLOSED. If you mistype CLOSED, Python will error — if you mistype "clsoed", it silently does the wrong thing. So using constants is safer.

# The __init__ — setting up the breaker
# python
# def __init__(
#     self,
#     *,
#     failure_threshold: int = 5,
#     cooldown: float = 10.0,
#     clock: Callable[[], float] = time.monotonic,
# ) -> None:
# This runs once when you create a CircuitBreaker. It's the "setup" step.

# Parameter	Meaning	Default
# failure_threshold	How many failures in a row before we OPEN	5
# cooldown	How many seconds to wait before testing again	10.0
# clock	A function that returns the current time	time.monotonic
# Why the *? Same as before — everything after must be passed by name. So you write CircuitBreaker(failure_threshold=10) — clear and explicit.

# Why inject clock? This is a testing trick. In real life, clock is time.monotonic (a real clock). In a test, you can pass a fake clock that you control:

# python
# fake_time = [0.0]
# def fake_clock():
#     return fake_time[0]

# breaker = CircuitBreaker(clock=fake_clock)
# # ... cause failures ...
# fake_time[0] = 15.0   # jump forward 15 seconds — now cooldown has passed
# You can fast-forward time in tests without actually sleeping. Brilliant.

# What is time.monotonic? It's a clock that only moves forward — never goes backward. Unlike time.time() (which can jump backward if the system clock is adjusted), monotonic is perfect for measuring durations. If you measure "10 seconds have passed," that's always true.

# The internal state
# python
# self._threshold = failure_threshold
# self._cooldown = cooldown
# self._clock = clock
# self._lock = threading.Lock()
# self._state = CLOSED
# self._failures = 0
# self._opened_at = 0.0
# self._probe_in_flight = False
# These are the variables the breaker remembers:

# Variable	What it remembers
# _threshold	The failure limit (5)
# _cooldown	The wait time (10s)
# _clock	The time function
# _lock	A lock — explained below
# _state	Current state (starts CLOSED)
# _failures	How many failures in a row (starts 0)
# _opened_at	When we opened (timestamp)
# _probe_in_flight	Is a test call currently running?
# What is _lock? A lock prevents two threads from changing the state at the same time. Imagine two people trying to write on the same piece of paper at once — chaos. The lock says: "Only one thread at a time can do this."

# Every method that reads or changes state does with self._lock: — that means "grab the lock, do my work, release the lock." This makes the breaker thread-safe — safe to use from multiple threads at once.

# allow() — "Should I let this cache call through?"
# python
# def allow(self) -> bool:
#     with self._lock:
#         if self._state == CLOSED:
#             return True
#         if self._state == OPEN:
#             if self._clock() - self._opened_at < self._cooldown:
#                 return False
#             self._state = HALF_OPEN
#             self._probe_in_flight = True
#             logger.warning("cache circuit HALF_OPEN: sending one probe to Redis")
#             return True
#         # HALF_OPEN: exactly one probe at a time
#         if self._probe_in_flight:
#             return False
#         self._probe_in_flight = True
#         return True
# This is the gatekeeper. Every cache call first asks: allow(). It returns True (go ahead) or False (skip the cache — return a miss instantly).

# Let's walk through each state:

# If CLOSED (normal)
# python
# if self._state == CLOSED:
#     return True
# "We're healthy — let the call through." Simple.

# If OPEN (we gave up on Redis)
# python
# if self._clock() - self._opened_at < self._cooldown:
#     return False
# self._clock() - self._opened_at = how many seconds since we opened.

# If that's less than the cooldown (10 seconds), return False — "still too soon, don't try."

# python
# self._state = HALF_OPEN
# self._probe_in_flight = True
# logger.warning("cache circuit HALF_OPEN: sending one probe to Redis")
# return True
# If the cooldown has passed, we switch to HALF_OPEN and let one call through as a probe (a test). We mark _probe_in_flight = True so no other call sneaks through.

# If HALF_OPEN (we're testing)
# python
# if self._probe_in_flight:
#     return False
# self._probe_in_flight = True
# return True
# "A probe is already running — don't send another. Let it finish first."

# If no probe is running, start one and let this call through.

# Why only one probe? Imagine 100 requests all trying to test Redis at once. If Redis is still dead, you'd have 100 timeouts — the same problem you're trying to avoid! One probe at a time keeps the damage contained.

# record_success() — "The cache call worked"
# python
# def record_success(self) -> None:
#     with self._lock:
#         if self._state == HALF_OPEN:
#             logger.info("cache circuit CLOSED: Redis is back")
#         self._state = CLOSED
#         self._failures = 0
#         self._probe_in_flight = False
# When a cache call succeeds, the caller tells the breaker: "That worked."

# What happens:

# If we were HALF_OPEN, it means the probe worked — Redis is back! Log it.

# Set state to CLOSED (back to normal).

# Reset the failure counter to 0.

# Clear the probe flag.

# So one success fully heals the breaker.

# record_failure() — "The cache call failed"
# python
# def record_failure(self) -> None:
#     with self._lock:
#         self._probe_in_flight = False
#         if self._state == HALF_OPEN:
#             self._open_locked("probe failed")
#             return
#         self._failures += 1
#         if self._state == CLOSED and self._failures >= self._threshold:
#             self._open_locked(f"{self._failures} consecutive failures")
# When a cache call fails (timeout, connection refused), the caller tells the breaker.

# Clear the probe flag (a probe is no longer running).

# If we were HALF_OPEN: the probe failed → re-OPEN immediately. Don't bother counting — one failure in HALF_OPEN is enough.

# Otherwise (we're CLOSED): increment the failure count.

# If we're still CLOSED and the count has reached 5, OPEN the breaker.

# So 5 failures in a row = OPEN. But 1 success resets the count to zero. This means it's really "5 failures without an intervening success."

# abort_probe() — "Something else went wrong"
# python
# def abort_probe(self) -> None:
#     """A non-Redis error (e.g. an unserializable value) ended a probe: free the slot."""
#     with self._lock:
#         self._probe_in_flight = False
# This handles a special case. Imagine the probe call is let through, but then the code fails for a reason unrelated to Redis — like trying to cache a value that can't be serialized.

# You don't want to blame Redis for that. But you do want to release the probe slot, or else no future probe can ever run (because _probe_in_flight stays True forever — a stuck flag).

# So abort_probe() just clears the flag without counting a failure or changing state.

# Method	When called	Changes state?
# record_success()	Cache call worked	Yes → CLOSED
# record_failure()	Cache call failed (Redis problem)	Maybe → OPEN
# abort_probe()	Non-Redis error	No — just frees the slot
# reset() — "Force back to normal"
# python
# def reset(self) -> None:
#     with self._lock:
#         self._state = CLOSED
#         self._failures = 0
#         self._probe_in_flight = False
# Manually put the breaker back to CLOSED. Useful for tests or admin tools ("I fixed Redis, reset the breaker now").

# _open_locked() — the helper that opens the breaker
# python
# def _open_locked(self, reason: str) -> None:
#     self._state = OPEN
#     self._opened_at = self._clock()
#     logger.error(
#         "cache circuit OPEN (%s): skipping Redis for %.0fs, serving from the database",
#         reason,
#         self._cooldown,
#     )
# A helper used by record_failure(). It:

# Sets state to OPEN.

# Remembers when we opened (self._opened_at) — needed to know when the cooldown has passed.

# Logs an error with the reason.

# Why _locked in the name? It's a reminder: "This method assumes the caller already holds the lock." Calling it without the lock would be a bug. The name is a safety hint for the programmer.

# The global instance
# python
# breaker = CircuitBreaker()
# At the bottom of the file, one global breaker is created with default settings (5 failures, 10s cooldown). Everything else in the app imports and uses this one shared instance:

# python
# from mymodule import breaker

# if breaker.allow():
#     try:
#         value = redis.get(key)
#         breaker.record_success()
#     except RedisError:
#         breaker.record_failure()
#         value = None
# The whole thing in a story
# Let's trace what happens when Redis dies:

# Time	Event	State	What happens
# 0s	Request 1 calls allow()	CLOSED	True → call goes to Redis → fails → record_failure() → failures=1
# 0s	Request 2 calls allow()	CLOSED	True → fails → failures=2
# ...	(3 more failures)	...	...
# 0s	Request 5 fails	CLOSED → OPEN	failures=5 → _open_locked() → OPEN at t=0
# 1s	Request 6 calls allow()	OPEN	False — instant miss. No waiting. ✅
# 5s	Request 50 calls allow()	OPEN	False — instant.
# 10s	Request 100 calls allow()	OPEN → HALF_OPEN	Cooldown passed → one probe allowed
# 10s	Request 101 calls allow()	HALF_OPEN	False — probe already in flight
# 10.1s	Probe fails	HALF_OPEN → OPEN	_open_locked("probe failed") → OPEN again at t=10.1
# 20.1s	Next call after cooldown	OPEN → HALF_OPEN	Second probe sent
# 20.2s	Probe succeeds	HALF_OPEN → CLOSED	record_success() → back to normal ✅
# Notice: during the 10-second OPEN window, every request is instant — no waiting, no timeouts. The app stays fast while Redis is down.

# Why "state is per process"
# The docstring says:

# "State is per process. That is intentional: each worker learns for itself."

# If your app runs 4 worker processes (common with Gunicorn, uWSGI), each one has its own breaker object. They don't share state.

# Why? Because sharing state would require another network call (to a database or a shared store) — which would defeat the purpose. The whole point is to be fast and local. If worker A learns "Redis is dead," worker B will learn it too — after its own 5 failures. That's fine. Each worker's 5 failures take milliseconds (they're all timing out at once anyway).

# Summary table
# Piece	Meaning in plain English
# CLOSED, OPEN, HALF_OPEN	The three states — normal, broken, testing
# failure_threshold=5	Open after 5 failures in a row
# cooldown=10.0	Wait 10 seconds before testing again
# clock=time.monotonic	Injectable clock — makes it testable
# threading.Lock()	Prevents two threads from changing state at once
# allow()	The gatekeeper — should this call go to Redis?
# record_success()	"That worked" → close the breaker
# record_failure()	"That failed" → maybe open the breaker
# abort_probe()	"Something non-Redis went wrong" → just free the probe slot
# reset()	"Force back to normal"
# _open_locked()	Helper: switch to OPEN and remember when
# breaker = CircuitBreaker()	The one shared instance everyone uses
# One-line summary
# A circuit breaker watches for repeated cache failures. After 5 in a row, it stops calling Redis entirely — so requests return instantly instead of waiting 1 second each. After 10 seconds it lets one call through to test; if it works, we're back to normal; if not, we wait another 10 seconds. It's a safety valve that keeps your app fast when Redis is down.

# Would you like me to show you how this breaker would be used inside a real cache function — like the get() method that calls allow(), then record_success() or record_failure() — so you can see the full loop in action?

