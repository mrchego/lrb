from __future__ import annotations
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def unlock_user(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
    user.locked_until = None
    user.failed_login_attempts = 0
    user.save(update_fields=["locked_until", "failed_login_attempts"])
    return user


# 1. Purpose — Why does this exist?

# What problem is this solving?
# Most auth systems lock an account after too many failed login attempts — a defense against brute-force password guessing. But that lockout needs an "escape hatch": a support agent, admin, or automated process that says "okay, this was a false alarm, let this person back in."

# Why not just let the lockout expire on its own?
# Because sometimes you don't want to wait. A legitimate user calls support after getting locked out — someone needs a way to manually clear the lock immediately rather than telling them "try again in 30 minutes."

# What happens if this code doesn't exist?
# Support staff would have no way to manually unlock an account short of going into the database directly and editing rows by hand — risky, unaudited, and not something you want non-engineers doing.

# 2. Imports
# python
# from django.db import transaction
# from lrb.accounts.models import User
# from lrb.accounts.selectors import get_user

# Nothing new here versus last time — same three ingredients as delete_user: the atomic-transaction tool, the User model (used only as a type hint here, notice — it never appears in the body), and the get_user selector.

# One thing worth flagging: this file does not import ApplicationError or ErrorCode. Hold that thought — it matters in a minute.

# 3. Function Signature
# python
# @transaction.atomic
# def unlock_user(*, user_id:str) -> User:

# Same shape as before:

# @transaction.atomic — wrap this in an all-or-nothing database transaction.
# def unlock_user — name the recipe.
# (*, user_id:str) — the * forces user_id to be passed by keyword only. Same reasoning as before: keeps call sites unambiguous and future-proof if more parameters get added later (e.g. unlocked_by=).
# -> User — promises to hand back a User object.

# (Small style note, not a functional issue: user_id:str is missing the space after the colon that delete_user had — user_id: str. Python doesn't care, but most style guides — PEP8 — would flag this in a linter. Cosmetic only.)

# 4. Body — line by line
# Line 1
# python
# user = get_user(user_id=user_id)

# Same as before: ask the selector to find a user by ID. Store whatever comes back — a User object, or None — in user.

# Line 2
# python
# user.locked_until = None

# Who? user.
# What's being done? Setting the attribute locked_until to None.

# This field is presumably a datetime — "this account is locked until such-and-such time." Setting it to None means "there is no lock in effect." This is the actual unlocking action.

# Line 3
# python
# user.failed_login_attempts =  0

# Reset the failed-attempt counter back to zero. This matters for a subtle reason: if you only cleared locked_until but left failed_login_attempts at, say, 5, the very next failed login might immediately re-trigger the lockout (if the lockout logic is "5 failed attempts → lock"). Resetting the counter gives the user a genuinely clean slate, not just a temporary reprieve.

# (Tiny cosmetic note: =  0 has two spaces before 0 instead of one. Doesn't affect anything — Python ignores extra whitespace around = — but again, a linter would flag it.)

# Line 4
# python
# user.save(update_fields=["locked_until", "failed_login_attempts"])

# Same pattern as delete_user: write only these two changed columns to the database, using update_fields to avoid clobbering unrelated fields another process might have changed concurrently.

# Line 5
# python
# return user

# Hand back the modified User object, fulfilling the -> User promise.

# 5. Design Discussion — and the bug this reveals

# Here's where comparing this file to delete_user really pays off.

# delete_user had this:

# python
# user = get_user(user_id=user_id)
# if not user:
#     raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

# unlock_user has this:

# python
# user = get_user(user_id=user_id)
# user.locked_until = None

# No if not user: check. If get_user returns None (because user_id doesn't exist, or was mistyped, or belongs to a deleted user), the very next line — user.locked_until = None — will crash with:

# AttributeError: 'NoneType' object has no attribute 'locked_until'

# This is a real, catchable bug, not a style nitpick. It's the exact kind of thing your "read every line, ask what could go wrong" habit is designed to catch. delete_user and unlock_user should almost certainly share this pattern, since they both start with the identical get_user(user_id=user_id) call — one of them (this one) is missing a guard the other has.

# Why does this matter more than it might seem? This function is presumably going to be called from something like an admin "unlock user" button where an ID gets typed or pasted in. A stale ID, a copy-paste mistake, a race condition where the user was deleted moments earlier — any of these turns into an ugly unhandled 500 error instead of a clean "user not found" response.

# Design principle worth naming: whenever two functions in the same codebase start with the same lookup call (get_user(user_id=user_id)), they should handle the "not found" case the same way, unless there's a specific reason not to. Inconsistency here is a sign the second function was probably copy-pasted from a simpler example and had its guard clause trimmed out — or was written independently by someone who forgot it.

# 6. Common Beginner Mistakes (this file as the case study)

# ❌ Missing null-check after a lookup function. Any time you call something like get_x(id=...) that might return None, the very next line touching that result needs a guard — otherwise you're one bad ID away from a crash.

# ❌ Not being consistent with sibling functions in the same module/package. If delete_user validates existence, unlock_user should too — same file family, same expectations.

# ❌ Silently trusting that user_id is always valid because "the frontend already checked it." Frontends lie, get out of sync, or get bypassed by direct API calls — backend services must defend themselves independently.

# 7. DIY Recipe — the fix, and how you'd build this yourself from scratch

# If you were designing this function from nothing, your mental checklist (per your own framework) would be:

# What am I looking up? A user, by ID.
# What could go wrong? The ID doesn't match anyone.
# How should I report that? The same way the rest of this codebase reports "not found" — reuse ApplicationError + ErrorCode.USER_NOT_FOUND, exactly like delete_user does. Don't invent a new pattern for the same problem.
# What should happen if everything works? Clear the lock fields, save only those fields, return the object.

# The corrected version, using the exact convention already established in delete_user:

# python
# from django.db import transaction
# from lrb.accounts.models import User
# from lrb.accounts.selectors import get_user
# from lrb.core.exceptions import ApplicationError, ErrorCode


# @transaction.atomic
# def unlock_user(*, user_id: str) -> User:
#     user = get_user(user_id=user_id)
#     if not user:
#         raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

#     user.locked_until = None
#     user.failed_login_attempts = 0
#     user.save(update_fields=["locked_until", "failed_login_attempts"])
#     return user
# 8. Real Project Usage

# Called from something like:

# An admin/support dashboard "Unlock Account" button
# An internal API endpoint restricted to staff permissions (this is where RBAC actually intersects with this file — you'd want a permission check above this function, in the view, ensuring only staff/admins can call unlock_user at all)
# Possibly a scheduled task that auto-unlocks accounts after a cool-down, though that's more likely handled by locked_until simply expiring on its own without needing this function

# Two files in, and you're already spotting the shape of this codebase's conventions well enough to notice when a function breaks them. That's the pattern-recognition your document talks about kicking in. Want to keep going with more service files, or is this a good point to jump into the actual RBAC/permission-checking code (roles, permissions, decorators) — since that's the part that'll be more novel territory?
