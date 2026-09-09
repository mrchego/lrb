from django.db import transaction
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.role import Role
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_role_permissions_cache,
)
from lrb.core.exceptions import ApplicationError, AppValidationError, ErrorCode


@transaction.atomic
def update_role(
    *, role_id, company_id, name=None, permission_codenames=None, is_default=None
):
    role = Role.objects.filter(pk=role_id, company_id=company_id).first()
    if not role:
        raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

    if name is not None:
        name = name.strip()
        if len(name) < 2:
            raise AppValidationError(
                message="Role name must be at least 2 characters long.", field="name"
            )
        role.name = name

    if is_default is not None:
        role.is_default = is_default

    role.save()

    if permission_codenames is not None:
        permissions = list(Permission.objects.filter(codename__in=permission_codenames))
        unknown = set(permission_codenames) - {p.codename for p in permissions}
        if unknown:
            raise AppValidationError(
                message=f"Unknown permission codename(s): {sorted(unknown)}",
                field="permission_codenames",
            )
        role.permissions.set(permissions)
        invalidate_role_permissions_cache(role=role)

    return role


# Teaching: update_role

# This one reuses a lot of what you already know (@transaction.atomic, pk=/company_id scoping, the permission-validation set-difference pattern from create_role), so I'll move quickly through those and spend more time on what's genuinely new: partial updates using is not None as a sentinel, and a couple of real design questions worth raising — including one about ordering inside the transaction.

# 1. What is it?

# A service that updates an existing role — but only the fields the caller actually chose to change. Unlike create_role (which builds something new from scratch), this handles the "PATCH-style partial update" problem you first saw hinted at in UserMutation's dict-comprehension filtering — but done differently here, and it's worth understanding why it's done differently.

# New pieces:

# if name is not None: — an is not None check, distinct from a truthiness check
# role.name = name / role.save() — mutating and persisting an existing model instance
# invalidate_role_permissions_cache(role=role) — a cache-invalidation call
# 2. How is it written?

# role = Role.objects.filter(pk=role_id, company_id=company_id).first()
# Exactly the pattern from get_role, just inlined here instead of calling that selector — one .filter() call with both conditions combined (recall from get_role's teaching: this single-call form only works because both role_id and company_id are always provided here, no optional skipping needed — unlike get_role, where company_id could be None).

# if not role: raise ApplicationError(...)
# Same "role and correct company, or nothing" security pattern you already learned — a role belonging to a different company is treated identically to a role that doesn't exist at all.

# if name is not None: — the important new distinction
# This is genuinely different from patterns you've seen before, and the difference matters:

# In list_permissions, you saw if category: — a truthiness check (empty string counts as "not given").
# Here, it's if name is not None: — an identity/sentinel check (only actual None counts as "not given"; an empty string "" would still enter this block).

# Why the difference? Look at the signature: name=None. Since None is the default, "the caller didn't send a name to update" is represented as None. But what if the caller genuinely wants a name of ""? That would fail the .strip() + length check below anyway, so it doesn't matter much for name — but it matters a lot for the next one:

# if is_default is not None: role.is_default = is_default
# This is why is not None matters here specifically. is_default is a boolean — its valid values are True and False. If this code had instead written if is_default:, that would be a real bug: a caller trying to set is_default=False (a perfectly valid, meaningful request — "make this role NOT the default anymore") would have that request silently ignored, because False is falsy and would never enter the if block! Using is not None correctly distinguishes "the caller didn't mention this field at all" (None) from "the caller explicitly set it to False" (a real, intentional value). This is a crucial, easy-to-get-wrong pattern for any optional boolean field in a partial update — good one to actually notice, not skim past.

# role.name = name
# Plain attribute assignment on an already-loaded model instance — this only changes the Python object in memory; nothing is written to the database yet.

# role.save()
# This is what actually persists any changed attributes back to the database — the counterpart to .create() you saw before, but for an existing row rather than a new one. .create() = build + save in one step for a new object; .save() = write current in-memory field values for an existing object.

