"""cached_read: fresh/stale/miss, single-flight, negative caching, failures."""
import contextlib
import threading
import time
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from redis.exceptions import ConnectionError as RedisConnectionError

from lrb.core.cache import client, metrics, read
from lrb.core.cache.breaker import breaker
from lrb.core.cache.invalidation import _make_handler, _ModelRule, invalidate_policy
from lrb.core.cache.keys import lock_key, policy_key
from lrb.core.cache.policies import CachePolicy, Consistency

POLICY = CachePolicy(
    name="demo.stats", owner="demo", consistency=Consistency.BOUNDED_STALE,
    ttl=60, stale_ttl=120, description="demo", loader="demo.loaders.stats",
)
NEGATIVE = CachePolicy(
    name="demo.lookup", owner="demo", consistency=Consistency.BOUNDED_STALE,
    ttl=60, stale_ttl=0, cache_missing=True, missing_ttl=30,
    description="demo", loader="demo.loaders.lookup",
)


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class Loader:
    """Stands in for a selector; counts calls and can be slow or failing."""

    def __init__(self, value=None, delay=0.0):
        self.value, self.delay, self.calls, self.fail = value, delay, [], False
        self._lock = threading.Lock()

    def __call__(self, *, company_id, **params):
        with self._lock:
            self.calls.append((company_id, params))
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("database down")
        return self.value


@pytest.fixture(autouse=True)
def env(monkeypatch):
    cache.clear()
    breaker.reset()
    metrics.reset()
    clock = Clock()
    monkeypatch.setattr(read, "_now", clock)
    monkeypatch.setattr(read, "jittered_ttl", lambda policy, seconds: seconds)
    monkeypatch.setattr(read, "_tenant_matches", lambda company_id: True)
    return clock


@pytest.fixture
def loader(monkeypatch):
    fn = Loader(value={"n": 1})
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    return fn


@pytest.fixture
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr(read, "_enqueue_refresh", lambda **kw: calls.append(kw))
    return calls


# ---- basics -----------------------------------------------------------------

def test_second_read_is_a_fresh_hit(loader):
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(loader.calls) == 1
    snap = metrics.snapshot()["demo.stats"]
    assert snap["miss"] == 1 and snap["hit"] == 1


def test_companies_never_share_entries(monkeypatch):
    monkeypatch.setattr(read, "import_string", lambda path: lambda *, company_id: {"for": company_id})
    assert read.cached_read(policy=POLICY, company_id="A") == {"for": "A"}
    assert read.cached_read(policy=POLICY, company_id="B") == {"for": "B"}
    assert read.cached_read(policy=POLICY, company_id="A") == {"for": "A"}


def test_params_are_part_of_the_key(loader):
    read.cached_read(policy=POLICY, company_id="A", params={"sku": "x"})
    read.cached_read(policy=POLICY, company_id="A", params={"sku": "y"})
    read.cached_read(policy=POLICY, company_id="A", params={"sku": "x"})
    assert [c[1] for c in loader.calls] == [{"sku": "x"}, {"sku": "y"}]


def test_value_and_timeouts_follow_the_policy(loader, monkeypatch):
    seen = []
    monkeypatch.setattr(read, "cache_set", lambda key, value, *, timeout: seen.append((value, timeout)))
    read.cached_read(policy=POLICY, company_id="A")
    value, timeout = seen[0]
    assert timeout == POLICY.ttl + POLICY.stale_ttl  # stays stored while it may be served stale
    assert value["v"] == {"n": 1} and value["m"] is False


def test_cached_read_applies_the_shared_jitter(loader, monkeypatch, env):
    from lrb.core.cache import policies

    monkeypatch.setattr(read, "jittered_ttl", policies.jittered_ttl)  # undo the autouse pin
    monkeypatch.setattr(policies, "_uniform", lambda low, high: high)  # BOUNDED_STALE: +10 %
    seen = []
    monkeypatch.setattr(read, "cache_set", lambda key, value, *, timeout: seen.append((value, timeout)))
    read.cached_read(policy=POLICY, company_id="A")
    value, timeout = seen[0]
    assert value["f"] - env.t == 66  # fresh window = ttl 60 + 10 %
    assert timeout == 66 + POLICY.stale_ttl  # stale window added on top, not jittered


