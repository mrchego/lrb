from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def set_staff_login_access(*, user_id, can_login):
    user = get_user(user_id=user_id)
    if not user:
        raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)
    user.can_login = can_login
    user.save(update_fields=["can_login"])
    return user