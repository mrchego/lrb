"""
Tenant-isolation guards shared by every selector, service and resolver.

Rule of the project: nothing reads or writes tenant data without a company_id
that came from the *logged-in user on the server*, never from client input.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lrb.core.exceptions import AppPermissionDeniedError

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


def assert_company_active(user: "User") -> None:
    """A deactivated company's users (and live sessions) lose all access."""
    company = user.company
    if company is None or not company.is_active:
        raise AppPermissionDeniedError(message="This company is deactivated.")