def test_strict_policies_and_policies_without_loader_are_refused(loader):
    strict = CachePolicy(name="demo.perm", owner="demo", consistency=Consistency.STRICT, ttl=60, description="d")
    with pytest.raises(ImproperlyConfigured):
        read.cached_read(policy=strict, company_id="A")
    no_loader = CachePolicy(name="demo.nl", owner="demo", consistency=Consistency.BOUNDED_STALE, ttl=60, description="d")
    with pytest.raises(ImproperlyConfigured):
        read.cached_read(policy=no_loader, company_id="A")


def test_missing_company_fails_closed(loader):
    from lrb.core.exceptions import AppPermissionDeniedError

    with pytest.raises(AppPermissionDeniedError):
        read.cached_read(policy=POLICY, company_id=None)
    assert loader.calls == []


def test_wrong_tenant_bypasses_the_cache_completely(loader, monkeypatch):
    monkeypatch.setattr(read, "_tenant_matches", lambda company_id: False)
    read.cached_read(policy=POLICY, company_id="A")
    read.cached_read(policy=POLICY, company_id="A")
    assert len(loader.calls) == 2  # asked the database both times
    assert cache.get(policy_key(policy=POLICY, company_id="A")) is None  # and stored nothing
    assert metrics.snapshot()["demo.stats"]["bypass"] == 2


@pytest.mark.parametrize("junk", ["garbage", 5, ["x"], {"f": "soon", "v": 1}, {"v": 1}, {"f": 1}])
def test_corrupt_entries_count_as_a_miss(loader, junk):
    cache.set(policy_key(policy=POLICY, company_id="A"), junk)
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(loader.calls) == 1


def test_loader_errors_are_not_cached(loader):
    loader.fail = True
    with pytest.raises(RuntimeError):
        read.cached_read(policy=POLICY, company_id="A")
    loader.fail = False
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}


# ---- negative caching -------------------------------------------------------

def test_not_found_is_remembered_when_the_policy_allows_it(monkeypatch, env):
    fn = Loader(value=None)
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    assert read.cached_read(policy=NEGATIVE, company_id="A") is None
    assert read.cached_read(policy=NEGATIVE, company_id="A") is None
    assert len(fn.calls) == 1
    assert metrics.snapshot()["demo.lookup"]["negative_hit"] == 1
    env.advance(31)  # past missing_ttl: forgotten, never served stale
    read.cached_read(policy=NEGATIVE, company_id="A")
    assert len(fn.calls) == 2


def test_none_is_never_cached_unless_declared(monkeypatch):
    fn = Loader(value=None)
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    read.cached_read(policy=POLICY, company_id="A")
    read.cached_read(policy=POLICY, company_id="A")
    assert len(fn.calls) == 2


# ---- stale-while-revalidate -------------------------------------------------

def test_stale_value_is_served_instantly_and_refreshed_once(loader, enqueued, env):
    read.cached_read(policy=POLICY, company_id="A")
    env.advance(POLICY.ttl + 1)  # now stale, but still stored

    loader.value = {"n": 2}
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}  # old value, no waiting
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(loader.calls) == 1  # the request path never ran the loader
    assert len(enqueued) == 1  # and only ONE refresh was requested
    assert enqueued[0]["policy_name"] == "demo.stats" and enqueued[0]["company_id"] == "A"
    snap = metrics.snapshot()["demo.stats"]
    assert snap["stale_hit"] == 2 and snap["refresh_enqueued"] == 1 and snap["refresh_skipped"] == 1

    # What the Celery task does: recompute and store.
    key = policy_key(policy=POLICY, company_id="A")
    read._load_and_store(POLICY, "A", {}, key)
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 2}


def test_failed_enqueue_still_returns_the_stale_value(loader, env, monkeypatch):
    attempts = []

    def boom(**kw):
        attempts.append(kw)
        raise ConnectionError("broker down")

    monkeypatch.setattr(read, "_enqueue_refresh", boom)
    read.cached_read(policy=POLICY, company_id="A")
    env.advance(POLICY.ttl + 1)
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(attempts) == 2  # the lock was freed, so the next read tried again


# ---- single-flight ----------------------------------------------------------

def _run_threads(count, fn):
    barrier = threading.Barrier(count)
    results, errors = [], []

    def work():
        barrier.wait()
        try:
            results.append(fn())
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(count)]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    assert not errors, errors
    return results


