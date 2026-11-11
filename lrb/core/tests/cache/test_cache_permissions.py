"""The permission cache after migrating to the platform (policy, metrics, safety rules)."""
from types import SimpleNamespace

import pytest
from django.core.cache import cache

from lrb.authorization.cache_policies import USER_PERMISSIONS
from lrb.authorization.selectors import get_user_permissions as sel
from lrb.core.cache import metrics
from lrb.core.cache.policies import Consistency
from lrb.core.exceptions import AppPermissionDeniedError


@pytest.fixture(autouse=True)
def env(monkeypatch):
    cache.clear()
    metrics.reset()
    monkeypatch.setattr(sel, "current_tenant_scope", lambda: "c1")
    calls = []

    def compute(*, user):
        calls.append(user.id)
        return {"products.view_product", "products.create_product"}

    monkeypatch.setattr(sel, "_compute_user_permission_codenames", compute)
    return calls


USER = SimpleNamespace(id="u1", company_id="c1")


def test_permissions_policy_is_strict_and_short():
    assert USER_PERMISSIONS.consistency is Consistency.STRICT
    assert USER_PERMISSIONS.stale_ttl == 0
    assert sel.USER_PERMISSIONS_CACHE_TTL == USER_PERMISSIONS.ttl <= 300


def test_second_call_is_served_from_cache_and_stays_a_set(env):
    first = sel.get_user_permission_codenames(user=USER)
    second = sel.get_user_permission_codenames(user=USER)
    assert isinstance(second, set) and second == first
    assert env == ["u1"]
    assert metrics.snapshot()["authz.user_perms"] == {"miss": 1, "hit": 1}


def test_user_of_another_company_is_never_cached(env):
    outsider = SimpleNamespace(id="u2", company_id="c2")
    sel.get_user_permission_codenames(user=outsider)
    sel.get_user_permission_codenames(user=outsider)
    assert env == ["u2", "u2"]


def test_no_tenant_means_no_caching(env, monkeypatch):
    def no_tenant():
        raise AppPermissionDeniedError(message="No company context.")

    monkeypatch.setattr(sel, "current_tenant_scope", no_tenant)
    sel.get_user_permission_codenames(user=USER)
    sel.get_user_permission_codenames(user=USER)
    assert env == ["u1", "u1"]


@pytest.mark.django_db
def test_revoking_clears_the_entry_only_at_commit(env, django_capture_on_commit_callbacks):
    sel.get_user_permission_codenames(user=USER)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        sel.invalidate_user_permissions_cache(user_id="u1")
        sel.get_user_permission_codenames(user=USER)  # still the cached value inside the transaction
    assert env == ["u1"]
    callbacks[0]()
    sel.get_user_permission_codenames(user=USER)
    assert env == ["u1", "u1"]
