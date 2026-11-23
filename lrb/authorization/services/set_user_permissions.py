from typing import Iterable

from django.db import transaction

from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.user_role import UserPermissionOverride
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.exceptions import (
    AppValidationError,
    ApplicationError,
    ErrorCode,
)


@transaction.atomic
def set_user_permissions(
    *, user_id: str, company_id: str, permission_codenames: Iterable[str]
) -> None:
    """Make the user's EFFECTIVE permissions equal `permission_codenames`.

    Effective permissions = role permissions + overrides (grants add, denies
    remove). So we store only the DIFFERENCE between what the founder ticked
    and what the user's role(s) already give:

        ticked but not in role  -> grant override
        in role but not ticked  -> deny override

    Overrides are always rebuilt from scratch, so changing the role first and
    calling this afterwards never leaves stale overrides behind. Call it
    AFTER the user's role assignment is final.
    """
    user = get_user(user_id=user_id, company_id=company_id)
    if user is None:
        raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)
    if user.has_founder_access:
        raise ApplicationError(
            message="Founders and co-founders always have full access; their permissions can't be customised.",
            code=ErrorCode.BUSINESS_RULE,
        )

    desired = set(permission_codenames)
    known = set(
        Permission.objects.filter(codename__in=desired).values_list(
            "codename", flat=True
        )
    )
    unknown = desired - known
    if unknown:
        raise AppValidationError(
            message=f"Unknown permission codename(s): {sorted(unknown)}",
            field="permission_codenames",
        )

    baseline = set(
        Permission.objects.filter(
            roles__company_id=company_id, roles__user_roles__user=user
        )
        .values_list("codename", flat=True)
        .distinct()
    )

    grants = desired - baseline
    denies = baseline - desired
    changed = grants | denies
    by_codename = {
        p.codename: p for p in Permission.objects.filter(codename__in=changed)
    }

    UserPermissionOverride.objects.filter(user=user).delete()
    for codename in sorted(changed):
        UserPermissionOverride.objects.create(
            user=user,
            permission=by_codename[codename],
            is_granted=codename in grants,
        )

    transaction.on_commit(lambda: invalidate_user_permissions_cache(user_id=user.id))