from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def demote_owner(*, user_id: str, company_id: str) -> User:
    user = get_user(user_id=user_id)
    if user is None:
        raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)
    if not user.is_superuser:
        raise ApplicationError("User Is Not Owner", code=ErrorCode.VALIDATION_ERROR)
    assert_not_last_owner(user=user, company_id=company_id, action="demoted")
    user.is_superuser = False
    user.save(update_fields=["is_superuser"])
    return user



# 1. Purpose — Why this exists

# What problem is this solving?
# Removing someone's superuser (owner) status is a meaningfully dangerous action — it needs to: confirm the target actually exists, confirm they're actually a superuser to begin with (demoting someone who isn't one makes no sense), confirm this wouldn't leave the company with zero owners or touch the untouchable founder, and only then actually flip the flag.

# Why not just set user.is_superuser = False directly wherever this is needed?
# Because skipping any of those checks — especially the last-owner/founder guard — is exactly how a company ends up locked out of its own admin capabilities, which is the whole scenario count_active_superusers and assert_not_last_owner were built to prevent.

# When is this used?
# A staff/admin action — "remove owner privileges from this person" — on a role/permissions management screen.

# What breaks without it?
# Without the guard call, a company could lose its last superuser. Without the "is this actually a superuser" check (even though, as we'll see, it's currently broken), a caller could invoke this on someone who was never a superuser, and get a confusing or misleading response.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import TYPE_CHECKING
# from django.db import transaction
# from lrb.accounts.selectors.get_user import get_user
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# from lrb.core.exceptions import ApplicationError, ErrorCode

# if TYPE_CHECKING:
#     from lrb.accounts.models import User

# Every piece here you've now seen and can verify yourself. Quick check on the TYPE_CHECKING decision, applying your own test from a few turns ago: does User appear anywhere as real running code in this file, or only as an annotation? Scanning the body — user (lowercase, an object) is used throughout, but the literal name User only ever appears once, in -> User. Correctly guarded, same as force_password_reset.

# One new, useful detail: from lrb.accounts.services.ownership_guard import assert_not_last_owner — this confirms exactly where that guard function actually lives: the services module (not selectors), inside a file called ownership_guard.py. That placement makes sense given what you learned about it — it's not a read-only query itself (even though it calls one), and its entire purpose is gating a write action, which is a services-layer concern.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def demote_owner(*, user_id: str, company_id: str) -> User:

# Nothing new mechanically here — @transaction.atomic because this reads, checks, and writes as one unit; keyword-only *; two required string parameters (no defaults — you can't demote "someone" from "some company," both are mandatory); -> User promising a real object back, never None.

# 4. Classes

# No class here — User appears only as a type, never constructed (matches the force_password_reset pattern exactly).

# 5. Body — line by line
# Fetch and guard
# python
# user = get_user(user_id=user_id)
# if user is None:
#     raise ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)

# Identical shape to every fetch-and-guard block you've now seen three times — reusing get_user, translating None into ApplicationError.

# The "is this actually an owner" check — here's the bug
# python
# if user.is_superuser is None:
#     raise ApplicationError("User Is Not Owner", code=ErrorCode.VALIDATION_ERROR)

# Read it exactly the way we've been reading conditions: user.is_superuser is None — this asks "is the value of is_superuser literally the Python object None?"

# Here's the problem: is_superuser is a BooleanField on your User model (you saw it constructed as is_superuser=False back in create_user's parameter list, always with a concrete default of True or False, never None). A standard Django BooleanField cannot hold None unless it was explicitly declared with null=True — and even if it technically could, nothing in this codebase treats None as a valid state for this field; every place you've seen it, it's always either True or False.

# That means user.is_superuser is None will always evaluate to False, for every single user, every single time. This if block can never execute. The check that's supposed to catch "you're trying to demote someone who isn't even an owner" silently never fires — a non-superuser could be passed into this function, sail straight past this line, get run through assert_not_last_owner (which itself would just return immediately, since assert_not_last_owner's very first line is if not user.is_superuser: return — meaning the guard does nothing for a non-superuser either), and then have is_superuser = False "set" on them — a no-op, since it was already False — and get .save()d and returned as if the demotion succeeded.

# What the check almost certainly meant to say:

# python
# if not user.is_superuser:
#     raise ApplicationError("User Is Not Owner", code=ErrorCode.VALIDATION_ERROR)

# not user.is_superuser is True when the field is False — which is the actual, real-world "this person isn't an owner" case, unlike checking for None, a value this field never holds in practice.

# Why is this bug easy to miss reading top-to-bottom? Because the rest of the line reads perfectly — the error message, the error code, the exception type are all exactly right. Only the specific comparison (is None versus not ... / is False) is wrong, and it's the kind of typo that looks entirely plausible at a glance, especially right after you've spent several files carefully distinguishing is not None from plain truthy checks (in update_user) — it's easy to reach for is None/is not None out of habit even when the field in question is a boolean, not an Optional.

# The ownership guard
# python
# assert_not_last_owner(user=user, company_id=company_id, action="demoted")

# Exactly the call we predicted when we first walked through assert_not_last_owner's "real project usage" section — action="demoted" here, matching this specific caller's wording, versus a hypothetical action="deactivated" elsewhere. This raises if user is the founder, or if demoting them would leave zero active superusers at the company.

# The actual demotion
# python
# user.is_superuser = False
# user.save(update_fields=["is_superuser"])
# return user

