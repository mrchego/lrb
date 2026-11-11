from lrb.core.cache import CachePolicy, Consistency, register_policy

USER_PERMISSIONS = register_policy(
    CachePolicy(
        name="authz.user_perms",
        owner="authz",
        consistency=Consistency.STRICT,
        ttl=300,
        description=(
            "Permission codenames of one user in one company. Deleted after commit "
            "whenever roles or overrides change; the TTL is only the safety net."
        ),
    )
)
