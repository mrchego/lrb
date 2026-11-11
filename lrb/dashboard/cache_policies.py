from lrb.core.cache import (
    CachePolicy,
    Consistency,
    register_model_invalidation,
    register_policy,
)

# Product counts change only through product writes, so they are cleared the moment a
# Product is saved or deleted. The TTL only covers the 30-day chart window rolling over.
PRODUCT_STATS = register_policy(
    CachePolicy(
        name="dashboard.product_stats",
        owner="dashboard",
        consistency=Consistency.BOUNDED_STALE,
        ttl=120,
        stale_ttl=600,
        description="Per-company product totals and 30-day creation chart for the dashboard.",
        loader="lrb.dashboard.selectors.product_stats.get_product_stats",
    )
)

# User counts include lockouts (time-based) and are affected by logins and invitations,
# so no signal-based clearing: a short TTL keeps it honest. Worst case is about 3 minutes old.
USER_STATS = register_policy(
    CachePolicy(
        name="dashboard.user_stats",
        owner="dashboard",
        consistency=Consistency.BOUNDED_STALE,
        ttl=60,
        stale_ttl=120,
        description="Per-company user totals, locked users, pending invitations, signups chart.",
        loader="lrb.dashboard.selectors.user_stats.get_user_stats",
    )
)

register_model_invalidation(model="company.CompanySettings", policies=[PRODUCT_STATS, USER_STATS])