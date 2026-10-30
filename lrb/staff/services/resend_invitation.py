import uuid

from django.db import transaction
from django.utils import timezone

from lrb.core.constants import INVITATION_EXPIRY_DAYS
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation
from lrb.staff.selectors.get_invitation import get_invitation
from lrb.staff.services.send_invitation_email import send_invitation_email


@transaction.atomic
def resend_invitation(*, invitation_id, company_id, request):
    invitation = (
        Invitation.objects.select_for_update()
        .filter(pk=invitation_id, company_id=company_id, used=False)
        .first()
    )
    if not invitation:
        raise ApplicationError(
            message="Invitation not found or already used.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    invitation.token = uuid.uuid4()
    invitation.expires_at = timezone.now() + timezone.timedelta(
        days=INVITATION_EXPIRY_DAYS
    )
    invitation.save(update_fields=["token", "expires_at"])
    transaction.on_commit(
        lambda: send_invitation_email(request=request, invitation=invitation)
    )
    return invitation
