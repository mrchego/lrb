"""Thin, failure-tolerant wrappers around Django's cache.

A cache is an optimisation, never a source of truth. If Redis is slow or down:
  * a read becomes a MISS (the caller falls back to the database);
  * a write is skipped;
  * a delete reports failure so the caller can log it loudly;
  * a lock reports "acquired" (fail-open: go to the database, never hang).
Only connection-type errors are swallowed. A serialization bug (TypeError)
still raises, because hiding it would silently disable caching.

Every call goes through the circuit breaker (see breaker.py), so a dead Redis
costs one probe every few seconds instead of a timeout on every call.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, TypeVar

from django.core.cache import cache
from redis.exceptions import RedisError

from lrb.core.cache import metrics
from lrb.core.cache.breaker import breaker

logger = logging.getLogger(__name__)

_CACHE_DOWN = (RedisError, OSError)
_SCOPE = "_cache"
T = TypeVar("T")


def _call(fn: Callable[[], T], *, default: T | None) -> tuple[T | None, bool]:
    """Run one cache operation. Returns (result, reached_redis)."""
    if not breaker.allow():
        metrics.record(_SCOPE, "breaker_skip")
        return default, False
    try:
        result = fn()
    except _CACHE_DOWN as exc:
        breaker.record_failure()
        metrics.record(_SCOPE, "error")
        logger.warning("cache call failed (%s)", type(exc).__name__)
        return default, False
    except BaseException:
        breaker.abort_probe()  # not a Redis problem: do not wedge the breaker
        raise
    breaker.record_success()
    return result, True


def cache_get(key: str, default: Any = None) -> Any:
    return _call(lambda: cache.get(key, default), default=default)[0]


def cache_set(key: str, value: Any, *, timeout: int) -> bool:
    return _call(lambda: cache.set(key, value, timeout=timeout), default=None)[1]


def cache_delete_many(keys: Iterable[str]) -> bool:
    key_list = list(keys)
    return _call(lambda: cache.delete_many(key_list), default=None)[1]


def cache_try_lock(key: str, token: str, *, ttl: int) -> bool:
    """Try to take a short lock (atomic SET-if-absent). True also when Redis is down."""
    added, reached = _call(lambda: cache.add(key, token, timeout=ttl), default=False)
    return True if not reached else bool(added)


def cache_unlock(key: str, token: str) -> None:
    """Release a lock only if it is still ours.

    Check-then-delete is not atomic. If our lock expired and another worker took
    it in that tiny gap, we could release theirs early. The lock only reduces
    duplicate database work; it never protects correctness, so that is harmless.
    """

    def _release() -> None:
        if cache.get(key) == token:
            cache.delete(key)

    _call(_release, default=None)


# The big picture: What problem does this solve?
# Remember the circuit breaker from Lesson 7? It knows how to track failures. Remember the metrics module from Lesson 8? It knows how to count events. But neither of them actually talks to Redis.

# This file is the piece that talks to Redis — and it does so carefully, following one golden rule:

# "A cache is an optimisation, never a source of truth."

# That sentence is the heart of the whole file. Let's unpack it.

# What does "never a source of truth" mean?
# In a typical app, there's a database — the source of truth. Everything real lives there. The database is slow but reliable.

# The cache (Redis) sits in front of the database. It holds copies of data that's likely to be asked for again. If it has the answer, great — fast. If it doesn't, fall back to the database — slow but correct.

# Critical insight: the cache holding wrong data, no data, or being dead must never break your app. The database always has the correct answer. The cache is just a shortcut.

# If your app crashes when Redis is down — you've made Redis a source of truth by mistake. That's a bug in the design.

# This file prevents that bug. Every cache operation is designed to degrade gracefully.

# The four rules, from the docstring
# "If Redis is slow or down:
# - a read becomes a MISS (the caller falls back to the database);
# - a write is skipped;
# - a delete reports failure so the caller can log it loudly;
# - a lock reports 'acquired' (fail-open: go to the database, never hang)."

# Each of the four operations has its own sensible fallback:

# Operation	Normal	If Redis is down
# read (get)	Return the cached value	Return None (a "miss") — app goes to DB
# write (set)	Store the value	Skip — don't raise, don't block
# delete (delete_many)	Remove the keys	Return False — caller decides what to do
# lock (try_lock)	Acquire if free	Return True (pretend we got it) — never hang
# Why does a lock "fail open" (return True)?

# Think of a lock as "only one worker should do this work at a time." If Redis is down, we can't coordinate across workers. So what do we do?

# Option A: Fail closed — say "lock not acquired" → nobody does the work. Bad! Now the database query never happens, and the user gets nothing.

# Option B: Fail open — say "lock acquired" → every worker does the work. Slight waste (duplicate DB queries), but the work gets done. Correctness is preserved; only efficiency suffers.

# A cache lock is about reducing duplicate work, not guaranteeing it. So fail open is correct.

# The one exception: TypeError still raises
# "Only connection-type errors are swallowed. A serialization bug (TypeError) still raises, because hiding it would silently disable caching."

# Why? Two categories of errors:

# Error type	Example	Should we hide it?
# Connection (RedisError, OSError)	Redis is down, network timeout	✅ Yes — this is expected and temporary
# Bug (TypeError, AttributeError)	Trying to cache a non-picklable object, passing wrong args	❌ No — this is a programmer mistake
# If we swallowed a TypeError, the app would silently stop caching. You'd never know caching was broken until you inspected metrics weeks later. Bugs should be loud. That's why TypeError re-raises.

# The imports and setup
# python
# from django.core.cache import cache
# from redis.exceptions import RedisError

# from lrb.core.cache import metrics
# from lrb.core.cache.breaker import breaker

# logger = logging.getLogger(__name__)

# _CACHE_DOWN = (RedisError, OSError)
# _SCOPE = "_cache"
# T = TypeVar("T")
# Line	Meaning
# from django.core.cache import cache	Django's cache object — cache.get(), cache.set(), etc.
# from redis.exceptions import RedisError	Redis-specific exceptions
# metrics	Lesson 8 — the counter module
# breaker	Lesson 7 — the circuit breaker
# _CACHE_DOWN = (RedisError, OSError)	A tuple of "cache is down" errors
# _SCOPE = "_cache"	The metrics scope name
# T = TypeVar("T")	A type variable — for generics, explained below
# What is _CACHE_DOWN = (RedisError, OSError)?
# This is a tuple of exception types. It's used in except _CACHE_DOWN as exc: — Python's except accepts a tuple and catches any of the listed types. So:

# RedisError → catch (Redis-specific failures: connection refused, timeout, etc.)

# OSError → catch (network-level issues: socket closed, DNS failed, etc.)

# Both mean "Redis is unreachable." That's what we want to handle gracefully.

# What is T = TypeVar("T")?
# This is a type variable — a placeholder for "some type." It's used for generics — writing a function that works with any type.

# Think of it like saying: "Call this function with whatever type you like, and I'll return the same type."

# python
# def first(items: list[T]) -> T:
#     return items[0]
# T means: whatever's in the list, that's what you get back. first([1, 2, 3]) → int. first(["a", "b"]) → str. The hint preserves the type.

# In this file, T is used in _call's signature — so callers know: "Whatever type the operation produces, that's what _call returns."

# Why is this useful? It's not enforced at runtime — it's for editors and type checkers (mypy, Pyright). Your IDE can say: "cache_get returns Any" — no surprises.

# _call() — the heart of the module
# python
# def _call(fn: Callable[[], T], *, default: T | None) -> tuple[T | None, bool]:
#     """Run one cache operation. Returns (result, reached_redis)."""
#     if not breaker.allow():
#         metrics.record(_SCOPE, "breaker_skip")
#         return default, False
#     try:
#         result = fn()
#     except _CACHE_DOWN as exc:
#         breaker.record_failure()
#         metrics.record(_SCOPE, "error")
#         logger.warning("cache call failed (%s)", type(exc).__name__)
#         return default, False
#     except BaseException:
#         breaker.abort_probe()  # not a Redis problem: do not wedge the breaker
#         raise
#     breaker.record_success()
#     return result, True
# This is the function every wrapper calls. It runs one cache operation and returns two things: the result and a flag saying whether Redis was actually reached.

# Why the two-part return? Because the callers need to distinguish "returned None because the value was None" from "returned None because Redis was down":

# Situation	Result	Reached Redis
# Cache had value 42	42	True ✅
# Cache had no key	None (default)	True ✅
# Redis was down	None (default)	False ❌
# Breaker was OPEN	None (default)	False ❌
# The boolean reached lets callers like cache_try_lock treat the two failure modes differently (fail-open). More on that below.

# Let's walk through line by line.

# The signature
# python
# def _call(fn: Callable[[], T], *, default: T | None) -> tuple[T | None, bool]:
# Part	Meaning
# fn: Callable[[], T]	A function that takes no arguments and returns type T
# *, default: T | None	A fallback value if Redis is down (keyword-only)
# -> tuple[T | None, bool]	Returns (result, reached)
# What's Callable[[], T]? It's a type hint for "a function that takes no arguments and returns T." The [] is an empty list of parameters — meaning the function takes no arguments.

# You pass a lambda or a small function. For example:

# python
# _call(lambda: cache.get(key, default), default=default)
# The lambda is fn — a "function with no parameters" that will call cache.get(key, default).

# Why pass a function? Because the operation might never run (breaker is open) or might fail (Redis is down). By wrapping the actual call in a lambda, _call decides whether and how to invoke it.

# Step 1: check the breaker
# python
# if not breaker.allow():
#     metrics.record(_SCOPE, "breaker_skip")
#     return default, False
# "Ask the breaker: should I call Redis?"

# If allow() returns False — skip Redis entirely. The breaker is OPEN, or a probe is already in flight in HALF_OPEN.

# Record a breaker_skip metric — so dashboards can see "we're skipping due to breaker."

# Return (default, False) — the fallback value, with reached_redis = False.

# Why check allow() BEFORE calling fn()? Because that's the whole point of the breaker — avoid making the expensive call. If we called fn() first and checked the breaker after, we'd still have waited for the timeout.

# Step 2: try the call
# python
# try:
#     result = fn()
# "Now actually call the operation."

# The lambda runs. cache.get(...), cache.set(...), whatever — the actual Redis call.

# If it succeeds, we skip the except blocks and go to record_success() below.

# If it raises, we jump to one of the two except blocks below.

# Step 3: except _CACHE_DOWN — connection error
# python
# except _CACHE_DOWN as exc:
#     breaker.record_failure()
#     metrics.record(_SCOPE, "error")
#     logger.warning("cache call failed (%s)", type(exc).__name__)
#     return default, False
# "Redis is down. Note the failure, count the error, log it, and return the fallback."

# breaker.record_failure() — Lesson 7. Tells the breaker: "another failure." After 5, the breaker OPENS. After a failed probe in HALF_OPEN, it re-OPENs immediately.

# metrics.record(_SCOPE, "error") — Lesson 8. Increments the error counter.

# logger.warning(...) — logs the error type name ("ConnectionError", "TimeoutError", etc.) but not the full traceback or message — because this can fire once per request, and we don't want to flood logs. The breaker's own log (when it opens) is the loud one.

# return default, False — the caller gets the fallback, and the False says "Redis was not reached."

# Why log at warning and not error? Because this is expected — Redis is allowed to die. Warnings mean "something to watch"; errors mean "something is wrong." A single Redis failure is a warning. Many is a problem — and that's what the breaker's logger.error(...) when it OPENS is for.

# Why type(exc).__name__ and not str(exc)? Because str(exc) can contain sensitive data (hostnames, IPs) or be very long (full tracebacks). type(exc).__name__ gives just the class name: "ConnectionError", "TimeoutError" — clean and safe.

# Step 4: except BaseException — any other error
# python
# except BaseException:
#     breaker.abort_probe()  # not a Redis problem: do not wedge the breaker
#     raise
# "Some other error happened. It's not Redis's fault — release the probe slot and re-raise."

# This is subtle. Let's break it down.

# What is BaseException? The root of all exceptions in Python — the parent of Exception and KeyboardInterrupt, SystemExit, etc. Catching BaseException is very broad — usually too broad.

# Why use it here? Because this catch must fire only if the error was NOT already caught by _CACHE_DOWN. Since Python evaluates except clauses in order, if the error was RedisError or OSError, the first except caught it. So we reach this one only for non-Redis errors (bugs, KeyboardInterrupt, etc.).

# What does abort_probe() do? From Lesson 7 — it frees the _probe_in_flight flag without counting a failure. The docstring from that module said:

# "A non-Redis error (e.g. an unserializable value) ended a probe: free the slot."

# Why is this important? Consider this sequence:

# Breaker is HALF_OPEN.

# allow() returns True and sets _probe_in_flight = True.

# The lambda runs — but raises TypeError (can't serialize the value).

# Without abort_probe(), _probe_in_flight stays True forever.

# Result: No future probe can ever run — the breaker is stuck in HALF_OPEN rejecting everything.

# The abort_probe() fixes this — it says: "The probe ended, but not because of Redis. Free the slot so we can try again next time."

# Why raise at the end? To re-raise the original exception. We caught it, but we don't want to swallow it. raise (bare) re-throws the same exception to the caller. The bug still surfaces — as it should.

# In short:

# abort_probe() — cleans up.

# raise — still lets the bug be visible.

# Both lines are doing essential work.

# Step 5: on success
# python
# breaker.record_success()
# return result, True
# "The call worked. Tell the breaker, and return the result."

# breaker.record_success() — Lesson 7. If we were HALF_OPEN, this closes the breaker. Otherwise it resets the failure counter to 0. Either way — Redis is healthy.

# return result, True — the caller gets the real result, and True says "yes, we reached Redis."

# The wrapper functions
# Each wrapper is tiny — the heavy lifting is in _call. Each is a specialised version for one cache operation.

# cache_get — a read
# python
# def cache_get(key: str, default: Any = None) -> Any:
#     return _call(lambda: cache.get(key, default), default=default)[0]
# "Read from cache; return default if missing OR down."

# The lambda calls cache.get(key, default).

# default=default — the fallback. If Redis is down, we return default (usually None).

# [0] — take the first element of the returned tuple. We only care about the result, not the reached flag.

# Why is this a "miss" on failure? Because the caller can't tell the difference between:

# "The key wasn't in cache" (real miss)

# "Redis was down" (fake miss)

# Both lead to the same action: query the database. So from the caller's perspective, treating them the same is correct. The metrics distinguish them — _cache.error for real errors, no hit for a real miss. But the caller doesn't need that distinction.

# Example usage:

# python
# from lrb.core.cache import cache_get

# def get_user(user_id):
#     cached = cache_get(f"user:{user_id}")
#     if cached is not None:
#         return cached
#     # Fall through to database
#     user = User.objects.get(id=user_id)
#     return user
# If Redis is down, cache_get returns None — the code goes to the database — correct behavior.

# cache_set — a write
# python
# def cache_set(key: str, value: Any, *, timeout: int) -> bool:
#     return _call(lambda: cache.set(key, value, timeout=timeout), default=None)[1]
# "Write to cache; return True if Redis was reached, False if down."

# The lambda calls cache.set(key, value, timeout=timeout).

# default=None — fallback is None (which is falsy).

# [1] — take the second element — the reached flag.

# Why return reached, not result? Because cache.set returns None on success — that's useless to us. What we want to know is: "did the write actually happen?"

# True → Redis was reached, the value is stored.

# False → Redis was down (or breaker open), the value was not stored.

# Callers typically ignore this return value — a failed write is fine, the next read will just miss and load from DB. But callers who care (e.g., for logging) can check.

# Example usage:

# python
# from lrb.core.cache import cache_set

# def get_user(user_id):
#     user = User.objects.get(id=user_id)
#     cache_set(f"user:{user_id}", user, timeout=300)   # 5 minutes
#     return user
# If Redis is down, cache_set returns False — but we don't care. The user is still returned correctly.

# cache_delete_many — bulk delete
# python
# def cache_delete_many(keys: Iterable[str]) -> bool:
#     key_list = list(keys)
#     return _call(lambda: cache.delete_many(key_list), default=None)[1]
# "Delete these keys; return True if Redis was reached, False if down."

# Two pieces:

# 1. key_list = list(keys) — materialise the iterable into a list.

# Why? Because keys is an Iterable — it might be a generator, a set, a queryset, etc. If we passed a generator into the lambda, it might be consumed before Redis actually sees it (e.g., if we retried, or if we inspected it). By calling list(keys) once, we:

# Get a stable snapshot.

# Allow multiple uses of key_list (though in this specific case, we only use it once — but it's defensive).

# 2. [1] — again, return the reached flag, not the result. cache.delete_many returns the number of keys deleted — but if Redis is down, we can't trust that. The caller wants to know "did the delete happen?"

# Why is delete different from read/write? The docstring says:

# "a delete reports failure so the caller can log it loudly."

# Deletes are often invalidations — "the user updated their profile, so remove the cache." If the delete fails, the cache now holds stale data. The user sees their old profile for up to timeout seconds.

# This matters! So cache_delete_many returns False — and the caller can log loudly or take action (e.g., set a shorter TTL on the next write, or alert). It's not "swallowed" — the caller knows.

# Example usage:

# python
# from lrb.core.cache import cache_delete_many

# def update_user(user_id, data):
#     user = User.objects.get(id=user_id)
#     user.update(**data)
#     if not cache_delete_many([f"user:{user_id}", f"user:{user_id}:profile"]):
#         logger.error("Cache invalidation failed for user %s — stale data possible", user_id)
# The loudness is the point.

# cache_try_lock — fail-open locking
# python
# def cache_try_lock(key: str, token: str, *, ttl: int) -> bool:
#     """Try to take a short lock (atomic SET-if-absent). True also when Redis is down."""
#     added, reached = _call(lambda: cache.add(key, token, timeout=ttl), default=False)
#     return True if not reached else bool(added)
# This is the most interesting wrapper. Let's fully unpack it.

# What is cache.add? Django's cache has a method add(key, value, timeout) that:

# Adds the key only if it doesn't already exist (atomic operation — Redis SET NX).

# Returns True if it was added, False if the key already existed.

# This is a cheap lock: the first worker to call cache.add gets True — they "have the lock." Everyone else gets False.

# The logic in three cases:

# Case	added	reached	Return
# Successfully acquired	True	True	True if not True else bool(True) = True ✅
# Already locked by another worker	False	True	True if not True else bool(False) = False ❌
# Redis down	False (default)	False	True if not False else ... = True ⚠️ fail-open!
# Read that last row carefully. When Redis is down:

# default=False → added = False

# reached = False

# True if not reached else bool(added) — since not reached is True, we return True.

# We lie and say "you have the lock."

# Why? Because we can't coordinate without Redis. The alternative (returning False) would mean nobody gets to do the work — the database query never runs. So we return True: everyone tries — slight waste, but correctness preserved.

# The docstring says it directly:

# "True also when Redis is down."

# Example usage:

# python
# from lrb.core.cache import cache_try_lock, cache_unlock

# def refresh_expensive_data():
#     if cache_try_lock("refresh:expensive", "worker-1", ttl=30):
#         try:
#             data = slow_database_query()
#             cache_set("expensive:data", data, timeout=300)
#         finally:
#             cache_unlock("refresh:expensive", "worker-1")
# If Redis is up: only one worker runs slow_database_query(). Others skip.
# If Redis is down: all workers run it — duplicate work, but the data is refreshed.

# cache_unlock — release only if still ours
# python
# def cache_unlock(key: str, token: str) -> None:
#     """Release a lock only if it is still ours.

