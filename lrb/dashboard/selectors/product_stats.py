from datetime import timedelta

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from lrb.core.clock.core import local_today
from lrb.core.clock.ranges import TimePreset, apply_date_range, build_date_range
from lrb.core.clock.zones import get_company_timezone
from lrb.products.models import Product


def get_product_stats(*, company_id: str):
    tz = get_company_timezone(company_id=company_id)
    window = build_date_range(preset=TimePreset.LAST_30_DAYS, today=local_today(tz=tz))
    qs = Product.objects.filter(company_id=company_id)
    stats = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    daily = (
        apply_date_range(qs, "created_at", date_range=window, tz=tz)
        .annotate(day=TruncDate("created_at", tzinfo=tz))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return {
        **stats,
        "created_last_30_days": [
            {"date": d["day"].isoformat(), "value": d["count"]} for d in daily
        ],
    }
