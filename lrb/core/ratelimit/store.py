"""The Redis connection for rate limiting.

Deliberately NOT Django's cache:
  * cache.clear() or an LRU eviction there would wipe buckets, handing everyone a full burst;
  * Lua needs a raw client.
Use a dedicated DB (default /2), ideally an instance with maxmemory-policy
`noeviction` or `volatile-*` (every key here has a TTL).

Every call goes through its own circuit breaker (the one from lrb.core.cache.breaker),
so a dead Redis costs one probe every few seconds, not a timeout per request.
"""
from __future__ import annotations

import logging
import threading

import redis
from django.conf import settings
from redis.exceptions import RedisError, ResponseError

from lrb.core.cache.breaker import CircuitBreaker
from lrb.core.ratelimit import metrics, scripts

logger = logging.getLogger(__name__)

breaker = CircuitBreaker(failure_threshold=3, cooldown=5.0)


class StoreUnavailable(Exception):
    """Redis could not give an answer (down, slow, breaker open, or a script bug)."""


_lock = threading.Lock()
_client: redis.Redis | None = None
_scripts: dict[str, object] = {}


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                timeout = float(getattr(settings, "RATE_LIMIT_REDIS_TIMEOUT", 0.25))
                _client = redis.Redis.from_url(
                    getattr(settings, "RATE_LIMIT_REDIS_URL", "redis://redis:6379/2"),
                    socket_timeout=timeout,
                    socket_connect_timeout=timeout,
                    health_check_interval=30,
                )
    return _client


def reset_client() -> None:
    """Forget the connection and scripts (tests, or after changing the URL)."""
    global _client
    with _lock:
        _client = None
        _scripts.clear()
    breaker.reset()


def _script(name: str):
    s = _scripts.get(name)
    if s is None:
        s = _get_client().register_script(getattr(scripts, name))
        _scripts[name] = s
    return s


def run(name: str, keys: list[str], args: list, *, policy: str = "_store"):
    if not breaker.allow():
        metrics.record(policy, "breaker_skip")
        raise StoreUnavailable("circuit open")
    try:
        out = _script(name)(keys=keys, args=args)
    except ResponseError as exc:          # a Lua/script problem is OUR bug, not an outage
        breaker.abort_probe()
        metrics.record(policy, "script_error")
        logger.exception("rate-limit script %s failed", name)
        raise StoreUnavailable("script error") from exc
    except (RedisError, OSError) as exc:
        breaker.record_failure()
        metrics.record(policy, "store_error")
        logger.warning("rate-limit store call failed (%s)", type(exc).__name__)
        raise StoreUnavailable(type(exc).__name__) from exc
    except BaseException:
        breaker.abort_probe()
        raise
    breaker.record_success()
    return out
