"""Schema-level isolation, and the guards for wrong-site and no-company requests.

Layer 1  the database: each company's rows live in their own schema.
Layer 2  the guards: what happens when a user is presented on the wrong site, or when
         there is no company context at all.
Layer 3  real HTTP requests through the full middleware stack (Host -> Domain -> Company
         -> search_path), including the session-cookie replay attack.

Every test that asserts "was rejected" also asserts the rejection came from the guard we
mean (by its message), and a canary proves the check can actually see that guard.
"""
from __future__ import annotations

import json

import pytest
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import Client
from django_tenants.utils import tenant_context

from lrb.accounts.models import User
from lrb.company.services.create_company import create_company
from lrb.core.exceptions import AppPermissionDeniedError
from lrb.core.tenancy import (
    assert_user_in_current_tenant,
    get_current_tenant,
    require_public_schema,
)
from lrb.products.models import Product

from .conftest import PASSWORD, PUBLIC
from .helpers import error_messages, state

pytestmark = pytest.mark.django_db

NO_COMPANY_CONTEXT = "No company context."

# Queries a company member runs all day. On the wrong site none may return anything.
READ_QUERIES = {
    "products": "{ products(limit: 100) { items { id } } }",
    "users": "{ users(limit: 100) { items { id } } }",
    "roles": "{ roles { id } }",
    "company": "{ company { name } }",
    "dashboard": "{ dashboard { __typename } }",
}


# --------------------------------------------------------------------------- #
# Layer 1: the database                                                        #
# --------------------------------------------------------------------------- #
def _tenant_app_configs():
    wanted = {entry.split(".apps.")[0] for entry in settings.TENANT_APPS} | set(settings.TENANT_APPS)
    return [cfg for cfg in apps.get_app_configs() if cfg.name in wanted]


def _tenant_models_with_company_fk():
    found = []
    for cfg in _tenant_app_configs():
        for model in cfg.get_models():
            if any(f.name == "company" and f.many_to_one for f in model._meta.get_fields()):
                found.append(model)
    return found


def test_the_check_below_actually_covers_the_core_tables():
    # Vacuity guard for the generic test that follows.
    labels = {m._meta.label for m in _tenant_models_with_company_fk()}
    assert {"products.Product", "authorization.Role", "accounts.User"} <= labels, labels


def test_no_row_in_a_company_schema_belongs_to_another_company(w):
    """Generic: walks EVERY tenant model that has a `company` foreign key, so a model added
    next year is covered without anyone remembering to add a test."""
    for company in (w.a, w.b):
        with tenant_context(company):
            for model in _tenant_models_with_company_fk():
                strangers = model.objects.exclude(company_id=company.pk)
                assert not strangers.exists(), f"{model._meta.label} in {company.schema_name} holds another company's rows"


def test_each_company_schema_really_contains_its_own_data(w):
    for company in (w.a, w.b):
        with tenant_context(company):
            assert Product.objects.filter(company_id=company.pk).exists()
            assert User.objects.filter(company_id=company.pk).count() >= 2


def test_company_b_rows_do_not_exist_in_company_a_schema_and_vice_versa(w):
    with tenant_context(w.a):
        assert not Product.objects.filter(pk=w.product_b.pk).exists()
        assert not User.objects.filter(pk__in=[w.owner_b.pk, w.staff_b.pk]).exists()
    with tenant_context(w.b):
        assert not Product.objects.filter(pk=w.product_a.pk).exists()
        assert not User.objects.filter(pk__in=[w.owner_a.pk, w.staff_a.pk]).exists()


def _current_schema() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        return cursor.fetchone()[0]


def test_tenant_context_switches_the_real_search_path_and_restores_it(w):
    assert _current_schema() == "public"
    with tenant_context(w.a):
        assert _current_schema() == w.a.schema_name
        with tenant_context(w.b):
            assert _current_schema() == w.b.schema_name
        assert _current_schema() == w.a.schema_name
    assert _current_schema() == "public"


def test_snapshots_see_changes_made_inside_the_rows_own_schema(w):
    """The attack suite is only as good as its watchers. If `state()` read the wrong
    schema it would report DELETED both before and after, and hide a real modification."""
    before = state(w.product_b, "name")
    with tenant_context(w.b):
        Product.objects.filter(pk=w.product_b.pk).update(name="CHANGED")
    assert state(w.product_b, "name") != before
    assert state(w.product_b, "name") == {"name": "CHANGED"}
    with tenant_context(w.b):
        Product.objects.filter(pk=w.product_b.pk).delete()
    assert state(w.product_b, "name") == "DELETED"


