"""Policy declaration, validation, registry and auto-discovery."""
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from lrb.core.cache import policies
from lrb.core.cache.policies import (
    CachePolicy,
    Consistency,
    all_policies,
    autodiscover_cache_policies,
    get_policy,
    register_policy,
)


def make(**overrides):
    fields = dict(
        name="demo.thing",
        owner="demo",
        consistency=Consistency.BOUNDED_STALE,
        ttl=60,
        stale_ttl=30,
        description="demo",
        loader="demo.selectors.get_thing",
    )
    fields.update(overrides)
    return CachePolicy(**fields)


@pytest.fixture
def empty_registry(monkeypatch):
    # Import every app's policy file FIRST, so it registers in the real registry. A module is
    # only executed once; if it were first imported while the registry is swapped out, its
    # policies would be lost for the rest of the test run.
    autodiscover_cache_policies()
    monkeypatch.setattr(policies, "_REGISTRY", {})


def test_valid_policy_is_accepted():
    assert make().name == "demo.thing"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "Demo.Thing"},  # uppercase
        {"name": "thing"},  # no owner part
        {"name": "other.thing"},  # name does not start with owner
        {"owner": "Demo"},
        {"description": "  "},
        {"ttl": 0},
        {"ttl": 3601},
        {"ttl": 1.5},
        {"ttl": True},
        {"stale_ttl": -1},
        {"stale_ttl": 3601},
        {"loader": "not a path"},
        {"loader": None},  # stale_ttl > 0 needs a loader
        {"cache_missing": True, "missing_ttl": 0},
        {"cache_missing": True, "missing_ttl": 61},  # longer than ttl
        {"consistency": "strict"},  # must be the enum
    ],
)
def test_bad_policies_stop_the_app_booting(overrides):
    with pytest.raises(ImproperlyConfigured):
        make(**overrides)


def test_strict_policy_cannot_be_served_stale_or_live_long():
    with pytest.raises(ImproperlyConfigured):
        make(consistency=Consistency.STRICT, stale_ttl=10)
    with pytest.raises(ImproperlyConfigured):
        make(consistency=Consistency.STRICT, stale_ttl=0, ttl=301)
    assert make(consistency=Consistency.STRICT, stale_ttl=0, ttl=300, loader=None)


def test_register_and_lookup(empty_registry):
    p = register_policy(make())
    assert get_policy("demo.thing") is p
    assert all_policies() == [p]


def test_registering_the_same_policy_twice_is_fine(empty_registry):
    register_policy(make())
    register_policy(make())  # module re-import must not crash
    assert len(all_policies()) == 1


def test_conflicting_duplicate_is_refused(empty_registry):
    register_policy(make())
    with pytest.raises(ImproperlyConfigured):
        register_policy(make(ttl=61))


def test_unknown_policy_is_a_clear_error(empty_registry):
    with pytest.raises(ImproperlyConfigured, match="cache_policies.py"):
        get_policy("nope.nothing")


def test_apps_are_discovered_without_any_central_list():
    autodiscover_cache_policies()
    names = {p.name for p in all_policies()}
    assert {"authz.user_perms", "dashboard.product_stats", "dashboard.user_stats"} <= names


def test_every_registered_loader_really_exists():
    """A typo in a loader path would only show up as a runtime error on a cache miss."""
    autodiscover_cache_policies()
    for policy in all_policies():
        if policy.loader:
            assert callable(import_string(policy.loader)), policy.name


def test_a_model_rule_registered_after_startup_still_gets_connected(monkeypatch):
    from lrb.core.cache import invalidation as inv

    connected = []
    monkeypatch.setattr(inv, "_RULES", [])
    monkeypatch.setattr(inv, "_connect_rule", connected.append)

    monkeypatch.setattr(inv, "_CONNECTED", False)
    inv.register_model_invalidation(model="x.Early", policies=[make()])
    assert connected == []  # startup will connect it in a moment

    monkeypatch.setattr(inv, "_CONNECTED", True)
    inv.register_model_invalidation(model="x.Late", policies=[make()])
    assert [r.model for r in connected] == ["x.Late"]  # startup is over: connect immediately
    inv.register_model_invalidation(model="x.Late", policies=[make()])
    assert len(connected) == 1  # registering the same rule twice does nothing