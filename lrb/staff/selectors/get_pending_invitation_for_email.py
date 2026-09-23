from typing import Optional

from django.utils import timezone

from lrb.staff.models import Invitation


def get_pending_invitation_for_email(
    *, email: str, company_id: str
) -> Optional[Invitation]:
    return Invitation.objects.filter(
        email=email,
        company_id=company_id,
        used=False,
        expires_at__gt=timezone.now(),
    ).first()
