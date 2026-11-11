import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from lrb.core.cache import client, metrics
from lrb.core.cache.breaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def b(clock):
    return CircuitBreaker(failure_threshold=3, cooldown=10, clock=clock)


def test_opens_after_consecutive_failures(b):
    for _ in range(2):
        b.record_failure()
    assert b.state == CLOSED and b.allow()
    b.record_failure()
    assert b.state == OPEN and not b.allow()


def test_a_success_resets_the_failure_count(b):
    b.record_failure(); b.record_failure(); b.record_success()
    b.record_failure(); b.record_failure()
    assert b.state == CLOSED


def test_one_probe_after_the_cooldown_then_close_on_success(b, clock):
    for _ in range(3):
        b.record_failure()
    clock.advance(9)
    assert not b.allow()
    clock.advance(1)
    assert b.allow() and b.state == HALF_OPEN
    assert not b.allow()  # only ONE probe at a time
    b.record_success()
    assert b.state == CLOSED and b.allow()


def test_failed_probe_reopens_and_restarts_the_cooldown(b, clock):
    for _ in range(3):
        b.record_failure()
    clock.advance(10)
    assert b.allow()
    b.record_failure()
    assert b.state == OPEN
    clock.advance(9)
    assert not b.allow()


def test_an_aborted_probe_frees_the_slot(b, clock):
    for _ in range(3):
        b.record_failure()
    clock.advance(10)
    assert b.allow()
    b.abort_probe()
    assert b.allow()  # not stuck


# ---- wired into the client --------------------------------------------------

class Flaky:
    def __init__(self):
        self.calls = 0
        self.mode = "down"

    def get(self, key, default=None):
        self.calls += 1
        if self.mode == "down":
            raise RedisConnectionError("down")
        if self.mode == "bug":
            raise TypeError("not serializable")
        return "value"

    def add(self, key, value, timeout=None):
        return self.get(key)


@pytest.fixture
def wired(monkeypatch, clock):
    metrics.reset()
    flaky = Flaky()
    monkeypatch.setattr(client, "cache", flaky)
    monkeypatch.setattr(client, "breaker", CircuitBreaker(failure_threshold=2, cooldown=10, clock=clock))
    return flaky


def test_open_breaker_stops_touching_redis(wired):
    assert client.cache_get("k", "dflt") == "dflt"
    assert client.cache_get("k", "dflt") == "dflt"
    assert wired.calls == 2
    for _ in range(5):
        assert client.cache_get("k", "dflt") == "dflt"
    assert wired.calls == 2  # no more timeouts paid
    assert metrics.snapshot()["_cache"]["breaker_skip"] == 5


def test_recovery_after_the_cooldown(wired, clock):
    client.cache_get("k"); client.cache_get("k")
    wired.mode = "up"
    clock.advance(10)
    assert client.cache_get("k") == "value"  # the probe
    assert client.cache_get("k") == "value"  # closed again


def test_a_bug_during_a_probe_does_not_wedge_the_breaker(wired, clock):
    client.cache_get("k"); client.cache_get("k")
    clock.advance(10)
    wired.mode = "bug"
    with pytest.raises(TypeError):
        client.cache_get("k")
    wired.mode = "up"
    assert client.cache_get("k") == "value"  # a new probe was allowed


def test_locks_fail_open_when_redis_is_down(wired):
    assert client.cache_try_lock("k:lock", "t", ttl=5) is True
