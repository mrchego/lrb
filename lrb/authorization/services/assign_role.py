from django.db import IntegrityError, transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def assign_role(*, user_id, role_id, company_id):
    user = get_user(user_id=user_id)
    if not user or str(user.company_id) != str(company_id):
        raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

    role = Role.objects.filter(pk=role_id, company_id=company_id).first()
    if not role:
        raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

    try:
        UserRole.objects.create(user=user, role=role)
    except IntegrityError:
        return ApplicationError(message=IntegrityError, code=ErrorCode.ALREADY_ASSIGNED)

    invalidate_user_permissions_cache(user_id=user.id)
    return True
