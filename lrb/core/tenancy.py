"""
Tenant-isolation guards shared by every selector, service and resolver.

Rule of the project: nothing reads or writes tenant data without a company_id
that came from the *logged-in user on the server*, never from client input.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lrb.core.exceptions import AppPermissionDeniedError

from django.db import connection
from django_tenants.utils import get_public_schema_name

if TYPE_CHECKING:
    from lrb.accounts.models import User



def require_company_id(company_id) -> str:
    """
    Fail closed. A missing/empty company_id must never mean "all companies".
    Call this at the top of every tenant-scoped selector and service.
    """
    if not company_id:
        raise AppPermissionDeniedError(message="No company context.")
    return str(company_id)


def get_current_tenant():
    tenant = getattr(connection, "tenant", None)
    if tenant is None or connection.schema_name == get_public_schema_name():
        raise AppPermissionDeniedError(message="No company context.")
    return tenant


def require_public_schema() -> None:
    if connection.schema_name != get_public_schema_name():
        raise AppPermissionDeniedError(message="Only available on the platform site.")


def assert_user_in_current_tenant(user) -> None:
    """Lock two: the user's company must be the company whose schema is active."""
    if str(user.company_id) != str(get_current_tenant().pk):
        raise AppPermissionDeniedError(message="No company context.")

def assert_company_active(user: "User") -> None:
    assert_user_in_current_tenant(user)  # <-- new first line
    company = user.company
    if company is None or not company.is_active:
        raise AppPermissionDeniedError(message="This company is deactivated.")
