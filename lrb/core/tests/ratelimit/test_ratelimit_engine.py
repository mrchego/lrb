import os
import multiprocessing as mp
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import redis
from django.conf import settings

from lrb.core.ratelimit import keys, metrics, policies, store
from lrb.core.ratelimit.engine import limiter
from lrb.core.ratelimit.policies import B, Layer, Policy, Window

CO = "11111111-1111-1111-1111-111111111111"
IP = "203.0.113.7"


def define(name, layers, **kw):
    """Register a throw-away policy for one test."""
    p = Policy(name, tuple(layers), **kw)
    policies.POLICIES = {**policies.POLICIES, name: p}  # type: ignore[assignment]
    import lrb.core.ratelimit.engine as eng
    eng.POLICIES = policies.POLICIES
    return p


def hit(name, **kw):
    kw.setdefault("company", CO); kw.setdefault("ip", IP)
    return limiter.check(name, **kw)


def raw():
    return redis.Redis.from_url(settings.RATE_LIMIT_REDIS_URL)


# ---------- token bucket -----------------------------------------------------
def test_bucket_allows_capacity_then_rejects_with_correct_retry():
    define("t1", [Layer("ip", B(5, 5, 60))])
    assert all(hit("t1").allowed for _ in range(5))
    r = hit("t1")
    assert not r.allowed and r.reason == "limit" and r.layer == "ip"
    assert r.retry_after == 12            # 1 token at 5/60s = 12 s


def test_weighted_cost_and_remaining():
    define("t2", [Layer("ip", B(100, 100, 60))])
    r = hit("t2", cost=10)
    assert r.allowed and r.remaining == 90
    assert hit("t2", cost=90).allowed
    assert not hit("t2", cost=1).allowed


def test_invalid_cost_is_rejected():
    define("t3", [Layer("ip", B(5, 5))])
    for bad in (0, -1, 1.5, True, "2"):
        assert hit("t3", cost=bad).reason == "invalid_cost"


def test_refill_over_time_and_cap():
    define("t4", [Layer("ip", B(10, 10, 1))])      # 10 tokens per second
    for _ in range(10): assert hit("t4").allowed
    assert not hit("t4").allowed
    time.sleep(0.5)
    ok = sum(hit("t4").allowed for _ in range(10))
    assert 4 <= ok <= 6                             # ~5 refilled
    time.sleep(1.3)                                 # idle longer than a full refill
    ok = sum(hit("t4").allowed for _ in range(15))
    assert ok == 10                                 # never above capacity


def test_timestamp_is_stored_without_precision_loss():
    define("t5", [Layer("ip", B(5, 5))])
    hit("t5")
    key = keys.build("b", CO, "t5", "ip", keys.hash_identity(IP))
    ts = int(raw().hget(key, "ts"))
    assert abs(ts - int(time.time() * 1e6)) < 5_000_000      # within 5 s, 16 digits intact
    assert len(str(ts)) == 16


def test_fractional_refill_is_not_lost_under_rapid_calls():
    # 3 tokens/hour: calling constantly must still release a token on schedule
    define("t6", [Layer("ip", B(1, 3, 3600))])
    assert hit("t6").allowed
    key = keys.build("b", CO, "t6", "ip", keys.hash_identity(IP))
    r = raw()
    ts = int(r.hget(key, "ts"))
    r.hset(key, "ts", ts - 1_200_000_000)                    # pretend 20 minutes passed
    assert hit("t6").allowed                                 # 1 token (20 min * 3/h)
    assert not hit("t6").allowed


def test_ttl_matches_refill_time_plus_grace():
    define("t7", [Layer("ip", B(100, 100, 60))])
    hit("t7", cost=100)                                      # empty: 60 s to refill
    key = keys.build("b", CO, "t7", "ip", keys.hash_identity(IP))
    ttl = raw().pttl(key)
    assert 60_000 < ttl <= 120_000 + 1000


def test_rejected_requests_do_not_write():
    define("t8", [Layer("ip", B(1, 1, 3600))])
    hit("t8"); key = keys.build("b", CO, "t8", "ip", keys.hash_identity(IP))
    before = raw().hgetall(key); ttl = raw().pttl(key)
    for _ in range(20): assert not hit("t8").allowed
    assert raw().hgetall(key) == before and raw().pttl(key) <= ttl


def test_lowering_policy_clamps_and_never_grants_extra():
    define("t9", [Layer("ip", B(100, 100, 3600))])
    hit("t9")                                                # 99 left
    define("t9", [Layer("ip", B(10, 10, 3600))])
    ok = sum(hit("t9").allowed for _ in range(30))
    assert ok == 10


def test_all_or_nothing_across_layers():
    define("t10", [Layer("actor", B(100, 100, 3600)), Layer("company", B(2, 2, 3600))])
    assert hit("t10", actor="u-1").allowed and hit("t10", actor="u-2").allowed
    assert not hit("t10", actor="u-3").allowed               # company layer empty
    a = hit("t10", actor="u-3", company=CO)
    key = keys.build("b", CO, "t10", "actor", "u-3")
    assert raw().exists(key) == 0                            # user layer was NOT charged


