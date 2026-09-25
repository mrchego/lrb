from typing import List, Optional

import strawberry

from lrb.accounts.selectors.get_current_user import get_current_user
from lrb.authorization.selectors.user_has_permission import user_has_permission
from lrb.dashboard.selectors.product_stats import get_product_stats
from lrb.dashboard.selectors.user_stats import get_user_stats


@strawberry.type
class ChartPoint:
    date: str
    value: float


@strawberry.type
class ProductStats:
    total: int
    active: int
    inactive: int
    created_last_30_days: List[ChartPoint]


@strawberry.type
class UserStats:
    total: int
    active: int
    locked: int
    pending_invitations: int
    signups_last_30_days: List[ChartPoint]


def _points(raw: list) -> List[ChartPoint]:
    return [ChartPoint(date=p["date"], value=p["value"]) for p in raw]


@strawberry.type
class DashboardData:
    @strawberry.field
    def products(self, info: strawberry.Info) -> Optional[ProductStats]:
        user = get_current_user(info)
        if not user or not user.company_id:
            return None
        if not user_has_permission(user=user, codename="products.view_product"):
            return None
        stats = get_product_stats(company_id=str(user.company_id))
        return ProductStats(
            total=stats["total"],
            active=stats["active"],
            inactive=stats["inactive"],
            created_last_30_days=_points(stats["created_last_30_days"]),
        )

    @strawberry.field
    def users(self, info: strawberry.Info) -> Optional[UserStats]:
        user = get_current_user(info)
        if not user or not user.is_superuser or not user.company_id:
            return None
        stats = get_user_stats(company_id=str(user.company_id))
        return UserStats(
            total=stats["total"],
            active=stats["active"],
            locked=stats["locked"],
            pending_invitations=stats["pending_invitations"],
            signups_last_30_days=_points(stats["signups_last_30_days"]),
        )
