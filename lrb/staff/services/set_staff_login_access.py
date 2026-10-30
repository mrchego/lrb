from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.services.demote_staff_from_login import demote_staff_from_login


@transaction.atomic
def set_staff_login_access(*, user_id, can_login,company_id):
    user = get_user(user_id=user_id)
    if not user or str(user.company_id) != str(company_id):
        raise ApplicationError(
            message="Staff member not found.", code=ErrorCode.USER_NOT_FOUND
        )
    if can_login:
        raise ApplicationError(
            message="Use 'Give Login Access' to grant login. It sends an invitation.",
            code=ErrorCode.BUSINESS_RULE,
        )
    return demote_staff_from_login(user_id=user_id, company_id=company_id)