#     Check-then-delete is not atomic. If our lock expired and another worker took
#     it in that tiny gap, we could release theirs early. The lock only reduces
#     duplicate database work; it never protects correctness, so that is harmless.
#     """

#     def _release() -> None:
#         if cache.get(key) == token:
#             cache.delete(key)

#     _call(_release, default=None)
# The big idea: When releasing a lock, we must check that the lock is still ours before deleting it.

# Why? Because our lock had a ttl (say 30 seconds). If our code took longer than 30 seconds:

# t=0: We call cache_try_lock("lock", "worker-A", ttl=30) → True. We hold the lock.

# t=30: The lock expires in Redis.

# t=31: Worker B calls cache_try_lock("lock", "worker-B", ttl=30) → True. B holds the lock.

# t=35: We (worker A) finally finish, and call cache_unlock("lock", "worker-A").

# Without the check: cache.delete("lock") would delete B's lock. Now B thinks it holds the lock, but the lock is gone — C can also get it. Duplicate work across the board.

# With the check: cache.get("lock") returns "worker-B" — not "worker-A" — so we don't delete. B's lock stays intact. ✅

# The docstring's honest caveat:

# "Check-then-delete is not atomic. If our lock expired and another worker took it in that tiny gap, we could release theirs early."

# What's the "tiny gap"?

