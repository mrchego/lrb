"""
Fixtures for the cross-company isolation suite.

World builds TWO complete companies (A and B). Every test acts as company A and
tries to touch company B. Targets are created fresh per attack so one attack
can't mask or contaminate another.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from config.schema import schema
from lrb.accounts.services.create_user import create_user
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.permissions import PERMISSION_REGISTRY
from lrb.authorization.services.create_role import create_role
from lrb.company.services.create_company import create_company
from lrb.products.services.create_product import create_product
from lrb.staff.models import Invitation

PASSWORD = "Str0ng-Passw0rd!"


def _uid(prefix: str = "x") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class World:
    def __init__(self):
        self.a = self.new_company("A")
        self.b = self.new_company("B")

        all_codenames = [codename for codename, _, _ in PERMISSION_REGISTRY]
        self.role_a = self.new_role(self.a, all_codenames)
        self.role_b = self.new_role(self.b, ["products.view_product"])

        # Company A: founder-owner + a staff member holding every permission.
        self.owner_a = self.new_user(self.a, is_superuser=True, is_founder=True)
        self.staff_a = self.new_user(self.a, role=self.role_a)
        self.product_a = self.new_product(self.a)

        # Company B: founder-owner + a staff member with a role.
        self.owner_b = self.new_user(self.b, is_superuser=True, is_founder=True)
        self.staff_b = self.new_user(self.b, role=self.role_b)
        self.product_b = self.new_product(self.b)

    # ---- builders -----------------------------------------------------------
    def new_company(self, label: str):
        return create_company(
            name=f"Company {label} {_uid()}",
            email=f"{_uid(label.lower())}@company.test",
            phone="+254700000001",
            country="KE",
            city="Nairobi",
            address="1 Test Street",
        )

    def new_role(self, company, codenames):
        return create_role(
            company=company, name=_uid("role"), permission_codenames=list(codenames)
        )

    def new_user(self, company, *, role=None, **flags):
        flags.setdefault("can_login", True)
        flags.setdefault("is_active", True)
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

    def new_product(self, company, *, is_active: bool = True):
        return create_product(
            company=company,
            name="Widget",
            sku=_uid("sku"),
            price=Decimal("10.00"),
            is_active=is_active,
        )

    def new_invitation(self, company, invited_by):
        user = self.new_user(company, can_login=False, is_active=False)
        invitation = Invitation.objects.create(
            email=user.email,
            company=company,
            invited_by=invited_by,
            role=self.role_b if company == self.b else self.role_a,
            expires_at=timezone.now() + timedelta(days=7),
        )
        return user, invitation

    # ---- GraphQL ------------------------------------------------------------
    def run(self, user, document: str, variables: dict | None = None):
        """Execute a GraphQL document exactly as the real view would, as `user`."""
        request = RequestFactory().post("/graphql/")
        request.user = user
        return schema.execute_sync(
            document,
            variable_values=variables,
            context_value=SimpleNamespace(request=request),
        )


@pytest.fixture
def w(db) -> World:
    cache.clear()
    call_command("sync_permissions")
    return World()