# --------------------------------------------------------------------------- #
# Layer 2a: a user presented on the WRONG company's site                       #
# --------------------------------------------------------------------------- #
def test_lock_two_rejects_a_user_from_another_company(w):
    with tenant_context(w.a):
        assert_user_in_current_tenant(w.owner_a)  # right site: passes
    with tenant_context(w.b):
        with pytest.raises(AppPermissionDeniedError, match=NO_COMPANY_CONTEXT):
            assert_user_in_current_tenant(w.owner_a)
    with tenant_context(w.a):
        with pytest.raises(AppPermissionDeniedError, match=NO_COMPANY_CONTEXT):
            assert_user_in_current_tenant(w.owner_b)


@pytest.mark.parametrize("actor_name", ["owner_a", "staff_a"])
@pytest.mark.parametrize("query_name", list(READ_QUERIES))
def test_a_user_on_the_wrong_site_is_rejected_by_lock_two_and_sees_nothing(w, actor_name, query_name):
    result = w.run(getattr(w, actor_name), READ_QUERIES[query_name], host=w.b)
    assert any(NO_COMPANY_CONTEXT in m for m in error_messages(result)), error_messages(result)
    leaked = json.dumps(result.data or {})
    assert str(w.product_b.id) not in leaked and str(w.owner_b.id) not in leaked
    assert w.b.name not in leaked


def test_canary_these_checks_can_see_lock_two(w, monkeypatch):
    """Switch lock two off. The rejection message must vanish (so the tests above really
    are watching that lock), while the company_id filter still keeps B's data hidden:
    two independent layers, and we can tell them apart."""
    import lrb.core.tenancy as tenancy

    monkeypatch.setattr(tenancy, "assert_user_in_current_tenant", lambda user: None)
    result = w.run(w.owner_a, READ_QUERIES["products"], host=w.b)
    assert not any(NO_COMPANY_CONTEXT in m for m in error_messages(result))
    assert str(w.product_b.id) not in json.dumps(result.data or {})  # second layer still holds


# --------------------------------------------------------------------------- #
# Layer 2b: NO company context at all                                          #
# --------------------------------------------------------------------------- #
def test_the_platform_site_has_no_company_context(w):
    with w.on_public():
        with pytest.raises(AppPermissionDeniedError, match=NO_COMPANY_CONTEXT):
            get_current_tenant()


@pytest.mark.parametrize("actor_name", ["owner_a", "staff_a"])
@pytest.mark.parametrize("query_name", list(READ_QUERIES))
def test_a_company_user_gets_nothing_on_the_platform_site(w, actor_name, query_name):
    result = w.run(getattr(w, actor_name), READ_QUERIES[query_name], host=PUBLIC)
    assert any(NO_COMPANY_CONTEXT in m for m in error_messages(result)), error_messages(result)
    leaked = json.dumps(result.data or {})
    assert str(w.product_a.id) not in leaked and w.a.name not in leaked


def test_a_platform_operator_gets_nothing_on_a_company_site(w):
    """A user with no company (a platform operator, living in the public schema)."""
    with w.on_public():
        operator = User.objects.create_user(email="operator@platform.test", password=PASSWORD)
    for host in (w.a, w.b):
        result = w.run(operator, READ_QUERIES["products"], host=host)
        assert any(NO_COMPANY_CONTEXT in m for m in error_messages(result)), error_messages(result)
        assert result.data in (None, {"products": None})


def test_platform_only_operations_are_unavailable_on_a_company_site(w):
    with w.on_public():
        require_public_schema()  # fine on the platform site
    with tenant_context(w.a):
        with pytest.raises(AppPermissionDeniedError):
            require_public_schema()
        with pytest.raises(AppPermissionDeniedError):
            create_company(
                name="Sneaky", slug="sneaky-co", email="sneaky@company.test", phone="+254700000009",
                country="KE", city="Nairobi", address="x",
            )


# --------------------------------------------------------------------------- #
# Layer 3: real HTTP through the full middleware stack                         #
# --------------------------------------------------------------------------- #
@pytest.fixture
def any_host(settings):
    settings.ALLOWED_HOSTS = ["*"]


def _host(company) -> str:
    return company.get_primary_domain().domain


def _post(client, host, query, *, preflight=True):
    extra = {"HTTP_HOST": host}
    if preflight:
        extra["HTTP_APOLLO_REQUIRE_PREFLIGHT"] = "true"  # Apollo-Require-Preflight
    return client.post(
        "/graphql/", data=json.dumps({"query": query}), content_type="application/json", **extra
    )


