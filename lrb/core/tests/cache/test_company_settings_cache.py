"""Company settings cache on the shared two-company world (real schemas, Postgres)."""
import json

import pytest
from django.core.cache import cache
from django_tenants.utils import tenant_context

from lrb.company.models.settings import CompanySettings
from lrb.company.selectors.get_cached_company_settings import get_cached_company_settings
from lrb.company.selectors.get_company_settings_snapshot import (
    SNAPSHOT_FIELDS,
    get_company_settings_snapshot,
)
from lrb.company.services.update_company_settings import update_company_settings
from lrb.core.cache import metrics
from lrb.core.exceptions import ApplicationError, ErrorCode

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean():
    cache.clear()
    metrics.reset()


def _read(company):
    """What a request on that company's site does."""
    with tenant_context(company):
        return get_cached_company_settings(company_id=str(company.pk))


def test_the_snapshot_is_plain_strings_matching_the_database(w):
    snapshot = get_company_settings_snapshot(company_id=str(w.a.pk))
    assert set(snapshot) == set(SNAPSHOT_FIELDS)
    assert all(isinstance(v, str) for v in snapshot.values())
    json.dumps(snapshot)  # the cache stores JSON: this must not raise
    row = CompanySettings.objects.get(company=w.a)
    assert snapshot == {name: getattr(row, name) for name in SNAPSHOT_FIELDS}


def test_the_snapshot_covers_every_text_setting():
    """Fails when someone adds a text setting to CompanySettings and forgets the snapshot, so
    a setting never silently goes missing from cached reads (or into the cache unreviewed)."""
    text_fields = {
        f.name for f in CompanySettings._meta.concrete_fields if f.get_internal_type() == "CharField"
    }
    assert text_fields == set(SNAPSHOT_FIELDS), (
        f"CompanySettings text fields {sorted(text_fields)} != SNAPSHOT_FIELDS "
        f"{sorted(SNAPSHOT_FIELDS)}: add the new field to SNAPSHOT_FIELDS (or change this test "
        "to exclude it on purpose)."
    )


def test_the_second_read_is_served_from_the_cache(w):
    first, second = _read(w.a), _read(w.a)
    assert first == second
    snap = metrics.snapshot()["company.settings"]
    assert snap["loaded"] == 1 and snap["hit"] == 1


def test_an_owner_edit_on_the_company_site_is_visible_on_the_next_read(
    w, django_capture_on_commit_callbacks
):
    assert _read(w.a)["currency"] == "KES"
    with django_capture_on_commit_callbacks(execute=True):
        with tenant_context(w.a):
            update_company_settings(company=w.a, currency="EUR")
    assert _read(w.a)["currency"] == "EUR"


def test_a_platform_admin_edit_from_the_public_schema_clears_the_companys_entry(
    w, django_capture_on_commit_callbacks
):
    """The entry was cached under company A's schema; an admin saves the row while the PUBLIC
    schema is active (Django admin). Without schema_from_company the delete would use the wrong
    key prefix and A would keep the old value until the TTL ran out."""
    assert _read(w.a)["timezone"] == "UTC"
    with django_capture_on_commit_callbacks(execute=True):
        with w.on_public():
            row = CompanySettings.objects.get(company=w.a)
            row.timezone = "Africa/Nairobi"
            row.save()
    assert _read(w.a)["timezone"] == "Africa/Nairobi"


def test_one_companys_edit_never_clears_or_leaks_into_the_other(w, django_capture_on_commit_callbacks):
    _read(w.a), _read(w.b)
    metrics.reset()
    with django_capture_on_commit_callbacks(execute=True):
        with w.on_public():
            row = CompanySettings.objects.get(company=w.b)
            row.currency = "GBP"
            row.save()
    assert _read(w.a)["currency"] != "GBP"  # A: still cached, untouched
    assert metrics.snapshot()["company.settings"].get("hit") == 1
    assert _read(w.b)["currency"] == "GBP"  # B: recomputed


def test_a_missing_settings_row_is_a_company_not_found_error(w, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        CompanySettings.objects.filter(company=w.a).delete()
    with pytest.raises(ApplicationError) as exc:
        _read(w.a)
    assert exc.value.code == ErrorCode.COMPANY_NOT_FOUND