from typing import Iterable, Optional

from django.db.models import Q

from lrb.accounts.models import User
from lrb.core.tenancy import require_company_id


def count_active_founders(
    *, company_id: str, exclude_ids: Optional[Iterable[str]] = None
) -> int:
    """Active founders + co-founders of one company (the 'founder tier')."""
    company_id = require_company_id(company_id)
    qs = User.objects.filter(
        Q(is_founder=True) | Q(is_cofounder=True),
        company_id=company_id,
        is_active=True,
    )
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    return qs.count()