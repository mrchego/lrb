from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.authorization.services.set_user_permissions import set_user_permissions
from lrb.core.constants import INVITATION_EXPIRY_DAYS
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation
from lrb.staff.selectors.get_pending_invitation_for_email import (
    get_pending_invitation_for_email,
)
from lrb.staff.services.send_invitation_email import send_invitation_email


@transaction.atomic
def promote_staff_to_login(
    *,
    user_id,
    company,
    invited_by,
    request,
    role=None,
    permission_codenames: Optional[Iterable[str]] = None,
):
    """Give a records-only person login access.

    Access can come from a role, from directly ticked permissions, or both
    (ticked permissions that differ from the role become overrides).
    """
    user = get_user(user_id=user_id, company_id=company.id)
    if not user:
        raise ApplicationError(
            message="Staff member not found.", code=ErrorCode.USER_NOT_FOUND
        )

    permission_codenames = (
        list(permission_codenames) if permission_codenames is not None else None
    )
    if role is None and not permission_codenames:
        raise ApplicationError(
            message="Choose a role or tick at least one permission.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if role is not None and role.company_id != company.id:
        raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)
    if user.can_login:
        raise ApplicationError(
            message="This staff member can already log in.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if get_pending_invitation_for_email(email=user.email, company_id=company.id):
        raise ApplicationError(
            message="An invitation is already pending for this staff member.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if role is not None:
        UserRole.objects.get_or_create(user=user, role=role)
    if permission_codenames is not None:
        set_user_permissions(
            user_id=user.id,
            company_id=str(company.id),
            permission_codenames=permission_codenames,
        )
    transaction.on_commit(lambda: invalidate_user_permissions_cache(user_id=user.id))

    invitation = Invitation.objects.create(
        email=user.email,
        company=company,
        invited_by=invited_by,
        role=role,
        expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
    )
    transaction.on_commit(
        lambda: send_invitation_email(request=request, invitation=invitation)
    )
    return user, invitation