# Same single-flag pattern as force_password_reset — direct attribute assignment, then a narrow update_fields save touching only the one column that changed, then return the same in-memory object.

# 6. Beginner questions, answered proactively

# If the broken check never fires, does anything bad actually happen right now, given assert_not_last_owner also short-circuits on non-superusers?
# Practically, the dangerous outcome (locking out a company) is still prevented, because assert_not_last_owner's own early exit independently protects against demoting a non-superuser into some invalid state. But the intended behavior — clearly telling the caller "this action doesn't make sense, they're not an owner" — is lost. Instead, calling demote_owner on an ordinary staff member currently succeeds silently, returning the user unchanged with is_superuser still False, giving no signal that nothing meaningful happened. That's a UX/correctness bug, not a security hole — but still a real bug worth fixing.

# Why use ErrorCode.VALIDATION_ERROR here instead of a new, more specific code like the CANNOT_MODIFY_FOUNDER/LAST_OWNER codes from assert_not_last_owner?
# Worth flagging as a design question rather than assuming it's deliberate — a more specific code (say, ErrorCode.NOT_AN_OWNER) would let a frontend show a precisely tailored message, the same way the two codes in assert_not_last_owner each map to distinct wording. Reusing the generic VALIDATION_ERROR works but loses that precision.

# Why check "is this actually an owner" before calling assert_not_last_owner, rather than just letting assert_not_last_owner's own early exit handle it?
# Because they answer different questions for the caller. assert_not_last_owner's silent early-return (if not user.is_superuser: return) is designed for guard functions that get called unconditionally from many places — it stays quiet on purpose, so callers don't need to pre-check anything. But this function's whole purpose statement includes "demote an owner" — if the target was never an owner, that's a meaningful, reportable error specific to this action, not something that should be silently absorbed the way it currently is due to the bug.

# 7. Design discussion

# Why does this function duplicate get_user's fetch-and-guard pattern instead of, say, assert_not_last_owner doing the fetch itself?
# Because assert_not_last_owner takes an already-fetched user object as a parameter, not an ID — a deliberate design choice, since it's meant to be reusable from services that have already fetched their target for other reasons (checking permissions, applying other field changes) before reaching the point where this guard needs to run. Keeping assert_not_last_owner fetch-agnostic makes it composable across different callers with different existing context.

# Trade-off worth naming for the actual bug: once fixed, this function will have three distinct guard layers before the actual write — not-found, not-an-owner, and last-owner/founder — each raising a different, specific error. That's arguably the right amount of precision for an action this consequential, even though it means more lines than a bare user.is_superuser = False.

# 8. DIY Recipe — build one like this yourself
# Fetch and guard for existence first, same as every service.
# For boolean state-check preconditions ("is this actually true right now"), use not field or field is False — never field is None unless you've specifically confirmed the field is nullable and None is a real, distinct state you're modeling.
# Call your invariant-protecting guard function (like assert_not_last_owner) after confirming the basic precondition holds, so the guard's own silent-exit behavior doesn't accidentally absorb a case your calling function actually wants to report distinctly.
# Use update_fields for single-flag writes, consistent with force_password_reset.
# When testing a function like this, write a test case specifically for "call this on someone who is not currently an owner" — this is exactly the kind of case a broken is None check would pass silently instead of failing loudly, and only a targeted test (not just eyeballing the code) reliably catches it.
# 9. General pattern recognition

# This combines two patterns you already know how to name: "fetch and guard" (from update_user/force_password_reset) followed by "assert invariant" (calling assert_not_last_owner) before a "single-flag action" write (matching force_password_reset's save style). Recognizing a new file as a composition of patterns you've already named — rather than something wholly unfamiliar — is exactly the fluency this whole exercise has been building toward.

# 10. Real project usage
# python
# def resolve_demote_owner(self, info, user_id: str, company_id: str) -> UserPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_roles")
#     try:
#         user = demote_owner(user_id=user_id, company_id=company_id)
#     except ApplicationError as e:
#         return UserPayload(success=False, errors=[e.to_error_response()])
#     return UserPayload(success=True, user=user)
# 11. Common beginner mistakes

# ❌ The exact bug in this file — checking is None against a plain boolean field that never holds None, silently disabling the intended check entirely. Worth internalizing as its own named trap: a condition that can never be true fails silently, not loudly — no crash, no error, just a check that quietly does nothing, forever, until someone specifically tests the case it was meant to catch.

# ❌ Assuming a guard function's silent early-exit covers every case your caller needs reported — assert_not_last_owner's quiet return for non-superusers is correct for its own purpose, but doesn't substitute for this function's own, more specific "not an owner" error.

# ❌ Reusing a generic error code (VALIDATION_ERROR) for a case specific enough to deserve its own named code, losing precision a frontend could otherwise use.

# 12. Think like the original developer
# What problem am I solving? "Remove someone's owner status, safely — confirming they exist, confirming they're actually an owner, and confirming this won't break the company's ownership invariants."
# What inputs will I need? The target user's ID and the company context (needed by the last-owner check).
# What could go wrong? The ID doesn't exist; the target isn't actually an owner (a case that needs a real, working check — is None was the wrong comparison for a boolean field); demoting them would violate the founder or last-owner invariant.
# How should I report failure? Three distinct, specific errors for three distinct failure reasons — not found, not an owner, or blocked by the ownership guard — each clear enough for a frontend to act on differently.
# What should happen if everything works? Flip exactly one field, save narrowly, return the updated user — matching the exact shape of force_password_reset, since both are single-flag security actions.