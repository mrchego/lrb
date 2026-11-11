"""Fixtures for the cross-company isolation suite (one PostgreSQL schema per company).

The world is TWO complete companies (A and B), each in its own schema, built ONCE per test
session and committed, because creating a schema and running its migrations is slow.
Every test then runs inside the normal rolled-back `db` transaction, so anything a test
creates, changes or deletes disappears afterwards. `w` re-reads the base objects fresh
for each test, so an in-memory object that one test modified never leaks into the next.

Every builder and `w.run` switches to the right company schema itself, mirroring what
TenantMiddleware does for a real request (Host -> Domain -> Company -> search_path).

Do not use `transaction=True` in this package: its end-of-test flush would truncate the
committed Company rows and destroy the shared world. `World.load` fails loudly if that
ever happens.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context, tenant_context

from config.schema import schema
from lrb.accounts.models import User
from lrb.accounts.services.create_user import create_user
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.permissions import PERMISSION_REGISTRY
from lrb.authorization.services.create_role import create_role
from lrb.company.models.company import Company
from lrb.company.models.domain import Domain
from lrb.company.models.settings import CompanySettings
from lrb.company.services.create_company import create_company
from lrb.products.models import Product
from lrb.products.services.create_product import create_product
from lrb.staff.models import Invitation

PASSWORD = "Str0ng-Passw0rd!"
SLUG_PREFIX = "iso-"  # every company this suite creates; used to clean up leftovers

# Pass as `host=PUBLIC` to run a request on the platform (public-schema) site.
PUBLIC = object()


def _uid(prefix: str = "x") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- #
# Builders. Each one enters the company's own schema, like a real request would. #
# --------------------------------------------------------------------------- #
def new_company(label: str) -> Company:
    slug_part = uuid.uuid4().hex[:8]
    return create_company(  # public-schema only, as in production
        name=f"Company {label} {_uid()}",
        slug=f"{SLUG_PREFIX}{label.lower()}-{slug_part}",  # 3-42 chars, lowercase/digits/hyphens
        email=f"{_uid(label.lower())}@company.test",
        phone="+254700000001",
        country="KE",
        city="Nairobi",
        address="1 Test Street",
    )


def new_role(company, codenames):
    with tenant_context(company):
        return create_role(company=company, name=_uid("role"), permission_codenames=list(codenames))


def new_user(company, *, role=None, **flags):
    flags.setdefault("can_login", True)
    flags.setdefault("is_active", True)
    with tenant_context(company):
        user = create_user(
            email=f"{_uid('u')}@example.test",
            first_name="Test",
            last_name="User",
            password=PASSWORD,
            company=company,
            **flags,
        )
        if role is not None:
            UserRole.objects.create(user=user, role=role)
    return user


def new_product(company, *, is_active: bool = True):
    with tenant_context(company):
        return create_product(
            company=company,
            name="Widget",
            sku=_uid("sku"),
            price=Decimal("10.00"),
            is_active=is_active,
        )


# --------------------------------------------------------------------------- #
# The shared world: built once, committed, dropped at the end of the session.   #
# --------------------------------------------------------------------------- #
def _drop_company_data(company_ids, schema_names) -> None:
    """Remove schemas and the public rows describing them (no ORM cascade: see below)."""
    with connection.cursor() as cursor:
        for schema_name in schema_names:
            cursor.execute(f"DROP SCHEMA IF EXISTS {connection.ops.quote_name(schema_name)} CASCADE")
    # _raw_delete skips Django's cascade collector. company.delete() would try to cascade
    # into Product, Role, ... whose tables only exist inside company schemas.
    Domain.objects.filter(tenant_id__in=company_ids)._raw_delete("default")
    CompanySettings.objects.filter(company_id__in=company_ids)._raw_delete("default")
    Company.objects.filter(pk__in=company_ids)._raw_delete("default")


def _purge_leftovers() -> None:
    """A crashed earlier run (with --reuse-db) can leave companies behind."""
    old = list(Company.objects.filter(slug__startswith=SLUG_PREFIX).values_list("pk", "schema_name"))
    if old:
        _drop_company_data([pk for pk, _ in old], [schema for _, schema in old])


def _build_world() -> dict:
    a, b = new_company("A"), new_company("B")
    all_codenames = [codename for codename, _, _ in PERMISSION_REGISTRY]
    role_a = new_role(a, all_codenames)
    role_b = new_role(b, ["products.view_product"])
    # Company A: founder-owner + a staff member holding every permission.
    owner_a = new_user(a, is_superuser=True, is_founder=True)
    staff_a = new_user(a, role=role_a)
    product_a = new_product(a)
    # Company B: founder-owner + a staff member with a role.
    owner_b = new_user(b, is_superuser=True, is_founder=True)
    staff_b = new_user(b, role=role_b)
    product_b = new_product(b)
    return {
        "a": a.pk, "b": b.pk,
        "schemas": [a.schema_name, b.schema_name],
        "role_a": role_a.pk, "role_b": role_b.pk,
        "owner_a": owner_a.pk, "staff_a": staff_a.pk, "product_a": product_a.pk,
        "owner_b": owner_b.pk, "staff_b": staff_b.pk, "product_b": product_b.pk,
    }


@pytest.fixture(scope="session")
def tenant_world_ids(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        _purge_leftovers()
        ids = _build_world()
    yield ids
    with django_db_blocker.unblock():
        _drop_company_data([ids["a"], ids["b"]], ids["schemas"])


class World:
    """Fresh instances of the shared world's objects, plus tenant-aware helpers."""

    def __init__(self, ids: dict):
        if Company.objects.filter(pk__in=[ids["a"], ids["b"]]).count() != 2:
            pytest.fail(
                "The shared tenant world is gone. Something flushed the database "
                "(a transaction=True test?). Keep transaction=True out of this package."
            )
        self.a = Company.objects.get(pk=ids["a"])
        self.b = Company.objects.get(pk=ids["b"])
        with tenant_context(self.a):
            self.role_a = Role.objects.get(pk=ids["role_a"])
            self.owner_a = User.objects.get(pk=ids["owner_a"])
            self.staff_a = User.objects.get(pk=ids["staff_a"])
            self.product_a = Product.objects.get(pk=ids["product_a"])
        with tenant_context(self.b):
            self.role_b = Role.objects.get(pk=ids["role_b"])
            self.owner_b = User.objects.get(pk=ids["owner_b"])
            self.staff_b = User.objects.get(pk=ids["staff_b"])
            self.product_b = Product.objects.get(pk=ids["product_b"])

    # ---- builders ------------------------------------------------------------
    def new_company(self, label: str):
        return new_company(label)

    def new_role(self, company, codenames):
        return new_role(company, codenames)

    def new_user(self, company, *, role=None, **flags):
        return new_user(company, role=role, **flags)

    def new_product(self, company, *, is_active: bool = True):
        return new_product(company, is_active=is_active)

    def new_invitation(self, company, invited_by):
        user = self.new_user(company, can_login=False, is_active=False)
        role = self.role_b if company.pk == self.b.pk else self.role_a
        with tenant_context(company):
            invitation = Invitation.objects.create(
                email=user.email,
                company=company,
                invited_by=invited_by,
                role=role,
                expires_at=timezone.now() + timedelta(days=7),
            )
        return user, invitation

    # ---- schema switching ------------------------------------------------------
    @staticmethod
    def in_tenant(company):
        """`with w.in_tenant(w.b):` runs the block inside company B's schema."""
        return tenant_context(company)

    @staticmethod
    def on_public():
        return schema_context(get_public_schema_name())

    # ---- GraphQL ---------------------------------------------------------------
    def run(self, user, document: str, variables: dict | None = None, *, host=None):
        """Execute a GraphQL document as `user`, the way the real view would.

        `host` is the site the request arrives on, i.e. which schema is active:
          None    the user's own company (a normal request),
          Company another company's host (a user presented on the wrong site),
          PUBLIC  the platform site (no company context).
        """
        request = RequestFactory().post("/graphql/")
        request.user = user
        if host is PUBLIC:
            context = schema_context(get_public_schema_name())
        else:
            context = tenant_context(host if host is not None else user.company)
        with context:
            return schema.execute_sync(
                document,
                variable_values=variables,
                context_value=SimpleNamespace(request=request),
            )


@pytest.fixture(autouse=True)
def _start_and_end_on_the_public_schema():
    """TenantMiddleware switches the connection to a company's schema for a request and
    nothing switches it back (in production the connection is recycled per request; in a
    test the next test would inherit it). Reset it around every test in this package."""
    connection.set_schema_to_public()
    yield
    connection.set_schema_to_public()


@pytest.fixture
def w(db, tenant_world_ids) -> World:
    cache.clear()
    return World(tenant_world_ids)