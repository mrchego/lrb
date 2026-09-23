from typing import Optional

from lrb.core.pagination import paginate_queryset
from lrb.staff.models import Invitation


def list_invitations(
    *,
    company_id: str,
    used: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    qs = Invitation.objects.select_related("role", "invited_by").filter(
        company_id=company_id
    )
    if used is not None:
        qs = qs.filter(used=used)
    return paginate_queryset(qs.order_by("-created_at"), limit=limit, offset=offset)