def test_threads_in_one_process_share_one_load(monkeypatch):
    fn = Loader(value={"n": 1}, delay=0.3)
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    results = _run_threads(8, lambda: read.cached_read(policy=POLICY, company_id="A"))
    assert results == [{"n": 1}] * 8
    assert len(fn.calls) == 1


def test_the_local_lock_alone_is_enough_inside_one_process(monkeypatch):
    """Redis lock switched off: only the per-process lock stands between 8 threads and 8 loads."""
    fn = Loader(value={"n": 1}, delay=0.3)
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    monkeypatch.setattr(read, "cache_try_lock", lambda *a, **k: True)
    results = _run_threads(8, lambda: read.cached_read(policy=POLICY, company_id="A"))
    assert results == [{"n": 1}] * 8
    assert len(fn.calls) == 1


def test_separate_processes_share_one_load_through_the_redis_lock(monkeypatch):
    """No local lock = what several gunicorn workers look like to each other."""
    fn = Loader(value={"n": 1}, delay=0.3)
    monkeypatch.setattr(read, "import_string", lambda path: fn)
    monkeypatch.setattr(read, "_local_lock", lambda key: contextlib.nullcontext())
    results = _run_threads(6, lambda: read.cached_read(policy=POLICY, company_id="A"))
    assert results == [{"n": 1}] * 6
    assert len(fn.calls) == 1


def test_a_stuck_lock_holder_cannot_hang_us(loader, monkeypatch):
    key = policy_key(policy=POLICY, company_id="A")
    cache.add(lock_key(key), "someone-else", timeout=30)  # a worker that died mid-load
    monkeypatch.setattr(read, "LOCK_WAIT_SECONDS", 0.15)
    monkeypatch.setattr(read, "LOCK_POLL_SECONDS", 0.03)
    assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(loader.calls) == 1  # we computed it ourselves
    assert metrics.snapshot()["demo.stats"]["lock_wait_timeout"] == 1


def test_a_loader_that_calls_cached_read_does_not_deadlock(monkeypatch):
    inner = Loader(value={"inner": True})
    outer_calls = []

    def outer_loader(*, company_id, **params):
        outer_calls.append(1)
        return {"outer": read.cached_read(policy=NEGATIVE, company_id=company_id)}

    monkeypatch.setattr(read, "import_string", lambda path: inner if path.endswith("lookup") else outer_loader)
    assert read.cached_read(policy=POLICY, company_id="A") == {"outer": {"inner": True}}


# ---- Redis trouble ----------------------------------------------------------

class DeadCache:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RedisConnectionError("redis is down")

        return fail


def test_redis_down_means_the_database_answers_every_time(loader, monkeypatch):
    monkeypatch.setattr(client, "cache", DeadCache())
    for _ in range(4):
        assert read.cached_read(policy=POLICY, company_id="A") == {"n": 1}
    assert len(loader.calls) == 4
    assert breaker.state == "open"  # after a few failures it stops even trying


# ---- invalidation -----------------------------------------------------------

@pytest.mark.django_db
def test_invalidate_policy_waits_for_commit(loader, django_capture_on_commit_callbacks):
    read.cached_read(policy=POLICY, company_id="A")
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        invalidate_policy(policy=POLICY, company_id="A")
        read.cached_read(policy=POLICY, company_id="A")  # inside the transaction: still cached
    assert len(loader.calls) == 1
    callbacks[0]()  # the commit happens
    read.cached_read(policy=POLICY, company_id="A")
    assert len(loader.calls) == 2


@pytest.mark.django_db
def test_model_rule_invalidates_the_rows_company_only(loader, django_capture_on_commit_callbacks):
    read.cached_read(policy=POLICY, company_id="A")
    read.cached_read(policy=POLICY, company_id="B")
    handler = _make_handler(_ModelRule(model="x.Thing", policies=(POLICY,), company_field="company_id"))
    with django_capture_on_commit_callbacks(execute=True):
        handler(sender=None, instance=SimpleNamespace(company_id="A"))
        handler(sender=None, instance=SimpleNamespace(company_id=None))  # ignored
        handler(sender=None, instance=SimpleNamespace(company_id="Z"), raw=True)  # fixtures: ignored
    assert cache.get(policy_key(policy=POLICY, company_id="A")) is None
    assert cache.get(policy_key(policy=POLICY, company_id="B")) is not None