from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def promote_to_cofounder(*, user_id: str, company_id: str) -> User:
    user = get_user(user_id=user_id, company_id=company_id)
    if user is None:
        raise ApplicationError("User Not Found.", code=ErrorCode.USER_NOT_FOUND)
    if user.has_founder_access:
        raise ApplicationError(
            "User is already a founder or co-founder.", code=ErrorCode.VALIDATION_ERROR
        )
    # Never hand the highest authority to a deleted or login-disabled account
    # (this also covers invited-but-not-yet-accepted users).
    if not user.is_active or not user.can_login:
        raise ApplicationError(
            "Only active users who can log in can become co-founders.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    user.is_cofounder = True
    user.save(update_fields=["is_cofounder"])
    return user