# invalidate_role_permissions_cache(role=role)
# A function call to clear some cached data related to this role's permissions. This tells you something architecturally important: somewhere else in your project, a role's effective permissions are cached (probably to avoid recomputing "what can this role do" on every single request — a reasonable performance optimization for a permission system that's checked constantly). Whenever the underlying permissions actually change, that cache would go stale unless something explicitly clears it — this line is that cleanup step, called only when permission_codenames was actually part of this update.

# 3. Signature — broken into pieces
# python
# def update_role(
#     *, role_id, company_id, name=None, permission_codenames=None, is_default=None
# ):
# Piece	Meaning
# *,	all keyword-only
# role_id	required — which role to update
# company_id	required — security scope, same reasoning as list_roles
# name=None	optional — None means "don't touch this field"
# permission_codenames=None	optional — same sentinel meaning
# is_default=None	optional — same sentinel meaning, and this time the sentinel distinction is load-bearing, as explained above

# Again: zero type hints anywhere, same drift you flagged in create_role. Worth noting the honest types here would include something like Optional[bool] for is_default — and writing that hint explicitly would make the "sentinel value" design intentional and visible to any future reader, rather than something you have to infer from behavior.

# 4. Body — line by line
# python
# role = Role.objects.filter(pk=role_id, company_id=company_id).first()
# if not role:
#     raise ApplicationError(message="Role not found.", code=ErrorCode.ROLE_NOT_FOUND)

# Fetch the role, scoped to the caller's company. If missing (or belongs to someone else), reject immediately — nothing below runs.

# python
# if name is not None:
#     name = name.strip()
#     if len(name) < 2:
#         raise AppValidationError(...)
#     role.name = name

# Only touch the name if one was actually provided; validate it exactly like create_role did, then stage the change on the in-memory object.

# python
# if is_default is not None:
#     role.is_default = is_default

# Only touch is_default if explicitly provided — correctly handling False as a real, intentional value (as explained above).

# python
# role.save()

# Persist whatever changes were staged above (name and/or is_default) to the database in one write.

# python
# if permission_codenames is not None:
#     permissions = list(Permission.objects.filter(codename__in=permission_codenames))
#     unknown = set(permission_codenames) - {p.codename for p in permissions}
#     if unknown:
#         raise AppValidationError(...)
#     role.permissions.set(permissions)
#     invalidate_role_permissions_cache(role=role)

# Only touch permissions if the caller sent a list at all (note: an empty list [] here is not None, so this would run and correctly clear all permissions — a meaningful, valid partial-update case, unlike name/is_default where the distinction was about booleans). Validate exactly like create_role, then replace the role's permission set entirely, and clear the stale cache.

# python
# return role

# Hand back the now-updated role.

# 5. Why?

# Why is not None here, but if category: truthiness in list_permissions?
# This is the single most important thing to take from this file: the right check depends on what "not provided" needs to mean for that specific type. For a string filter like category, treating both None and "" as "no filter" is harmless and convenient. For a boolean field being set, False is a completely valid, distinct value from "don't change this" — collapsing them with a truthiness check would silently break a real use case. Always ask: "is there a legitimate, meaningful falsy value this field could hold?" If yes (booleans, 0, empty lists that mean 'clear everything'), use is not None. If no meaningful falsy value could ever be intentional, a plain truthiness check is fine and reads more simply.

# Why does permission_codenames=[] (a caller wanting to clear all permissions) still work correctly here?
# Because [] is not None evaluates to True — an empty list is not None, so this branch still runs, correctly setting role.permissions.set([]), which clears everything. This is exactly the right behavior for a permission-clearing request, and it only works because the code used is not None rather than a truthiness check (if permission_codenames: would have been a bug — it would silently skip clearing permissions when the caller explicitly asked for zero permissions).

# Why invalidate the cache only inside this if block, not unconditionally at the end?
# Because the cache is specifically about permissions — invalidating it when only the name changed would be pointless extra work. Scoping the cache-clear to exactly the branch that could have changed permission data is the efficient, correct choice.

# 6. Connections

