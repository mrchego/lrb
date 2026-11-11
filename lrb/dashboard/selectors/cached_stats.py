from lrb.core.cache import cached_read
from lrb.dashboard.cache_policies import PRODUCT_STATS, USER_STATS


def get_cached_product_stats(*, company_id: str) -> dict:
    return cached_read(policy=PRODUCT_STATS, company_id=company_id)


def get_cached_user_stats(*, company_id: str) -> dict:
    return cached_read(policy=USER_STATS, company_id=company_id)
