"""Dashboard stats cache against the shared two-company world (real schemas, Postgres).

Uses the same `w` world as the rest of this package: no per-test schema creation and no
transaction=True (its flush would destroy the shared world). `django_capture_on_commit_callbacks`
stands in for the commit, so the on_commit invalidation runs exactly where a real commit would
run it: after the request's work, outside the company's tenant_context.
"""
import pytest
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save
from django_tenants.utils import tenant_context

from lrb.core.cache import metrics
from lrb.core.cache.tasks import refresh_cache_entry
from lrb.dashboard.selectors.cached_stats import get_cached_product_stats
from lrb.products.models import Product

pytestmark = pytest.mark.django_db


def _stats(company):
    with tenant_context(company):
        return get_cached_product_stats(company_id=str(company.pk))


@pytest.fixture(autouse=True)
def _clean_cache_and_metrics():
    cache.clear()
    metrics.reset()


def test_product_saves_are_wired_to_the_dashboard_policy():
    assert post_save.has_listeners(Product)


def test_stats_are_cached_per_company_and_cleared_when_a_product_is_written(
    w, django_capture_on_commit_callbacks
):
    a1, b1 = _stats(w.a), _stats(w.b)
    assert (a1["total"], b1["total"]) == (1, 1)  # each company sees only its own product

    _stats(w.a)  # second read
    assert metrics.snapshot()["dashboard.product_stats"]["hit"] == 1  # served from the cache

    # The product is written inside A's schema, but the commit (and so the invalidation) happens
    # after we have left it: the delete must still hit the key that was cached under A's schema.
    with django_capture_on_commit_callbacks(execute=True):
        w.new_product(w.a)

    assert _stats(w.a)["total"] == 2  # company A's entry was cleared by the product write
    assert _stats(w.b) == b1  # company B's entry was neither touched nor mixed up


def test_a_rolled_back_write_leaves_the_cache_alone(w, django_capture_on_commit_callbacks):
    before = _stats(w.a)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        w.new_product(w.a)
    assert callbacks  # the write DID schedule an invalidation...
    # ...but it never ran (a rollback discards on_commit callbacks), so the entry is still served.
    assert _stats(w.a) == before


def test_a_write_in_company_A_never_clears_company_B(w, django_capture_on_commit_callbacks):
    _stats(w.b)
    metrics.reset()
    with django_capture_on_commit_callbacks(execute=True):
        w.new_product(w.a)
    _stats(w.b)
    snap = metrics.snapshot()["dashboard.product_stats"]
    assert snap.get("hit") == 1 and "miss" not in snap  # B was still cached


def test_background_refresh_writes_where_the_request_will_read(w):
    # Exactly what the Celery worker runs (calling a task object runs it in-process).
    refresh_cache_entry(
        policy_name="dashboard.product_stats", company_id=str(w.a.pk), params={}, lock_token="t"
    )
    result = _stats(w.a)  # the web request afterwards

    snap = metrics.snapshot()["dashboard.product_stats"]
    assert result["total"] == 1
    assert snap.get("hit") == 1 and "miss" not in snap  # found what the task stored