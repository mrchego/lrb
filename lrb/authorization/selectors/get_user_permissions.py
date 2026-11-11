from __future__ import annotations

from typing import Optional

from lrb.authorization.cache_policies import USER_PERMISSIONS
from lrb.core.cache import (
    build_key,
    cache_get,
    cache_set,
    current_tenant_scope,
    delete_after_commit,
)
from lrb.core.cache import metrics
from lrb.core.exceptions import AppPermissionDeniedError

USER_PERMISSIONS_CACHE_TTL = USER_PERMISSIONS.ttl
_NAMESPACE = USER_PERMISSIONS.name


def user_permissions_cache_key(*, user_id: str) -> str:
    return build_key(
        namespace=_NAMESPACE, company_id=current_tenant_scope(), parts=[user_id]
    )


def invalidate_user_permissions_cache(*, user_id: str) -> None:
    """Safe to call anywhere in a write service: the delete waits for commit."""
    delete_after_commit(keys=[user_permissions_cache_key(user_id=user_id)])


def invalidate_role_permissions_cache(*, role) -> None:
    # Collect the user ids NOW. If the role is being deleted, its UserRole rows
    # will be gone by commit time and we could no longer find who to invalidate.
    user_ids = list(role.user_roles.values_list("user_id", flat=True))
    if user_ids:
        delete_after_commit(
            keys=[user_permissions_cache_key(user_id=uid) for uid in user_ids]
        )


def _cache_key_for(user) -> Optional[str]:
    """Key for this user, or None when caching would not be safe."""
    if not user.company_id:
        return None
    try:
        scope = current_tenant_scope()
    except AppPermissionDeniedError:
        return None
    if str(user.company_id) != scope:
        return None  # user does not belong to the active company: never cache
    return user_permissions_cache_key(user_id=user.id)


def _compute_user_permission_codenames(*, user) -> set[str]:
    from lrb.authorization.models.user_role import UserPermissionOverride, UserRole

    role_perms = set(
        UserRole.objects.filter(user=user, role__company_id=user.company_id)
        .values_list("role__permissions__codename", flat=True)
    )
    role_perms.discard(None)

    overrides = UserPermissionOverride.objects.filter(user=user).select_related(
        "permission"
    )
    for o in overrides:
        if o.is_granted:
            role_perms.add(o.permission.codename)
        else:
            role_perms.discard(o.permission.codename)
    return role_perms


def get_user_permission_codenames(*, user) -> set[str]:
    cache_key = _cache_key_for(user)
    if cache_key is None:
        return _compute_user_permission_codenames(user=user)

    cached = cache_get(cache_key)
    if cached is not None:
        metrics.record(_NAMESPACE, "hit")
        return set(cached)  # stored as a list: JSON has no set type

    metrics.record(_NAMESPACE, "miss")
    role_perms = _compute_user_permission_codenames(user=user)
    cache_set(cache_key, sorted(role_perms), timeout=USER_PERMISSIONS_CACHE_TTL)
    return role_perms