# cache.get(key) returns "worker-A" — the value is still ours.

# ← tiny gap — the lock expires — Worker B takes it

# cache.delete(key) — deletes B's lock!

# There's a few-microsecond window where a race could happen. But the docstring says this is harmless — because:

# "The lock only reduces duplicate database work; it never protects correctness."

# Meaning: if the race does happen, worker B might have its lock deleted early, and worker C might also run the work. Worst case: duplicate database query. Not: corrupt data. The lock was never a correctness guarantee — it's an efficiency optimisation.

# If you needed atomicity, you'd use a Lua script in Redis, or a WATCH/MULTI/EXEC transaction. That's more complexity for a rare race that only affects duplicate work. The team decided the trade-off isn't worth it — and the docstring documents that decision.

# The full picture: how all four lessons combine
# Let's trace a single cache_get call with all four lessons active.

# Setup: Worker with breaker OPEN (from earlier failures), default settings.

# python
# value = cache_get("user:42")
# Step 1 — cache_get calls _call(lambda: cache.get("user:42", None), default=None).

# Step 2 — _call asks breaker.allow() (Lesson 7).

# State is OPEN. _clock() - _opened_at = 3 seconds. Cooldown is 10. So allow() returns False.

# Step 3 — _call records metrics.record("_cache", "breaker_skip") (Lesson 8).

