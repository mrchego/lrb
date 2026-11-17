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
# CompanySettings lives in the shared (public) schema but its entries are cached under each
# company's own schema, and Django admin can edit the row from the public site:
# schema_from_company makes the delete hit the company's schema in both cases.
register_model_invalidation(
    model="company.CompanySettings",
    policies=[COMPANY_SETTINGS],
    schema_from_company=True,
)