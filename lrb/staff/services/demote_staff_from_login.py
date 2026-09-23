from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.selectors.get_pending_invitation_for_email import (
    get_pending_invitation_for_email,
)


@transaction.atomic
def demote_staff_from_login(*, user_id, company_id):
    user = get_user(user_id=user_id)
    if not user or user.company_id != company_id:
        raise ApplicationError(
            message="Staff member not found.", code=ErrorCode.USER_NOT_FOUND
        )
    UserRole.objects.filter(user=user).delete()
    user.can_login = False
    user.save(update_fields=["can_login"])
    invalidate_user_permissions_cache(user_id=user.id)
    pending = get_pending_invitation_for_email(email=user.email, company_id=company_id)
    if pending:
        pending.delete()
    return user
