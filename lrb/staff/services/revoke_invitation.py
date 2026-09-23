from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation


@transaction.atomic
def revoke_invitation(*, invitation_id):
    invitation = Invitation.objects.filter(pk=invitation_id, used=False).first()
    if not invitation:
        raise ApplicationError(
            message="Invitation not found or already used.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    user = invitation.company.users.filter(
        email=invitation.email, can_login=False, is_active=False
    ).first()
    if user:
        user.delete()

    invitation.delete()
    return True
