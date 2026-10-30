from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation
from lrb.staff.services.cancel_invitation import cancel_invitation

@transaction.atomic
def revoke_invitation(*, invitation_id, company_id):
    invitation = Invitation.objects.filter(pk=invitation_id, company_id=company_id, used=False).first()
    if not invitation:
        raise ApplicationError(
            message="Invitation not found or already used.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    cancel_invitation(invitation=invitation)
    return True
