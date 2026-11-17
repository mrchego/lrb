"""Invalidation for models that live in the shared (public) schema but hold per-company data."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from lrb.core.cache import invalidation as inv
from lrb.core.cache.policies import CachePolicy, Consistency

POLICY = CachePolicy(
    name="demo.shared", owner="demo", consistency=Consistency.BOUNDED_STALE,
    ttl=60, description="d", loader="demo.loaders.x",
)


def _rule(flag: bool):
    return inv._ModelRule(
        model="x.Thing", policies=(POLICY,), company_field="company_id", schema_from_company=flag
    )


@pytest.fixture
def invalidated(monkeypatch):
    calls = []
    monkeypatch.setattr(inv, "invalidate_policy", lambda **kw: calls.append(kw))
    return calls


def test_a_flagged_rule_targets_the_companys_own_schema(invalidated):
    instance = SimpleNamespace(company_id="c1", company=SimpleNamespace(schema_name="t_acme"))
    inv._make_handler(_rule(True))(sender=None, instance=instance)
    assert invalidated == [{"policy": POLICY, "company_id": "c1", "schema_name": "t_acme"}]


def test_an_unflagged_rule_uses_the_schema_active_at_save_time(invalidated):
    instance = SimpleNamespace(company_id="c1", company=SimpleNamespace(schema_name="t_acme"))
    inv._make_handler(_rule(False))(sender=None, instance=instance)
    assert invalidated[0]["schema_name"] is None  # tenant-schema models: current schema IS right


def test_the_schema_is_looked_up_when_the_relation_is_not_loaded(monkeypatch):
    class FakeTenants:
        objects = SimpleNamespace(
            filter=lambda **kw: SimpleNamespace(
                values_list=lambda *a, **k: SimpleNamespace(first=lambda: "t_looked_up")
            )
        )

    import django_tenants.utils as tenant_utils

    monkeypatch.setattr(tenant_utils, "get_tenant_model", lambda: FakeTenants)
    schema = inv._schema_of_company(SimpleNamespace(company_id="c1"), _rule(True), "c1")
    assert schema == "t_looked_up"


@pytest.fixture
def recorded(monkeypatch):
    log = {"entered": [], "deleted_inside": []}
    state = {"inside": None}

    @contextmanager
    def fake_schema_context(name):
        log["entered"].append(name)
        state["inside"] = name
        try:
            yield
        finally:
            state["inside"] = None

    monkeypatch.setattr(inv, "schema_context", fake_schema_context)
    monkeypatch.setattr(
        inv, "cache_delete_many", lambda keys: log["deleted_inside"].append((list(keys), state["inside"])) or True
    )
    return log


@pytest.mark.django_db
def test_delete_runs_under_the_requested_schema_even_when_another_is_active(
    recorded, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        inv.delete_after_commit(keys=["k1"], schema_name="t_company_schema")
    assert recorded["entered"] == ["t_company_schema"]
    assert recorded["deleted_inside"] == [(["k1"], "t_company_schema")]


@pytest.mark.django_db
def test_without_an_explicit_schema_nothing_is_switched(recorded, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        inv.delete_after_commit(keys=["k1"])
    assert recorded["entered"] == []  # same schema as at registration: delete directly
    assert recorded["deleted_inside"] == [(["k1"], None)]