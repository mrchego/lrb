from datetime import timedelta

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from lrb.products.models import Product


def get_product_stats(*, company_id: str):
    qs = Product.objects.filter(company_id=company_id)
    stats = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    since = timezone.now() - timedelta(days=30)
    daily = (
        qs.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
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