# The window counter increments. If this is the 500th event, it flushes to logs.

# Step 4 — _call returns (None, False).

# Step 5 — cache_get returns None.

# Total time: microseconds. No Redis call was attempted. The DB query follows. Correct.

# Now trace a call where Redis is up:

# Step 1 — _call asks breaker.allow() → returns True (state is CLOSED).

# Step 2 — _call runs fn() — cache.get("user:42", None).

# Step 3 — Redis replies {...user data...}.

# Step 4 — _call calls breaker.record_success() → resets failures to 0.

# Step 5 — _call returns ({...user data...}, True).

# Step 6 — cache_get returns the data.

# Total time: a few milliseconds. Correct.

# Now trace a call where Redis just went down (breaker still CLOSED, but 1st failure):

# Step 1 — _call asks breaker.allow() → True.

# Step 2 — _call runs fn() — cache.get("user:42", None).

# Step 3 — Redis connection times out. Raises ConnectionError (a RedisError).

# Step 4 — except _CACHE_DOWN catches it:

# breaker.record_failure() → failures = 1. Breaker still CLOSED.

# metrics.record("_cache", "error") → error count +1.

# logger.warning("cache call failed (ConnectionError)").

# Return (None, False).

# Step 5 — cache_get returns None.

# Total time: 1 second (the timeout). This is the last time we pay full price — after 5 such calls, the breaker opens and future calls are instant.

