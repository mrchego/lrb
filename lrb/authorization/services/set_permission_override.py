from django.db import transaction

from lrb.accounts.selectors import get_user
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.user_role import UserPermissionOverride
from lrb.authorization.selectors.get_user_permissions import invalidate_user_permissions_cache
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def set_permission_override(*, user_id:str, permission_codename: str, is_granted: bool) -> bool:
    user = get_user(user_id=user_id)
    if not user:
        raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)
    permission = Permission.objects.filter(codename=permission_codename).first()
    if not permission:
        raise ApplicationError(message="Permission not found.", code=ErrorCode.VALIDATION_ERROR)

    UserPermissionOverride.objects.update_or_create(user=user, permission=permission, defaults={"is_granted":is_granted})
    invalidate_user_permissions_cache(user_id=user.id)
    return True


# Teaching: set_permission_override

# The main new concept here is update_or_create — a genuinely useful Django method you haven't seen yet, built to solve a very specific "create it if missing, update it if it exists" problem cleanly. There's also a real scoping gap worth flagging, following the same instinct you've built up over the last several files. Let's go through it fully.

# 1. What is it?

# A service that sets (or changes) a per-user permission override — "grant" or "revoke" one specific permission for one specific user, regardless of what their role normally allows. This is the write-side counterpart to the list_user_overrides selector you read earlier.

# New piece: .update_or_create(...).

# 2. How is it written?

# user = get_user(user_id=user_id)
# Same selector, same shape as assign_role used — fetch or None.

# if not user: raise ApplicationError(...)
# Familiar not-found guard — but notice what's missing here compared to assign_role. More on that in section 5.

# permission = Permission.objects.filter(codename=permission_codename).first()
# This is exactly what get_permission (your very first selector!) already does — inlined here directly instead of calling that selector. Same "find one or None" pattern you've seen many times now.

# UserPermissionOverride.objects.update_or_create(user=user, permission=permission, defaults={"is_granted": is_granted})
# This is the new concept. update_or_create(...) is a Django manager method that does exactly what its name says, in one call:

# It looks for an existing row matching the arguments outside of defaults — here, that means "a UserPermissionOverride where user is this user and permission is this permission."
# If a matching row already exists — update it, setting its fields to whatever's inside defaults (here, just is_granted), and save it.
# If no matching row exists — create a brand-new row, using both the lookup fields (user, permission) and the defaults fields (is_granted) together, and save it.

# So the split between "plain keyword arguments" and the defaults={...} dictionary matters: the plain arguments (user=user, permission=permission) are what Django uses to search for an existing row; defaults is what gets applied whether creating fresh or updating what's found.

# Why does this matter here specifically? Because "set a permission override" is inherently ambiguous about whether one already exists — the caller might be creating a brand-new override for the first time, or flipping an existing override from granted to revoked (or vice versa). Without update_or_create, you'd have to write this yourself:

# python
# override = UserPermissionOverride.objects.filter(user=user, permission=permission).first()
# if override:
#     override.is_granted = is_granted
#     override.save()
# else:
#     UserPermissionOverride.objects.create(user=user, permission=permission, is_granted=is_granted)

# update_or_create collapses that entire branch into one call — and (importantly) does it as a single atomic-safe operation at the database level, avoiding the same kind of check-then-act race condition you learned about back in create_role's IntegrityError discussion.

# {"is_granted": is_granted}
# A plain dictionary literal — defaults expects a dict mapping field names to the values they should be set to. Only one field here, but the shape ({"field_name": value}) generalizes to any number of fields you'd want updated/created together.

# 3. Signature — broken into pieces
# python
# def set_permission_override(*, user_id: str, permission_codename: str, is_granted: bool) -> bool:
# Piece	Meaning
# *,	keyword-only
# user_id: str	which user this override applies to
# permission_codename: str	which permission to override
# is_granted: bool	True = explicitly grant this permission; False = explicitly revoke it, overriding whatever the role would normally say
# -> bool	fully typed, including the return hint! — the first write service in this whole conversation to have a complete, correct signature

# Worth stopping on this positively: every parameter and the return type are hinted here, unlike every previous write service you've read. Good to notice when a file actually matches the convention fully, not just when it drifts.

# 4. Body — line by line
# python
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

# Fetch the target user; reject if missing.

# python
# permission = Permission.objects.filter(codename=permission_codename).first()
# if not permission:
#     raise ApplicationError(message="Permission not found.", code=ErrorCode.VALIDATION_ERROR)

# Fetch the permission by its codename; reject if the codename doesn't exist — same validation spirit as create_role's unknown-codename check, just for a single value instead of a list.

# python
# UserPermissionOverride.objects.update_or_create(
#     user=user, permission=permission, defaults={"is_granted": is_granted}
# )

# Find-or-create the override row for this exact (user, permission) pair, setting/updating is_granted either way.

# python
# invalidate_user_permissions_cache(user_id=user.id)
# return True

# Clear this user's cached effective permissions (same per-user cache assign_role/remove_role used — makes total sense, since an override directly changes what permissions this user effectively has), and signal success.

# 5. Why? — and a real gap worth flagging

