# company/cache_policies.py
from lrb.core.cache.invalidation import register_model_invalidation
from lrb.core.cache.policies import CachePolicy, Consistency, register_policy

COMPANY_SETTINGS = register_policy(
    CachePolicy(
        name="company.settings",
        owner="company",
        consistency=Consistency.BOUNDED_STALE,
        ttl=300,
        description="Timezone, currency and date format of one company. Cleared on save.",
        loader="lrb.company.selectors.get_company_settings_snapshot.get_company_settings_snapshot",
    )
)
register_model_invalidation(
    model="company.CompanySettings", policies=[COMPANY_SETTINGS]
)
