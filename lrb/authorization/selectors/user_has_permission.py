from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User

def user_has_permission(*, user: User, codename:str) -> bool:
    if user.is_superuser:
        return True
    from lrb.authorization.selectors.get_user_permissions import get_user_permission_codenames
    return codename in get_user_permission_codenames(user=user)


# This is a small but important function: the actual permission check your services call — likely what's inside require_permission(). It also has a type hint mistake worth catching, since you're learning to read code critically.

# Signature
# python
# def user_has_permission(*, user: str, codename: str) -> bool:
# def user_has_permission(...) — a plain function.
# *, — same keyword-only marker from the last file. Both user and codename must be passed by name: user_has_permission(user=some_user, codename="can_edit_orders").
# user: str — a type hint saying "expects a string."
# codename: str — same, a string (the permission's codename, matching the Permission model field you saw earlier).
# -> bool — returns True or False.

# Catch the bug: user: str is almost certainly wrong. Look at the very next line — user.is_superuser. Strings don't have an .is_superuser attribute; only your Django User model does (you saw is_superuser listed as a real field on UserType back in your first file). This type hint should be user: User (or whatever your actual model/type is), not user: str. This is a common real-world mistake: a type hint that doesn't match how the value is actually used in the body. Type hints don't stop Python from running "wrong" code — they're just documentation for humans and tools (like editors and type-checkers); Python itself won't complain until something actually crashes at runtime. If you ran this with a real string, user.is_superuser would raise an AttributeError immediately.

# Body
# python
#     if user.is_superuser:
#         return True

# Line by line

# if user.is_superuser: — accesses the is_superuser field on the User object. This is a genuine boolean field on the model (you've seen it before, on UserType).
# return True — if the user is a superuser, stop here immediately and say "yes, they have this permission" — no further checking needed.

# Why?
# This matches your project's require_owner() vs require_permission() split. A superuser (the "owner" tier) should bypass the whole granular permission system entirely — they're not meant to need individual permissions assigned; they can do everything by definition. This is a classic short-circuit / early-exit pattern: handle the special, simple case first and return immediately, so the rest of the function only has to deal with the "normal user" case.

# python
#     from lrb.authorization.selectors.get_user_permissions import get_user_permission_codenames
#     return codename in get_user_permission_codenames(user=user)
# The local import — same technique from your last file (avoiding circular imports), pulling in the get_user_permission_codenames function you just learned about. Notice the file path: lrb.authorization.selectors.get_user_permissions — the folder is literally called selectors, confirming your project's service/selector separation. A selector is a function whose job is purely to read/compute data (like "what permissions does this user have?"), as opposed to a service, which changes data. user_has_permission is itself acting as a selector here too — it only answers a question, it doesn't modify anything.
# codename in get_user_permission_codenames(user=user) — calls the function from your last file, which returns a set[str] of all codenames this user effectively has (roles + overrides, already cached). The in operator checks membership: "is this exact string present in that set?" This is exactly why get_user_permission_codenames returns a set rather than a list — checking in on a set is very fast (near-instant, regardless of size), while checking in on a list gets slower as the list grows, because Python has to scan through it item by item.
# return ... — the result of that in check (True/False) is returned directly, without needing an if/else — the comparison itself already produces a boolean, so there's nothing to wrap it in.
# Why this design?

# This function is a clean two-tier permission model:

# Superusers — unconditional access, checked with a single fast attribute lookup, no database/cache involvement at all.
# Everyone else — falls through to the cached, role/override-based lookup you built up in the last few files.

# Putting the superuser check first, before touching get_user_permission_codenames, is also a small performance win: for superusers, you skip the cache lookup and the whole selector chain entirely — the cheapest possible check happens first.

# Advanced concept: reading this function "in layers"

# Using the reading technique you've been practicing — find the action first, then who, then the input:

# Line 1's action is a comparison/branch (if), acting on user.is_superuser.
# Line 2's action is return True — a direct, unconditional answer.
# Line 4's action is return, and the thing being returned is the result of in — so read right-to-left in a sense: first figure out what get_user_permission_codenames(user=user) produces (a set of strings), then check whether codename is inside it, and that whole expression is what gets returned.
# Small example
# python
# class FakeUser:
#     is_superuser = False

# alice = FakeUser()
# user_has_permission(user=alice, codename="can_edit_orders")
# # Skips the superuser branch, calls get_user_permission_codenames(user=alice),
# # then checks "can_edit_orders" in {"can_view_orders", "can_edit_orders"} -> True
# Connections

# This is very likely the exact function called inside require_permission(codename):

# python
# def require_permission(*, user, codename):
#     if not user_has_permission(user=user, codename=codename):
#         raise MutationError(...)

# Which in turn is called at the top of a service function, before any @transaction.atomic write happens — the enforcement point your RBAC project is built around.

# What I should remember
# A type hint can be wrong without Python complaining — always check the type hint against how the variable is actually used in the body; user.is_superuser only makes sense if user is a model instance, not a str.
# Handle special/simple cases first with an early return, so the rest of the function only deals with the general case — cleaner logic, and often faster too.
# x in a_set is a fast membership check — this is why the previous function returned a set[str] instead of a list.
# "Selector" = reads/computes data; "service" = changes data. Your folder structure (selectors/) makes this distinction visible at a glance, not just a naming convention in your head.
# A boolean comparison (in, ==, is) can be returned directly — no need for if x: return True else: return False when the comparison already gives you the boolean you want.