# Why update_or_create instead of a separate create_override/update_override pair of functions?
# Because from the caller's perspective (an admin UI toggling a permission checkbox for a specific user), there's no meaningful difference between "this is the first time we're overriding this permission" and "we're changing a previous override" — both cases boil down to the same intent: "make this permission's status for this user be exactly this." Modeling it as one operation avoids forcing the caller (or this service) to first check which case applies.

# A scoping gap worth flagging, matching your "catch drift" instinct from assign_role:
# Compare this function's user-fetching line to assign_role's:

# python
# # assign_role:
# user = get_user(user_id=user_id)
# if not user or str(user.company_id) != str(company_id):
#     raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

# # set_permission_override:
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError(message="User not found.", code=ErrorCode.USER_NOT_FOUND)

# set_permission_override doesn't accept a company_id parameter at all, and consequently has no company-scoping check on the fetched user. This means: whoever calls this service is fully trusted to have already verified, elsewhere, that the target user belongs to their own company — this service itself does nothing to enforce that. If the resolver calling this always passes current.company_id in some other validation step before reaching this service, that might be fine. But if any calling code skips that check, this function would let an admin from Company A silently grant or revoke permissions for a user in Company B — a serious, exploitable gap, in exactly the same spirit as the missing check you correctly flagged for list_user_overrides earlier. Worth tracing this function's actual callers to confirm the company check happens somewhere before this runs — never assume it does just because the function is named sensibly.

# Why is "permission not found" tagged with ErrorCode.VALIDATION_ERROR here, rather than something more specific like a dedicated "permission not found" code (compare to ErrorCode.USER_NOT_FOUND and ErrorCode.ROLE_NOT_FOUND used elsewhere)?
# Minor inconsistency worth noticing, similar to clone_role's error-code drift: every other "not found" case in your codebase so far (USER_NOT_FOUND, ROLE_NOT_FOUND) has its own specific code. This one reuses the generic VALIDATION_ERROR instead of, say, a hypothetical PERMISSION_NOT_FOUND. Not necessarily broken, but if your ErrorCode enum has a dedicated code for this and it's just not being used, that's a small consistency gap; if no such code exists yet, it might be worth adding one to match the pattern.

# 6. Connections

# What comes in: user_id, permission_codename, is_granted — no company_id, unlike its sibling assign_role.
# What goes out: True, or ApplicationError for a missing user or unknown permission.
# Where this fits: the write-side counterpart to list_user_overrides — likely called from an admin screen showing a user's full effective permission list (role-based + overrides), letting an admin toggle individual permissions on/off for that one user specifically.
# Cache connection: confirms again that invalidate_user_permissions_cache(user_id=...) is the standard cleanup step any time anything affecting one user's effective permissions changes — you've now seen it triggered by role assignment (assign_role), role removal (remove_role), and now individual overrides (set_permission_override). This is a strong, consistent pattern: any service that changes what a user can do calls this same cache invalidation at the end.

# 7. Advanced concepts

# A) update_or_create's split between lookup fields and defaults
# The general rule to remember: everything passed as a plain keyword argument (not inside defaults) is used to find the row; everything inside defaults is used to set values on whichever row is found or created. If a field needs to be part of both finding and setting (like user/permission here — they identify the row and would be set on it if newly created), just pass it as a lookup argument; Django uses lookup fields for creation too, alongside anything in defaults.

# B) update_or_create and atomicity together
# Just like create_role's reliance on the database's own uniqueness constraint, update_or_create is itself safe against the same kind of race condition a manual "check then create" would risk — Django implements it internally using the database's own atomic guarantees (helped further here by the surrounding @transaction.atomic). This is a recurring theme across every write service you've read: prefer a single database operation that expresses your full intent, over multiple separate Python-level steps that could interleave badly with another concurrent request.

# 8. Small example
# python
# overrides = {}   # (user_id, permission_codename) -> is_granted

# def set_permission_override(*, user_id, permission_codename, is_granted):
#     key = (user_id, permission_codename)
#     overrides[key] = is_granted   # same call handles both "new" and "changed"
#     return True

# set_permission_override(user_id="u1", permission_codename="orders.delete", is_granted=True)
# set_permission_override(user_id="u1", permission_codename="orders.delete", is_granted=False)
# print(overrides)  # {('u1', 'orders.delete'): False} — updated in place, not duplicated
# 9. What you should remember
# update_or_create(lookup_fields..., defaults={...}) collapses "find, then update-or-insert" into one safe, atomic call — reach for it whenever an operation's meaning is naturally "make this be true," regardless of whether a matching row already exists.
# The split matters: plain keyword arguments are used to find the row; defaults is what gets set, on either the found or newly-created row.
# A fully-typed signature (every parameter and the return type) is worth noticing and naming as a genuine positive — not every file needs a correction; recognizing when a convention is followed correctly is just as valuable a reading skill as catching drift.
# A missing scoping parameter (here: no company_id) compared to a near-identical sibling function (assign_role) is a real, security-relevant thing to investigate — trace the actual callers before assuming it's safe; don't assume a function is secure just because a similar one nearby is.
# Error codes should be as specific as the situation allows, and consistent with how similar "not found" cases are coded elsewhere in the same project — a generic VALIDATION_ERROR standing in for what looks like it should be a specific "not found" code is worth flagging as a small drift, even if it isn't breaking anything today.