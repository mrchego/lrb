from typing import Iterable

from lrb.staff.models import Invitation


def get_invitations_by_ids(*, invitation_ids: Iterable[str], company_id: str | None) -> QuerySet[User]:
    qs = Invitation.objects.filter(pk__in=invitation_ids)
    if company_id:
        qs = qs.filter(company_id=company_id)
    return qs