# Summary table
# Piece	Purpose
# _CACHE_DOWN = (RedisError, OSError)	The connection errors we handle gracefully
# _SCOPE = "_cache"	Metrics scope
# T = TypeVar("T")	Generic type for _call
# _call(fn, default=...)	Universal wrapper — checks breaker, handles errors, records metrics
# cache_get	Read — returns default on miss or down
# cache_set	Write — returns True if reached, False if down
# cache_delete_many	Delete — returns True if reached, False if down (caller can log)
# cache_try_lock	Acquire lock — fail-open (returns True even when Redis is down)
# cache_unlock	Release lock — check-then-delete (race window documented & accepted)
# The four principles this file embodies
# Cache is an optimisation, not a source of truth. Every failure mode degrades to "just use the database."

# Fail-open for locks, fail-closed for reads/writes. Reads return a miss — a caller falls back. Writes skip — the value just isn't cached. Locks return True — correctness preserved at the cost of duplicate work.

# Only Redis errors are swallowed. Bugs still raise. TypeError from a serialization mistake is loud, because silently failing caching would be a bug you don't notice for weeks.

# When in doubt, let the breaker decide. Every operation flows through breaker.allow() — the single point of control that stops all cache traffic during an outage.

# One-line summary
# This file wraps Django's cache with four simple safety rules — reads fail to miss, writes skip, deletes report failure loudly, and locks fail open — routing every call through the circuit breaker and metrics modules so that a dead Redis costs one probe every 10 seconds instead of a timeout on every single call.

# Would you like me to show you what a full request lifecycle looks like from the caller's perspective — where cache_get, cache_set, and cache_try_lock are used together to get maximum speed when Redis is healthy, and graceful degradation when it's not — so you can see the whole design in action?

