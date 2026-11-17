"""cached_read(): the one way an app caches a shared, company-scoped read model.

What happens on a call:
  FRESH hit   -> return it.
  STALE hit   -> return it immediately, and ask Celery to recompute it once
                 (stale-while-revalidate). The user never waits for the refresh.
  MISS        -> single-flight: only ONE caller per key recomputes it; the rest
                 wait briefly and read the result (no thundering herd).
  Redis down  -> the circuit breaker makes every read a miss; the database answers.

Not for per-user authorization data. STRICT policies are refused here, because
serving a stale permission, or filling one from a background task, is unsafe.

Value rules: the selector's return value must be JSON-friendly (see serializers.py).
Returning None means "not found" and is only remembered when the policy sets
cache_missing=True; otherwise None is never cached.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Mapping
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from lrb.core.cache import metrics
from lrb.core.cache.client import cache_get, cache_set, cache_try_lock, cache_unlock
from lrb.core.cache.keys import current_tenant_scope, lock_key, policy_key, refresh_lock_key
from lrb.core.cache.policies import CachePolicy, Consistency, get_policy, jittered_ttl
from lrb.core.exceptions import AppPermissionDeniedError
from lrb.core.tenancy import require_company_id

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 15  # a loader that takes longer than this loses its lock
LOCK_WAIT_SECONDS = 2.0  # how long a waiter polls before computing it itself
LOCK_POLL_SECONDS = 0.05
REFRESH_LOCK_TTL_SECONDS = 60

_FRESH, _STALE, _ABSENT = "fresh", "stale", "absent"

# 64 re-entrant locks shared by all keys in this process. Memory stays fixed
# (no per-key cleanup) and a loader that itself calls cached_read cannot deadlock.
_LOCAL_LOCKS = [threading.RLock() for _ in range(64)]


def _local_lock(key: str) -> threading.RLock:
    return _LOCAL_LOCKS[hash(key) % len(_LOCAL_LOCKS)]


def _now() -> float:
    return time.time()


def _tenant_matches(company_id: str) -> bool:
    try:
        return current_tenant_scope() == company_id
    except AppPermissionDeniedError:
        return False


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def cached_read(
    *, policy: CachePolicy, company_id, params: Mapping[str, str] | None = None
) -> Any:
    if policy.consistency is not Consistency.BOUNDED_STALE or not policy.loader:
        raise ImproperlyConfigured(
            f"cached_read needs a BOUNDED_STALE policy with a loader ({policy.name!r} is not)."
        )
    cid = require_company_id(company_id)
    clean = {str(k): str(v) for k, v in (params or {}).items()}

    # Never cache unless the active schema is this company's: a mismatch would
    # mean reading or writing another tenant's keys. Fail safe: ask the database.
    if not _tenant_matches(cid):
        metrics.record(policy.name, "bypass")
        return _call_loader(policy, cid, clean)

    key = policy_key(policy=policy, company_id=cid, params=clean)
    state, value = _inspect(cache_get(key), _now())

    if state == _FRESH:
        metrics.record(policy.name, "negative_hit" if value is None else "hit")
        return value
    if state == _STALE:
        metrics.record(policy.name, "stale_hit")
        _trigger_refresh(policy, cid, clean, key)
        return value

    metrics.record(policy.name, "miss")
    return _load_single_flight(policy, cid, clean, key)


# --------------------------------------------------------------------------- #
# Reading an entry                                                             #
# --------------------------------------------------------------------------- #
def _inspect(entry: Any, now: float) -> tuple[str, Any]:
    """Classify what came back from Redis. Anything unexpected counts as absent."""
    if not isinstance(entry, dict):
        return _ABSENT, None
    fresh_until = entry.get("f")
    if type(fresh_until) not in (int, float):
        return _ABSENT, None
    if entry.get("m") is True:
        # Remembered "not found". Never served stale: past its deadline it is simply gone.
        return (_FRESH, None) if now < fresh_until else (_ABSENT, None)
    if "v" in entry:
        return (_FRESH if now < fresh_until else _STALE), entry["v"]
    return _ABSENT, None


# --------------------------------------------------------------------------- #
# Loading + single-flight                                                      #
# --------------------------------------------------------------------------- #
def _call_loader(policy: CachePolicy, company_id: str, params: dict[str, str]) -> Any:
    loader = import_string(policy.loader)
    started = time.monotonic()
    value = loader(company_id=company_id, **params)
    metrics.record(policy.name, "loaded")
    metrics.record(policy.name, "load_ms", round((time.monotonic() - started) * 1000))
    return value


def _store(policy: CachePolicy, key: str, value: Any) -> None:
    now = _now()
    if value is None:
        if not policy.cache_missing:
            return  # never remember None unless the policy says "not found" is a real answer
        fresh = jittered_ttl(policy, policy.missing_ttl)
        cache_set(key, {"m": True, "f": now + fresh}, timeout=fresh)
        return
    fresh = jittered_ttl(policy, policy.ttl)
    # Keep the value for `stale_ttl` seconds past its fresh window so it can be served stale.
    cache_set(key, {"v": value, "m": False, "f": now + fresh}, timeout=fresh + policy.stale_ttl)


def _load_and_store(policy: CachePolicy, company_id: str, params: dict[str, str], key: str) -> Any:
    value = _call_loader(policy, company_id, params)
    _store(policy, key, value)
    return value


def _fresh_value(key: str) -> tuple[bool, Any]:
    state, value = _inspect(cache_get(key), _now())
    return state == _FRESH, value


def _load_single_flight(policy: CachePolicy, company_id: str, params: dict[str, str], key: str) -> Any:
    # Layer 1: threads inside this process queue up on a local lock.
    with _local_lock(key):
        found, value = _fresh_value(key)  # a sibling thread may have just filled it
        if found:
            return value

        # Layer 2: workers across processes compete for a short Redis lock.
        lock = lock_key(key)
        token = uuid4().hex
        if cache_try_lock(lock, token, ttl=LOCK_TTL_SECONDS):
            try:
                found, value = _fresh_value(key)  # another worker may have just finished
                if found:
                    return value
                return _load_and_store(policy, company_id, params, key)
            finally:
                cache_unlock(lock, token)

        # Someone else is computing it: wait for their result instead of hitting the database.
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(LOCK_POLL_SECONDS)
            found, value = _fresh_value(key)
            if found:
                return value
        # They took too long or died. Fail open: compute it ourselves.
        metrics.record(policy.name, "lock_wait_timeout")
        return _load_and_store(policy, company_id, params, key)


# --------------------------------------------------------------------------- #
# Stale-while-revalidate                                                       #
# --------------------------------------------------------------------------- #
def _enqueue_refresh(*, policy_name: str, company_id: str, params: dict, lock_token: str) -> None:
    from lrb.core.cache.tasks import refresh_cache_entry

    refresh_cache_entry.delay(
        policy_name=policy_name, company_id=company_id, params=params, lock_token=lock_token
    )


def _trigger_refresh(policy: CachePolicy, company_id: str, params: dict[str, str], key: str) -> None:
    lock = refresh_lock_key(key)
    token = uuid4().hex
    if not cache_try_lock(lock, token, ttl=REFRESH_LOCK_TTL_SECONDS):
        metrics.record(policy.name, "refresh_skipped")  # a refresh is already running
        return
    try:
        _enqueue_refresh(
            policy_name=policy.name, company_id=company_id, params=params, lock_token=token
        )
        metrics.record(policy.name, "refresh_enqueued")
    except Exception:  # broker down etc.: the user still gets the stale value
        logger.exception("could not enqueue cache refresh for %s", policy.name)
        metrics.record(policy.name, "refresh_enqueue_failed")
        cache_unlock(lock, token)


def refresh_entry(*, policy_name: str, company_id: str, params: dict[str, str], lock_token: str) -> None:
    """Runs in a Celery worker: recompute one entry inside the right company's schema."""
    from django_tenants.utils import get_tenant_model, tenant_context

    policy = get_policy(policy_name)
    tenant = get_tenant_model().objects.filter(pk=company_id).first()
    if tenant is None:
        metrics.record(policy_name, "refresh_failed")
        logger.warning("cache refresh: company %s no longer exists", company_id)
        return  # the refresh lock expires by itself

    # Keys depend on the active schema, so everything below runs inside it.
    with tenant_context(tenant):
        key = policy_key(policy=policy, company_id=company_id, params=params)
        try:
            _load_and_store(policy, company_id, params, key)
            metrics.record(policy_name, "refresh_ok")
        except Exception:
            metrics.record(policy_name, "refresh_failed")
            logger.exception("cache refresh failed for %s", policy_name)
        finally:
            cache_unlock(refresh_lock_key(key), lock_token)