def test_company_isolation():
    define("t11", [Layer("ip", B(2, 2, 3600))])
    other = "22222222-2222-2222-2222-222222222222"
    assert hit("t11").allowed and hit("t11").allowed and not hit("t11").allowed
    assert hit("t11", company=other).allowed                 # B unaffected by A
    for k in raw().scan_iter("rl:*"):
        assert k.decode().split(":")[2] in (CO, other)


def test_exactly_capacity_succeed_under_threads():
    define("t12", [Layer("ip", B(100, 1, 3600))])
    with ThreadPoolExecutor(64) as ex:
        res = list(ex.map(lambda _: hit("t12").allowed, range(1000)))
    assert sum(res) == 100


def _worker(args):
    url, n = args
    from django.conf import settings as s
    s.RATE_LIMIT_REDIS_URL = url
    from lrb.core.ratelimit import store as st
    st.reset_client()
    import lrb.core.ratelimit.policies as pol
    from lrb.core.ratelimit.engine import limiter as lim
    return sum(lim.check("t13", company=CO, ip=IP).allowed for _ in range(n))


def test_exactly_capacity_succeed_across_processes():
    define("t13", [Layer("ip", B(100, 1, 3600))])
    ctx = mp.get_context("fork")
    with ctx.Pool(8) as pool:
        total = sum(pool.map(_worker, [(settings.RATE_LIMIT_REDIS_URL, 125)] * 8))
    assert total == 100


# ---------- sliding window ---------------------------------------------------
def test_window_limit_retry_and_slide():
    define("w1", [Layer("ip", Window(3, 2))])
    assert all(hit("w1").allowed for _ in range(3))
    r = hit("w1")
    assert not r.allowed and 1 <= r.retry_after <= 2
    time.sleep(2.1)
    assert hit("w1").allowed


def test_window_exact_under_concurrency():
    define("w2", [Layer("ip", Window(50, 60))])
    with ThreadPoolExecutor(64) as ex:
        res = list(ex.map(lambda _: hit("w2").allowed, range(500)))
    assert sum(res) == 50


def test_window_rejections_are_not_recorded_and_subject_layer():
    define("w3", [Layer("ip", Window(10, 60)), Layer("subject", Window(2, 60))])
    assert hit("w3", subject="a@x.com").allowed and hit("w3", subject="a@x.com").allowed
    assert not hit("w3", subject="a@x.com").allowed
    assert hit("w3", subject="b@x.com").allowed              # other mailbox unaffected
    zk = keys.build("w", CO, "w3", "ip", keys.hash_identity(IP))
    assert raw().zcard(zk) == 3                              # 2 + 1, the rejection left no trace


# ---------- penalties ----------------------------------------------------------
def test_penalty_escalates_and_blocks_cheaply():
    from lrb.core.ratelimit.policies import PenaltyRule
    define("p1", [Layer("ip", Window(1, 60))], penalty=PenaltyRule(ladder=(0, 2, 5), decay_seconds=3600))
    assert hit("p1").allowed
    r = hit("p1"); assert r.reason == "limit"                # violation 1: reject only
    r = hit("p1"); assert r.reason == "limit"                # violation 2 -> sets 2 s block
    r = hit("p1"); assert r.reason == "penalty" and r.retry_after in (1, 2)
    zk = keys.build("p", CO, "p1", "ip", keys.hash_identity(IP))
    score = float(raw().hget(zk, "score"))
    for _ in range(5): hit("p1")                             # blocked calls don't pile on
    assert float(raw().hget(zk, "score")) == pytest.approx(score, abs=0.01)


def test_penalty_score_decays():
    from lrb.core.ratelimit.policies import PenaltyRule
    define("p2", [Layer("ip", Window(1, 60))], penalty=PenaltyRule(ladder=(0, 0, 0), decay_seconds=1))
    hit("p2"); hit("p2"); hit("p2")
    zk = keys.build("p", CO, "p2", "ip", keys.hash_identity(IP))
    s1 = float(raw().hget(zk, "score")); time.sleep(1.2); hit("p2")
    assert float(raw().hget(zk, "score")) < s1 + 1 - 0.9     # decayed by ~1 before +1


# ---------- concurrency ---------------------------------------------------------
def test_semaphore_limits_and_releases():
    from lrb.core.ratelimit.policies import Concurrency
    define("c1", [Layer("actor", B(100, 100))], concurrency=Concurrency(max=2, lease_seconds=60))
    a = limiter.acquire_slot("c1", company=CO, actor="u-1")
    b = limiter.acquire_slot("c1", company=CO, actor="u-2")
    c = limiter.acquire_slot("c1", company=CO, actor="u-3")
    assert a.acquired and b.acquired and not c.acquired
    limiter.release_slot(a.slot)
    assert limiter.acquire_slot("c1", company=CO, actor="u-3").acquired
    limiter.release_slot(a.slot)                              # double release is harmless
    assert not limiter.acquire_slot("c1", company=CO, actor="u-4").acquired


