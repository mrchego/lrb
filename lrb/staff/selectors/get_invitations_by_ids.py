from __future__ import annotations
from typing import Iterable, TYPE_CHECKING

from django.db.models import QuerySet


from lrb.staff.models import Invitation

if TYPE_CHECKING:
    from lrb.accounts.models import User

def get_invitations_by_ids(*, invitation_ids: Iterable[str], company_id: str | None) -> QuerySet[User]:
    qs = Invitation.objects.filter(pk__in=invitation_ids)
    if company_id:
        qs = qs.filter(company_id=company_id)
    return qs