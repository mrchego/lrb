from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.services.founder_guard import assert_not_last_founder
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def demote_cofounder(*, user_id: str, company_id: str) -> User:
    user = get_user(user_id=user_id, company_id=company_id)
    if user is None:
        raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)
    # Guard first: if this is the founder, report "founder is protected"
    # rather than "not a co-founder".
    assert_not_last_founder(user=user, company_id=company_id, action="demoted")
    if not user.is_cofounder:
        raise ApplicationError(
            "User Is Not A Co-founder", code=ErrorCode.VALIDATION_ERROR
        )
    user.is_cofounder = False
    user.save(update_fields=["is_cofounder"])
    return user