def _body(response) -> dict:
    return json.loads(response.content)


def test_http_a_logged_in_user_works_on_their_own_company_site(w, any_host):
    client = Client()
    with tenant_context(w.a):
        client.force_login(w.owner_a)
    response = _post(client, _host(w.a), READ_QUERIES["company"])
    assert response.status_code == 200
    assert _body(response)["data"]["company"]["name"] == w.a.name


def test_http_a_session_cookie_from_company_A_is_anonymous_on_company_B(w, any_host):
    """The real attack: take the cookie you got on A's site and send it to B's site.
    Sessions are stored per schema, so B's site has never heard of it.

    Deliberately independent of the error wording: some resolvers say "Authentication
    required." and others "No company context." for an anonymous visitor. What matters is
    that the cookie buys nothing: B answers exactly as it does for someone with no cookie."""
    client = Client()
    with tenant_context(w.a):
        client.force_login(w.owner_a)
    assert client.cookies, "force_login should have set a session cookie"

    on_a = _body(_post(client, _host(w.a), READ_QUERIES["company"]))
    assert on_a["data"]["company"]["name"] == w.a.name  # the cookie is genuine...

    response_b = _post(client, _host(w.b), READ_QUERIES["company"])  # ...but useless on B
    # Wording-independent proof: Django never authenticated anybody on B's site. (If sessions
    # ever became shareable between schemas, this fails even when the tenant lock still
    # hides the data, which a changed error message alone could not show on every resolver.)
    assert not response_b.wsgi_request.user.is_authenticated
    on_b = _body(response_b)
    assert on_b.get("errors"), on_b
    assert not (on_b.get("data") or {}).get("company")
    assert w.a.name not in json.dumps(on_b) and w.b.name not in json.dumps(on_b)

    nobody = _body(_post(Client(), _host(w.b), READ_QUERIES["company"]))  # no cookie at all
    assert on_b == nobody, "the cookie from company A changed B's answer: it gave A's user some standing on B"


def _post_safely(client, host, query, **kwargs):
    """(status, body). status is None when the ERROR PAGE itself crashed while Django was
    answering 403/404 (for example a 403.html that reverses a URL the tenant site lacks).
    Security assertions below must hold either way, so they use this."""
    try:
        response = _post(client, host, query, **kwargs)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        return None, f"{type(exc).__name__}: {exc}"
    return response.status_code, response.content.decode(errors="replace")


# If these two fail, Django is crashing while rendering its 403/404 page again (typically an error
# template calling {% url 'home' %} when the tenant URLconf has no 'home' route), so visitors get a
# raw server error. Access is still denied either way; only the response is wrong. The fix is
# handler403 / handler404 in the tenant URLconf that return a small JsonResponse.


def test_http_an_unknown_host_serves_no_company_data(w, any_host):
    status, body = _post_safely(Client(), "nobody.example.test", READ_QUERIES["company"])
    assert status is None or status >= 400, (status, body[:200])
    assert w.a.name not in body and w.b.name not in body and '"data"' not in body


def test_http_an_unknown_host_gets_a_clean_404(w, any_host):
    status, body = _post_safely(Client(), "nobody.example.test", READ_QUERIES["company"])
    assert status == 404, (status, body[:200])


def test_http_graphql_requires_the_preflight_header(w, any_host):
    response = _post(Client(), _host(w.a), READ_QUERIES["company"], preflight=False)
    assert response.status_code == 403


def test_http_a_deactivated_company_is_blocked_before_any_resolver_runs(w, any_host):
    client = Client()
    with tenant_context(w.a):
        client.force_login(w.owner_a)
    w.a.is_active = False
    w.a.save(update_fields=["is_active"])
    status, body = _post_safely(client, _host(w.a), READ_QUERIES["company"])
    assert status is None or status >= 400, (status, body[:200])  # blocked...
    assert '"data"' not in body and w.a.name not in body  # ...before GraphQL ran at all
    # ...and the other company is unaffected.
    other = Client()
    with tenant_context(w.b):
        other.force_login(w.owner_b)
    assert _post(other, _host(w.b), READ_QUERIES["company"]).status_code == 200


def test_http_a_deactivated_company_gets_a_clean_403(w, any_host):
    client = Client()
    with tenant_context(w.a):
        client.force_login(w.owner_a)
    w.a.is_active = False
    w.a.save(update_fields=["is_active"])
    status, body = _post_safely(client, _host(w.a), READ_QUERIES["company"])
    assert status == 403, (status, body[:200])