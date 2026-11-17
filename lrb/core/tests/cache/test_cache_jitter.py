"""TTL jitter: one helper, per-tier ranges, and the STRICT 'never longer than ttl' promise."""
import pytest

from lrb.core.cache import policies
from lrb.core.cache.policies import CachePolicy, Consistency, jittered_ttl

STRICT = CachePolicy(
    name="demo.strict", owner="demo", consistency=Consistency.STRICT, ttl=300, description="d"
)
BOUNDED = CachePolicy(
    name="demo.bounded", owner="demo", consistency=Consistency.BOUNDED_STALE,
    ttl=120, stale_ttl=600, description="d", loader="demo.loaders.x",
)


def test_a_strict_entry_never_outlives_its_ttl():
    draws = [jittered_ttl(STRICT, STRICT.ttl) for _ in range(50_000)]
    assert max(draws) <= STRICT.ttl  # the promise: never older than ttl
    assert min(draws) >= round(STRICT.ttl * 0.9)
    assert len(set(draws)) > 10  # and it really is spread out


@pytest.mark.parametrize("ttl", [1, 2, 3, 5, 10, 60, 300])
def test_strict_never_exceeds_ttl_even_for_tiny_ttls(ttl):
    policy = CachePolicy(
        name="demo.tiny", owner="demo", consistency=Consistency.STRICT, ttl=ttl, description="d"
    )
    draws = [jittered_ttl(policy, ttl) for _ in range(5_000)]
    assert 1 <= min(draws) and max(draws) <= ttl


def test_bounded_stale_stays_within_ten_percent_either_way():
    draws = [jittered_ttl(BOUNDED, BOUNDED.ttl) for _ in range(50_000)]
    assert min(draws) >= round(BOUNDED.ttl * 0.9) and max(draws) <= round(BOUNDED.ttl * 1.1)
    assert min(draws) < BOUNDED.ttl < max(draws)  # it goes both ways


def test_the_extreme_random_draws_land_exactly_where_the_ranges_say(monkeypatch):
    monkeypatch.setattr(policies, "_uniform", lambda low, high: high)
    assert jittered_ttl(STRICT, 300) == 300  # STRICT's highest draw is exactly ttl, no more
    assert jittered_ttl(BOUNDED, 120) == 132  # BOUNDED_STALE may run 10 % long
    monkeypatch.setattr(policies, "_uniform", lambda low, high: low)
    assert jittered_ttl(STRICT, 300) == 270
    assert jittered_ttl(BOUNDED, 120) == 108


def test_never_below_one_second(monkeypatch):
    monkeypatch.setattr(policies, "_uniform", lambda low, high: 0.0001)
    assert jittered_ttl(STRICT, 1) == 1
    assert jittered_ttl(BOUNDED, 1) == 1