def test_semaphore_lease_expires_after_crash():
    from lrb.core.ratelimit.policies import Concurrency
    define("c2", [Layer("actor", B(100, 100))], concurrency=Concurrency(max=1, lease_seconds=1))
    assert limiter.acquire_slot("c2", company=CO, actor=None).acquired
    assert not limiter.acquire_slot("c2", company=CO, actor=None).acquired
    time.sleep(1.2)
    assert limiter.acquire_slot("c2", company=CO, actor=None).acquired


def test_semaphore_is_per_company():
    from lrb.core.ratelimit.policies import Concurrency
    define("c3", [Layer("actor", B(100, 100))], concurrency=Concurrency(max=1))
    assert limiter.acquire_slot("c3", company=CO, actor=None).acquired
    assert limiter.acquire_slot("c3", company="22222222-2222-2222-2222-222222222222", actor=None).acquired


# ---------- Redis failure ---------------------------------------------------------
@pytest.fixture
def dead_redis(settings):
    settings.RATE_LIMIT_REDIS_URL = "redis://127.0.0.1:1/0"
    settings.RATE_LIMIT_REDIS_TIMEOUT = 0.05
    store.reset_client()


def test_failure_modes(dead_redis):
    define("f_open", [Layer("ip", B(2, 2))], failure="open")
    define("f_closed", [Layer("ip", B(2, 2))], failure="closed")
    define("f_local", [Layer("ip", B(2, 2, 3600))], failure="local")
    assert hit("f_open").allowed and hit("f_open").degraded
    r = hit("f_closed"); assert not r.allowed and r.reason == "unavailable" and r.retry_after >= 1
    assert hit("f_local").allowed and hit("f_local").allowed
    r = hit("f_local"); assert not r.allowed and r.degraded and r.retry_after >= 1


def test_breaker_stops_hammering_dead_redis(dead_redis):
    define("f2", [Layer("ip", B(5, 5))], failure="open")
    for _ in range(10): hit("f2")
    assert store.breaker.state == "open"
    t = time.perf_counter()
    for _ in range(200): hit("f2")
    assert time.perf_counter() - t < 0.5                      # instant, no socket timeouts


def test_recovers_when_redis_returns(settings):
    define("f3", [Layer("ip", B(5, 5))], failure="closed")
    settings.RATE_LIMIT_REDIS_URL = "redis://127.0.0.1:1/0"; settings.RATE_LIMIT_REDIS_TIMEOUT = 0.05
    store.reset_client()
    for _ in range(5): hit("f3")
    assert store.breaker.state == "open"
    settings.RATE_LIMIT_REDIS_URL = os.environ.get("RATE_LIMIT_TEST_REDIS_URL", "redis://redis:6379/15")
    store.reset_client(); store.breaker.reset()
    assert hit("f3").allowed


# ---------- shadow / off ----------------------------------------------------------
def test_shadow_counts_but_never_blocks(settings):
    define("s1", [Layer("ip", B(1, 1, 3600))])
    settings.RATE_LIMIT_MODE = "shadow"
    assert hit("s1").allowed
    r = hit("s1"); assert r.allowed and r.reason == "shadow"
    assert metrics.snapshot()["s1"]["shadow_rejected"] == 1


def test_off_mode_touches_nothing(settings):
    define("s2", [Layer("ip", B(1, 1))])
    settings.RATE_LIMIT_MODE = "off"
    assert all(hit("s2").allowed for _ in range(5))
    assert raw().dbsize() == 0


# ---------- registry ------------------------------------------------------------------
def test_registry_rejects_bad_policies():
    from django.core.exceptions import ImproperlyConfigured
    import importlib
    good = policies.POLICIES
    try:
        policies.POLICIES = {"x": Policy("x", (Layer("ip", B(5, 5, 10**6)),))}
        with pytest.raises(ImproperlyConfigured):
            policies.validate()                                # exceeds exact arithmetic
        policies.POLICIES = {"x": Policy("x", (Layer("ip", B(5, 5)), Layer("actor", Window(1, 1))))}
        with pytest.raises(ImproperlyConfigured):
            policies.validate()                                # mixed algorithms
    finally:
        policies.POLICIES = good


def test_every_shipped_operation_can_succeed():
    policies.validate()
    for op in policies.STRICT_OPERATIONS:
        assert op in policies.OPERATIONS


def test_penalty_level_is_not_undercounted_by_slow_round_trips():
    """Two violations a few tens of ms apart must still count as level 2 (decay in between
    is negligible). Regression: a 1e-6 tolerance made this depend on Redis latency."""
    from lrb.core.ratelimit.policies import PenaltyRule
    define("p3", [Layer("ip", Window(1, 60))], penalty=PenaltyRule(ladder=(0, 30, 120), decay_seconds=900))
    assert hit("p3").allowed
    assert hit("p3").reason == "limit"
    time.sleep(0.05)
    assert hit("p3").reason == "limit"          # 2nd violation -> 30 s block
    assert hit("p3").reason == "penalty"