# What comes in: the role's ID and company (for lookup/security), plus any subset of fields to change.
# What goes out: the updated Role, or one of ApplicationError (not found) / AppValidationError (bad input).
# Where this fits: called from a RoleMutation-style resolver, the write-side counterpart to get_role. The invalidate_role_permissions_cache import comes from authorization/selectors/get_user_permissions — meaning somewhere, a selector computes a user's effective permissions (likely combining role permissions + the UserPermissionOverride records you read about earlier) and caches that computation; this service is responsible for telling that cache "your data is now stale" whenever role permissions change directly.

# A naming detail worth flagging (same pattern as UserPermissionOverride living in user_role.py): invalidate_role_permissions_cache is imported from a file literally called get_user_permissions.py — a selector file (typically read-only lookups) apparently also contains a cache-invalidation function, which is more of a write/mutation concern. Worth being a little suspicious of this placement — it might make more sense living in a services file, since invalidating a cache is arguably a side-effecting action, not a query. Not necessarily wrong, but worth noticing as you build a feel for where your project draws its lines.

# 7. Advanced concepts

# A) The is not None sentinel pattern for partial updates, generalized
# This is a widely-used real-world pattern, not just a one-off trick: when a function needs to support "update only the fields you send me," and any of those fields could have a meaningful falsy value (False, 0, "", []), the only safe way to detect "was this field sent at all?" is to use None (or another dedicated sentinel) as the default, and check is not None explicitly — never a plain truthy check. GraphQL and REST PATCH endpoints hit this constantly.

# B) A subtlety: role.save() happens before permission validation — is that a problem?
# Look at the order: the code validates and saves name/is_default changes, calling role.save(), and only after that does it validate permission_codenames (which could raise AppValidationError for an unknown codename). If that validation fails, the function raises — but the name/is_default change already got written via .save(). Is this a bug?

# No — because of @transaction.atomic. Even though role.save() executes before the exception is raised, the entire function is wrapped in one atomic transaction. Django will roll back everything, including that earlier .save(), once the exception propagates out of this function. So there's no actual data-integrity problem. However, it's still worth noticing as a style/fail-fast concern: create_role validates name and permissions before writing anything at all; this function validates name, writes it, and only then validates permissions. It works correctly, but doing all validation before any writes (like create_role does) is generally considered cleaner and easier to reason about — you don't have to rely on remembering "oh right, the atomic decorator saves us here" to convince yourself it's safe.

# C) Duplicated validation logic — a DRY opportunity
# The permission-lookup-and-validate block here (list(Permission.objects.filter(codename__in=...)), the set difference, the AppValidationError raise) is copy-pasted nearly identically from create_role. This is a natural candidate for extraction into a shared helper, e.g., resolve_permissions_or_raise(codenames) used by both services — worth recognizing duplicated logic like this as a refactoring opportunity when you start writing your own services.

# 8. Small example
# python
# class Role:
#     def __init__(self, name, is_default):
#         self.name = name
#         self.is_default = is_default

# def update_role(role, *, name=None, is_default=None):
#     if name is not None:
#         role.name = name.strip()
#     if is_default is not None:      # correctly handles False!
#         role.is_default = is_default
#     return role

# r = Role(name="Manager", is_default=True)
# update_role(r, is_default=False)     # explicitly turning OFF default
# print(r.is_default)                  # False — correctly applied

# update_role(r)                       # nothing provided
# print(r.name, r.is_default)          # unchanged — "Manager", False
# 9. What you should remember
# is not None vs. plain truthiness is a real design decision, not a stylistic preference — use is not None whenever the field could legitimately hold a meaningful falsy value (False, 0, [], ""); a plain if field: would silently swallow those valid inputs.
# role.name = x then role.save() is the standard "load, mutate, persist" pattern for updating an existing Django model — distinct from .create(), which builds and saves a new row in one step.
# @transaction.atomic makes ordering-of-validation mistakes "safe" (nothing partially commits) but doesn't make them good style — prefer validating everything before writing anything, even when the safety net exists, because it's easier for humans to reason about later.
# When you see the same validation block appear in two different functions almost verbatim, that's a signal to extract a shared helper — recognizing duplication is a core code-reading skill, even before you're the one fixing it.
# A cache-invalidation call appearing right after a data change is a strong signal that some other part of the codebase caches a computed result — trace it back (as we did to get_user_permissions) to understand what's actually being kept fresh, and q