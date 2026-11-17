import json
import threading
import time
from types import SimpleNamespace

import pytest
import strawberry
from django.http import JsonResponse
from django.test import RequestFactory

from lrb.core.ratelimit import identity, policies
from lrb.core.ratelimit.graphql import RateLimitExtension
from lrb.core.middleware import RateLimitMiddleware
from lrb.core.ratelimit.policies import B, Concurrency, Layer, Policy, Window, OperationRule

COMPANY_A = SimpleNamespace(pk="aaaaaaaa-0000-0000-0000-000000000001", schema_name="t_a")
COMPANY_B = SimpleNamespace(pk="bbbbbbbb-0000-0000-0000-000000000002", schema_name="t_b")
PUBLIC = SimpleNamespace(pk=1, schema_name="public")

HELD = threading.Event(); RELEASE = threading.Event(); RAN = []


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.type
class Payload:
    ok: bool


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "hi"

    @strawberry.field
    def dashboard(self) -> str:
        return "d"


@strawberry.type
class Mutation:
    @strawberry.mutation
    def login(self, input: LoginInput) -> Payload:
        RAN.append("login"); return Payload(ok=True)

    @strawberry.mutation
    def forgot_password(self, input: LoginInput) -> Payload:
        RAN.append("forgot"); return Payload(ok=True)

    @strawberry.mutation
    def bulk_lock_users(self) -> Payload:
        RAN.append("bulk"); HELD.set(); RELEASE.wait(5); return Payload(ok=True)

    @strawberry.mutation
    def create_thing(self) -> Payload:
        RAN.append("thing"); return Payload(ok=True)

    @strawberry.mutation
    def other_thing(self) -> Payload:
        RAN.append("other"); return Payload(ok=True)


schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[RateLimitExtension])


def call(doc, *, tenant=COMPANY_A, ip="198.51.100.5", user=None, variables=None, mw=True):
    rf = RequestFactory()
    req = rf.post("/graphql/", REMOTE_ADDR=ip)
    req.tenant = tenant
    req.user = user or SimpleNamespace(is_authenticated=False)

    def view(request):
        res = schema.execute_sync(doc, variable_values=variables, context_value=SimpleNamespace(request=request))
        body = {"data": res.data}
        if res.errors:
            body["errors"] = [{"message": e.message, "extensions": e.extensions} for e in res.errors]
        return JsonResponse(body)

    resp = RateLimitMiddleware(view)(req)
    return resp, json.loads(resp.content)


LOGIN = 'mutation($e:String!){ login(input:{email:$e,password:"x"}){ ok } }'


def user(n):
    return SimpleNamespace(is_authenticated=True, pk=n)


@pytest.fixture(autouse=True)
def clean_registry():
    saved = (policies.POLICIES, policies.OPERATIONS)
    RAN.clear(); HELD.clear(); RELEASE.clear()
    yield
    policies.POLICIES, policies.OPERATIONS = saved
    import lrb.core.ratelimit.engine as eng, lrb.core.ratelimit.graphql as g
    eng.POLICIES = g.POLICIES = policies.POLICIES


def patch(policies_=None, ops=None):
    import lrb.core.ratelimit.engine as eng, lrb.core.ratelimit.graphql as g
    if policies_:
        policies.POLICIES = {**policies.POLICIES, **{p.name: p for p in policies_}}
    if ops:
        policies.OPERATIONS = {**policies.OPERATIONS, **ops}
    eng.POLICIES = g.POLICIES = policies.POLICIES


def test_login_is_limited_per_email_with_429_and_headers():
    for _ in range(5):
        resp, body = call(LOGIN, variables={"e": "Victim@Example.com"})
        assert resp.status_code == 200 and body["data"]["login"]["ok"]
    resp, body = call(LOGIN, variables={"e": " victim@example.com "})     # same mailbox, different casing
    assert resp.status_code == 429
    assert body["errors"][0]["extensions"]["code"] == "RATE_LIMITED"
    assert int(resp["Retry-After"]) >= 1 and body["errors"][0]["extensions"]["retryAfter"] >= 1
    assert RAN.count("login") == 5
    # another mailbox from the same IP still works
    resp, _ = call(LOGIN, variables={"e": "other@example.com"})
    assert resp.status_code == 200


def test_login_limits_do_not_cross_companies():
    for _ in range(5): call(LOGIN, variables={"e": "x@y.com"}, tenant=COMPANY_A)
    assert call(LOGIN, variables={"e": "x@y.com"}, tenant=COMPANY_A)[0].status_code == 429
    assert call(LOGIN, variables={"e": "x@y.com"}, tenant=COMPANY_B)[0].status_code == 200


def test_public_site_is_its_own_scope():
    assert identity.company_scope(SimpleNamespace(tenant=PUBLIC)) == "platform"
    assert identity.company_scope(SimpleNamespace(tenant=COMPANY_A)) == COMPANY_A.pk


