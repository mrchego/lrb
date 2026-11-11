"""Tests for the global cache foundation (step 1 + 2)."""
import pickle

import pytest
from django.core.cache import cache, caches
from django.core.cache.backends.redis import RedisCache

from lrb.core.cache import build_key, delete_after_commit
from lrb.core.cache.serializers import JSONSerializer
from lrb.core.exceptions import AppPermissionDeniedError


# ---- serializer: plain data only, never pickle ----------------------------

@pytest.mark.parametrize(
    "value", [1, 0, -5, 1.5, "text", "123", True, False, None, [], ["a", "b"], {"a": [1, 2]}]
)
def test_serializer_round_trip(value):
    s = JSONSerializer()
    assert s.loads(s.dumps(value)) == value


def test_serializer_keeps_bool_and_int_apart():
    s = JSONSerializer()
    assert s.loads(s.dumps(True)) is True
    assert s.loads(s.dumps(1)) == 1 and s.loads(s.dumps(1)) is not True


def test_serializer_rejects_sets():
    with pytest.raises(TypeError):
        JSONSerializer().dumps({"a", "b"})


def test_serializer_never_unpickles():
    # An attacker who can write to Redis must not be able to run code.
    with pytest.raises(ValueError):
        JSONSerializer().loads(pickle.dumps({"x": 1}))


# ---- keys ------------------------------------------------------------------

def test_key_contains_namespace_company_and_parts():
    assert build_key(namespace="authz.user_perms", company_id="c1", parts=["u1"]) == (
        "authz.user_perms:c1:u1"
    )


@pytest.mark.parametrize("company_id", [None, ""])
def test_key_requires_company(company_id):
    with pytest.raises(AppPermissionDeniedError):
        build_key(namespace="n", company_id=company_id, parts=["x"])


@pytest.mark.parametrize("bad", ["a:b", "has space", "", "x" * 200, "../etc"])
def test_key_rejects_unsafe_parts(bad):
    with pytest.raises(ValueError):
        build_key(namespace="n", company_id="c1", parts=[bad])


def test_different_companies_never_share_a_key():
    a = build_key(namespace="n", company_id="A", parts=["u"])
    b = build_key(namespace="n", company_id="B", parts=["u"])
    assert a != b


# ---- invalidation waits for commit ----------------------------------------

@pytest.mark.django_db
def test_delete_waits_for_commit(django_capture_on_commit_callbacks):
    cache.set("k-commit", [1])
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        delete_after_commit(keys=["k-commit"])
        assert cache.get("k-commit") == [1]  # still there inside the transaction
    assert len(callbacks) == 1
    callbacks[0]()
    assert cache.get("k-commit") is None


@pytest.mark.django_db
def test_rollback_keeps_cache(django_capture_on_commit_callbacks):
    cache.set("k-rollback", [1])
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        delete_after_commit(keys=["k-rollback"])
    # transaction rolled back => callbacks never executed => entry untouched
    assert cache.get("k-rollback") == [1]
    assert len(callbacks) == 1


# ---- needs a real Redis (skipped when tests use LocMemCache) ---------------

redis_only = pytest.mark.skipif(
    not isinstance(caches["default"], RedisCache), reason="cache backend is not Redis"
)


@redis_only
def test_two_independent_clients_share_state():
    """Stands in for two gunicorn workers: separate clients, no shared memory."""
    worker_a = caches.create_connection("default")
    worker_b = caches.create_connection("default")
    worker_a.set("shared-k", ["perm.a"], timeout=30)
    assert worker_b.get("shared-k") == ["perm.a"]
    worker_a.delete("shared-k")  # a revoke handled by worker A ...
    assert worker_b.get("shared-k") is None  # ... is seen by worker B
