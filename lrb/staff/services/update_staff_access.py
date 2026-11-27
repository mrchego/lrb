from typing import Iterable, Optional

from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_role import get_role
from lrb.authorization.services.set_user_permissions import set_user_permissions
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def update_staff_access(
    *,
    user_id: str,
    company_id: str,
    role_id: Optional[str] = None,
    permission_codenames: Iterable[str],
):
    """Change a staff member's role AND their exact permission set in one step."""
    user = get_user(user_id=user_id, company_id=company_id)
    if user is None:
        raise ApplicationError(
            message="Staff member not found.", code=ErrorCode.USER_NOT_FOUND
        )
    if user.has_founder_access:
        raise ApplicationError(
            message="Founders and co-founders always have full access.",
            code=ErrorCode.BUSINESS_RULE,
        )
    if not user.can_login:
        raise ApplicationError(
            message="This staff member has no login access. Give them login access first.",
            code=ErrorCode.BUSINESS_RULE,
        )

    permission_codenames = list(permission_codenames)

    if role_id is None:
        # Direct-permissions mode: no role at all. Require at least one
        # permission, otherwise the person could log in and do nothing.
        if not permission_codenames:
            raise ApplicationError(
                message="Choose a role or tick at least one permission.",
                code=ErrorCode.VALIDATION_ERROR,
            )
        UserRole.objects.filter(user=user).delete()
    else:
        role = get_role(role_id=role_id, company_id=company_id)
        if role is None:
            raise ApplicationError(
                message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND
            )
        # One role per staff member through this screen: drop any other
        # roles, keep (or create) the chosen one.
        UserRole.objects.filter(user=user).exclude(role=role).delete()
        UserRole.objects.get_or_create(user=user, role=role)

    set_user_permissions(
        user_id=user.id,
        company_id=company_id,
        permission_codenames=permission_codenames,
    )
    return user