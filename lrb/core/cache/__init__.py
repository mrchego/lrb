"""Global caching platform. Apps import from here and nowhere else."""
from lrb.core.cache.client import cache_delete_many, cache_get, cache_set
from lrb.core.cache.invalidation import (
    connect_model_invalidation,
    delete_after_commit,
    invalidate_policy,
    register_model_invalidation,
)
from lrb.core.cache.keys import build_key, current_tenant_scope
from lrb.core.cache.policies import (
    CachePolicy,
    Consistency,
    all_policies,
    autodiscover_cache_policies,
    get_policy,
    jittered_ttl,
    register_policy,
)
from lrb.core.cache.read import cached_read

__all__ = [
    "CachePolicy",
    "Consistency",
    "all_policies",
    "autodiscover_cache_policies",
    "build_key",
    "cache_delete_many",
    "cache_get",
    "cache_set",
    "cached_read",
    "connect_model_invalidation",
    "current_tenant_scope",
    "delete_after_commit",
    "get_policy",
    "invalidate_policy",
    "jittered_ttl",
    "register_model_invalidation",
    "register_policy",
]