def test_success_headers_present():
    resp, _ = call("{ hello }", user=user(1))
    assert resp.status_code == 200
    assert resp["X-RateLimit-Limit"] and resp["X-RateLimit-Remaining"] and resp["X-RateLimit-Reset"]
    assert "Retry-After" not in resp


def test_weighted_cost_dashboard_vs_hello():
    patch([Policy("api", (Layer("actor", B(10, 1, 3600)),))])
    assert call("{ dashboard }", user=user(7))[0].status_code == 200      # cost 5
    assert call("{ dashboard }", user=user(7))[0].status_code == 200      # cost 5 -> 0 left
    resp, body = call("{ hello }", user=user(7))
    assert resp.status_code == 429
    assert call("{ hello }", user=user(8))[0].status_code == 200          # other user unaffected


def test_mutation_batch_is_all_or_nothing_after_first_rejection():
    patch([Policy("api", (Layer("actor", B(1, 1, 3600)),))])
    resp, body = call("mutation{ createThing{ok} otherThing{ok} }", user=user(1))   # first field costs 2 > 1
    assert resp.status_code == 429
    assert RAN == []                                          # the 2nd field was NOT run either                                          # nothing executed, safe to retry whole request


def test_partial_batch_keeps_200_but_reports_error():
    patch([Policy("api", (Layer("actor", B(3, 1, 3600)),))])
    resp, body = call("mutation{ createThing{ok} otherThing{ok} }", user=user(2))   # 2 ok, then 2 > 1 left
    assert RAN == ["thing"]
    assert resp.status_code == 200 and body["errors"][0]["extensions"]["code"] == "RATE_LIMITED"


def test_http_layer_blocks_before_graphql_runs():
    patch([Policy("http", (Layer("ip", B(3, 1, 3600)),))])
    for _ in range(3): assert call("{ hello }", user=user(1))[0].status_code == 200
    resp, body = call("{ hello }", user=user(1))
    assert resp.status_code == 429 and body["errors"][0]["extensions"]["code"] == "RATE_LIMITED"


def test_concurrency_limit_on_heavy_ops():
    patch([Policy("heavy", (Layer("actor", B(100, 100)),), failure="local", concurrency=Concurrency(max=1))])
    results = {}
    t = threading.Thread(target=lambda: results.update(first=call("mutation{ bulkLockUsers{ok} }", user=user(1))))
    t.start(); assert HELD.wait(3)
    resp, body = call("mutation{ bulkLockUsers{ok} }", user=user(2))      # same company, slot taken
    assert resp.status_code == 429 and body["errors"][0]["extensions"]["retryAfter"] == 5
    RELEASE.set(); t.join()
    assert results["first"][0].status_code == 200
    assert call("mutation{ bulkLockUsers{ok} }", user=user(3))[0].status_code == 200   # slot released


def test_spoofed_forwarded_header_cannot_evade_limits(settings):
    patch([Policy("api", (Layer("actor", B(2, 1, 3600)),))])
    rf = RequestFactory()
    def req(xff):
        r = rf.post("/graphql/", REMOTE_ADDR="198.51.100.9", HTTP_X_FORWARDED_FOR=xff); r.tenant = COMPANY_A
        r.user = SimpleNamespace(is_authenticated=False); return r
    assert identity.client_ip(req("1.2.3.4")) == "198.51.100.9"           # header ignored by default
    settings.RATE_LIMIT_TRUSTED_PROXY_COUNT = 1
    assert identity.client_ip(req("6.6.6.6, 203.0.113.50")) == "203.0.113.50"   # the hop our proxy added
    settings.RATE_LIMIT_TRUSTED_PROXY_COUNT = 2
    assert identity.client_ip(req("6.6.6.6, 203.0.113.50")) == "6.6.6.6"
    assert identity.client_ip(req("garbage, nonsense")) == "198.51.100.9"  # invalid -> falls back


def test_ipv6_grouped_by_64_and_v4_mapped():
    r = lambda a: SimpleNamespace(META={"REMOTE_ADDR": a})
    assert identity.client_ip(r("2001:db8:1:2:aaaa::1")) == identity.client_ip(r("2001:db8:1:2:bbbb::9"))
    assert identity.client_ip(r("::ffff:203.0.113.9")) == "203.0.113.9"
    assert identity.client_ip(r("")) == "unknown"


def test_static_paths_exempt(settings):
    settings.STATIC_URL = "/static/"
    patch([Policy("http", (Layer("ip", B(1, 1, 3600)),))])
    rf = RequestFactory()
    mw = RateLimitMiddleware(lambda r: JsonResponse({}))
    for _ in range(5):
        r = rf.get("/static/app.js", REMOTE_ADDR="198.51.100.5"); r.tenant = COMPANY_A
        assert mw(r).status_code == 200


def test_introspection_and_off_mode_not_limited(settings):
    settings.RATE_LIMIT_MODE = "off"
    for _ in range(20): assert call(LOGIN, variables={"e": "a@b.c"})[0].status_code == 200
