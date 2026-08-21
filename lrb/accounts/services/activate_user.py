from  __future__ import annotations
from typing import TYPE_CHECKING
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User
    
@transaction.atomic
def activate_user(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User Not Found", code= ErrorCode.USER_NOT_FOUND)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user



# 1. Purpose — Why this exists

# What problem is this solving?
# The mirror image of deactivate_user — some accounts get suspended, put on hold, or deactivated for review, and eventually need to be reinstated. This function flips is_active back to True.

# Why not just write user.is_active = True; user.save() wherever this is needed?
# Same reasoning as every other single-flag action you've built — one trusted place to do the lookup, the not-found handling, and the narrow save, rather than duplicating it per caller.

# When is this used?
# A staff "reactivate account" action — reversing a prior deactivation, or activating an account that was created inactive for some reason.

# What breaks without it?
# Duplicated lookup-and-save logic scattered wherever reactivation needs to happen, with the usual risk of inconsistent not-found handling.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import TYPE_CHECKING
# from django.db import transaction
# from lrb.accounts.selectors.get_user import get_user
# from lrb.core.exceptions import ApplicationError, ErrorCode

# if TYPE_CHECKING:
#     from lrb.accounts.models import User

# Every piece of this you've now built from scratch across several files — from __future__ import annotations letting -> User work unquoted, TYPE_CHECKING correctly guarding the User import (checking your own test: User never appears as running code in this body, only as the return annotation — correct to guard it), transaction for the atomic decorator, get_user via direct submodule import, and the now-familiar ApplicationError/ErrorCode pair for the not-found case.

# Notice what's absent here, compared to deactivate_user, demote_owner, lock_user, and delete_user: no from lrb.accounts.services.ownership_guard import assert_not_last_owner. Hold that thought — it's the most important thing to understand about this file, and we'll come back to it properly in Section 7.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def activate_user(*, user_id: str) -> User:

# Nothing new mechanically — matches force_password_reset's and the corrected deactivate_user's shape exactly: atomic decorator (a read plus a write, grouped), keyword-only *, one required user_id: str, and -> User promising a real object on success, an exception on failure.

# Naming check, since we just caught this exact issue in a sibling file: activate_user is correctly singular, matching its single user_id parameter and single User return — no repeat of the deactivate_users naming mismatch from a few turns ago.

# 4. Classes

# No class defined — User appears only in the return annotation, never constructed or referenced by name in the body, matching the pattern you've now confirmed across every sibling file in this group.

# 5. Body — line by line
# python
# user = get_user(user_id=user_id)
# if user is None:
#     raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)

# Exactly the fetch-and-guard shape from the previous walkthrough — get_user's parameter (the keyword on the left) filled by activate_user's own local variable (the value on the right), same mechanism you just traced end-to-end. code= is correctly passed as a keyword here (unlike the bug we caught in the earlier draft of deactivate_users), so this line will actually construct and raise ApplicationError correctly if reached.

# python
# user.is_active = True
# user.save(update_fields=["is_active"])
# return user

# The same single-flag pattern as force_password_reset and the corrected deactivate_user — direct attribute assignment, a narrow update_fields save touching only the one changed column, then returning the same in-memory, now-updated object.

# 6. Beginner questions, answered proactively

# Why is there no full_clean() call here, same question as force_password_reset?
# Same answer as before — a single boolean flip has nothing meaningful to validate that full_clean() would catch, and running full-model validation here would just add overhead without protecting anything relevant to this specific change.

# Why update_fields=["is_active"] instead of a full unguarded .save()?
# Same reasoning as every prior single-flag function — narrower, faster write, and immune to accidentally clobbering other fields that might have changed concurrently on the same row between fetch and save.

# 7. Design discussion — why this file correctly has NO ownership guard

# This is the most important thing to understand from this particular file, and it's a great test of whether the pattern-recognition you've built actually transfers, rather than being applied mechanically everywhere.

# Ask the question assert_not_last_owner exists to answer: "could this action leave the company with zero active superusers, or does it touch the untouchable founder?" Both of those questions are only meaningful for actions that remove or reduce someone's standing — demoting an owner, deactivating someone, deleting someone, locking someone out. Every one of those actions could, in principle, be the one that tips a company from "has an owner" to "has none."

# activate_user does the opposite. It reinstates someone. There is no version of this action where flipping is_active from False to True could ever reduce the number of active superusers at a company — if anything, reactivating a superuser can only ever increase or maintain that count, never decrease it. The entire premise the guard function protects against — "are we about to remove the last one" — simply cannot apply here, no matter who the target is, founder or not.

# This is exactly why its correct absence here is worth calling out explicitly, not just noting as "nothing to add." A less careful pass at building this file might have copy-pasted the guard call reflexively from deactivate_user "to be safe," the same instinct that produced the flawed if user.company_id: wrapper in earlier files. The correct engineering judgment here isn't "add every safety check everywhere" — it's "understand exactly what each check protects against, and only apply it where that specific risk actually exists." Reflexive over-guarding is its own kind of bug: it would mean, absurdly, that reactivating a suspended founder's account could raise "The founder's account cannot be activated" — blocking a completely safe, even necessary, administrative action for a risk that was never present in the first place.

# 8. DIY Recipe — build one like this yourself
# Before adding any guard call, name exactly what harm it prevents, then check whether this specific action could actually cause that harm. If the action moves in the opposite direction of the risk (restoring, granting, reinstating, rather than removing, revoking, demoting), the guard almost certainly doesn't apply.
# Fetch and guard for existence, as always.
# For a simple reinstatement flag, flip it directly and save narrowly with update_fields — no validation, no invariant checks needed if there's genuinely nothing to protect against.
# Resist copy-pasting a safety check from a sibling "opposite" function just because the two files look structurally similar — structural similarity doesn't imply the same risks apply.
# 9. General pattern recognition

# This is the simplest form of the "single-flag action" pattern you've now seen several times — fetch, guard, flip, save narrowly, return — with the added lesson that not every member of a family of similar functions needs every safety mechanism the others have. create_user/update_user share exception-translation logic; deactivate_user/demote_owner/lock_user/delete_user share the ownership guard; activate_user correctly shares neither the email-uniqueness handling nor the ownership guard, because neither risk applies to what it does.

# 10. Real project usage
# python
# def resolve_activate_user(self, info, user_id: str) -> UserPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     try:
#         user = activate_user(user_id=user_id)
#     except ApplicationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     return UserPayload(success=True, user=user)
# 11. Common beginner mistakes

# ❌ Reflexively adding assert_not_last_owner to every function that touches is_active or similar flags, without checking whether the specific direction of the change (restoring versus removing) actually carries the risk the guard protects against.

# ❌ Forgetting the not-found guard, on the assumption "this one's simple, surely nothing can go wrong" — the ID could still be stale or invalid regardless of how simple the eventual write is.

# ❌ Using a full .save() instead of update_fields, treating it as unimportant for "just a boolean" — the stale-data risk is identical regardless of which single field is being changed.

# 12. Think like the original developer
# What problem am I solving? "Reinstate a deactivated user's account, cleanly, in one trusted place."
# What inputs will I need? Just the user's ID — nothing else determines whether this write can happen.
# What could go wrong? The ID doesn't correspond to a real user. That's genuinely the only failure mode here — there's no invariant this specific direction of change could violate.
# How should I report failure? The same ApplicationError/USER_NOT_FOUND vocabulary used everywhere else for "record doesn't exist."
# What should happen if everything works? Flip the one field, save narrowly, return the updated object — and no more than that, since nothing else about this action carries risk worth guarding against.
