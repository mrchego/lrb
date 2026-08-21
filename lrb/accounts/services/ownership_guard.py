from __future__ import annotations
from lrb.accounts.selectors import count_active_superusers
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


def assert_not_last_owner(*, user: User, company_id:str, action: str="modified")-> None:
    if not user.is_superuser:
        return
    
    if user.is_founder:
        raise ApplicationError(
            f"The founder's account cannot be {action}.",
            code=ErrorCode.CANNOT_MODIFY_FOUNDER,
        )
        
    remaining = count_active_superusers(company_id=company_id, exclude_ids=[str(user.id)])
    if remaining == 0:
        raise ApplicationError(
            f"This is the last active owner of the company and cannot be {action}.",
            code=ErrorCode.LAST_OWNER,
        )
        
# 1. Purpose — Why this exists

# What problem is this solving?
# This is a guard function — its entire job is to answer "is it safe to do this thing to this user?" and raise loudly if not, before any actual modification happens. Specifically, it protects two related-but-distinct invariants: (1) a company's founder account can never be modified through normal staff actions, no matter what, and (2) a company must always retain at least one active superuser — you can never demote, deactivate, or delete the last one.

# Why not just write this check inline inside every service that touches a superuser?
# Because this exact check needs to run before multiple different actions — deactivating a user, demoting them from superuser, deleting their account — and each of those services shouldn't have to reimplement "is this the founder, or the last owner" logic separately. Also worth noticing: this reuses count_active_superusers rather than duplicating its query — the exact reuse we predicted back when we first reviewed that function.

# When is this used?
# At the top of any service that's about to change a superuser's standing — deactivate_user, revoke_superuser_role, delete_user — called before the actual mutation happens, so the whole operation can be aborted cleanly.

# What breaks without it?
# Without the founder check: someone could accidentally (or maliciously, if a permission check elsewhere had a gap) deactivate the company founder's account. Without the last-owner check: a company could end up with zero active superusers, locking everyone out of the ability to manage roles or staff at all — the exact scenario count_active_superusers was originally built to help prevent.

# 2. Imports — explained like you've never programmed
# python
# from lrb.accounts.selectors import count_active_superusers
# from lrb.core.exceptions import ApplicationError, ErrorCode

# count_active_superusers — this is the very first function you showed me, now being imported and reused exactly as its own docstring/design implied it would be. Worth noticing where it's imported from: lrb.accounts.selectors — confirming explicitly what we inferred earlier from its behavior (a read-only query, no @transaction.atomic, no side effects) — it lives in the selectors module, the read-only counterpart to the services module (where create_user, update_user, and presumably this file live).

# ApplicationError — the same exception type update_user used for its "user not found" case. Here it's reused for a conceptually similar situation: "this action cannot proceed, full stop" — not a validation problem with malformed input, not strictly a business-rule violation in the duplicate-email sense, just a flat "no."

# ErrorCode — the same enum-like class from create_user/update_user, here providing two new members you haven't seen yet: CANNOT_MODIFY_FOUNDER and LAST_OWNER — each presumably a distinct, named constant a frontend can match on to show a specific message, rather than parsing raw error text.

# 3. Signature — every symbol explained
# python
# def assert_not_last_owner(*, user, company_id, action="modify"):

# assert_not_last_owner — the function name itself follows a naming convention worth naming explicitly: functions starting with assert_ are a common pattern for "this either passes silently, or raises" — unlike get_/count_/list_ functions, which always return something useful. An assert_ function's entire contract is: "call me, and if you get past me without an exception, you're safe to proceed." There's no meaningful return value to use.

# (*, user, company_id, action="modify") — keyword-only again, consistent with your project's convention.

# Here's the gap worth fixing: every parameter is missing a type hint.

# user — should be typed as your User model, e.g. user: User (which would require importing User from lrb.accounts.models at the top of this file).
# company_id — every other function in this project types this as str (count_active_superusers, list_users) — should read company_id: str.
# action="modify" — has a default value but no type hint; should read action: str = "modify".
# The function itself has no -> None return type hint, even though — per the assert_ naming convention — it never meaningfully returns anything on success (an implicit return with no value happens at the very first return statement, and the function simply falls off the end otherwise, which is also an implicit None).

# Corrected signature:

# python
# def assert_not_last_owner(*, user: User, company_id: str, action: str = "modify") -> None:

# Why does action have a default value while user and company_id don't?
# Because action only affects the wording of the error message ("modify," "deactivated," "removed") — it's cosmetic, not structural to the check itself. user and company_id are the actual data the function needs to do its job; there's no sensible default for "which user" or "which company," so they're mandatory.

# 4. Classes

# No class here — same reasoning as every function we've covered: this does one focused check and either raises or falls through silently, with nothing to remember between calls.

# 5. Body — line by line
# Line 1 — the early exit
# python
# if not user.is_superuser:
#     return

# Condition: not user.is_superuser — true when this user isn't a superuser at all.

# return — with nothing after it. This is a bare return, distinct from every return <value> you've seen so far. It means "stop executing this function right now," and since there's nothing after return, the function implicitly gives back None — which is exactly appropriate here, since (per the assert_ naming convention) nobody's checking this function's return value anyway; they're only checking whether it raised.

# Whole thing, plain English: "If this user isn't even a superuser, none of the rest of this function applies — stop here, nothing to protect."

# This is the most important line to understand structurally, because it means everything below only ever runs for superusers — the founder check and the last-owner check are both specifically about superuser protections, not about users in general.

# Line 2 — the founder check
# python
# if user.is_founder:
#     raise ApplicationError(
#         f"The founder's account cannot be {action}.",
#         code=ErrorCode.CANNOT_MODIFY_FOUNDER,
#     )

# Condition: user.is_founder — a flag you've seen before, in create_user's parameter list (is_founder: bool = False).

# f"The founder's account cannot be {action}." — this is an f-string — a string literal prefixed with f, which lets you embed a variable's value directly inside curly braces {...}. Python replaces {action} with whatever action actually holds at the time this runs — so if action="deactivated", the message becomes "The founder's account cannot be deactivated." This is why action exists as a parameter at all: it lets the same guard function produce a message tailored to whatever specific operation triggered it, without needing a separate error message per calling service.

# code=ErrorCode.CANNOT_MODIFY_FOUNDER — a keyword argument attaching a specific, matchable error code alongside the human-readable message.

# Whole thing, plain English: "If this superuser is specifically the founder, refuse unconditionally — no counting required, no exceptions."

# Worth noting the ordering here: the founder check happens before the last-owner count query. This is deliberate and efficient — if the user is the founder, there's no need to run a database query at all; you already know the answer is "no."

# Lines 3–5 — the last-owner check
# python
# remaining = count_active_superusers(company_id=company_id, exclude_ids=[str(user.id)])
# if remaining == 0:
#     raise ApplicationError(
#         f"Cannot {action} the last active owner of the company.",
#         code=ErrorCode.LAST_OWNER,
#     )

# Right side of the assignment: count_active_superusers(company_id=company_id, exclude_ids=[str(user.id)]) — calling the exact function from way back at the start of this whole conversation. Notice exclude_ids=[str(user.id)] — a list containing one item, this user's own ID, explicitly converted to a string with str(...). This is the precise mechanism we predicted when we first walked through count_active_superusers's "real project usage" section: "pretend this user is already gone, then count who's left."

# Why str(user.id) and not just user.id?
# count_active_superusers's exclude_ids parameter is typed as Iterable[str] — a collection of strings. If user.id is stored internally as something other than a plain string (a UUID object, for instance, which is common for primary keys), passing it directly could fail to match correctly against the string-based pk__in comparison inside count_active_superusers. Explicitly converting with str(...) guarantees the type matches what the function expects, regardless of what type the underlying id field actually is.

# Left side: remaining — storing however many active superusers would be left if this user were removed from the count.

# if remaining == 0: — the actual safety check: if excluding this user leaves zero active superusers, this action cannot proceed.

# Whole thing, plain English: "Count how many active superusers this company would have left, pretending this specific user doesn't count. If that number is zero, refuse — this user is the last line of defense."

# 6. Beginner questions, answered proactively

# Why is there no else after the founder check, connecting it to the last-owner check?
# Because raise inside the if user.is_founder: block already stops execution entirely if that branch is taken — an else would be redundant. If the founder check doesn't raise (meaning user.is_founder was False), execution simply continues to the next line naturally — no explicit else needed to express that.

# Why check is_founder separately from the superuser count at all — isn't the founder presumably also caught by "last active superuser" eventually?
# Not necessarily, and that's exactly the point of having two separate checks. A company could have five active superusers, four of them ordinary staff-granted superusers and one the founder — remaining would be 4, well above zero, and the last-owner check alone would allow modifying the founder. The founder check exists specifically to protect that one person unconditionally, regardless of how many other superusers exist.

# What does "modify" actually get used for if this function never performs any modification itself?
# It's purely cosmetic, feeding into the error message text via the f-string. The function itself never touches the database for anything except the read-only count — the word "modify" is describing whatever the caller is about to attempt, not anything this function does.

# Why does this function raise ApplicationError rather than AppValidationError or BusinessRuleViolationError?
# Worth comparing against what you've already seen: AppValidationError was used for malformed input (a weak password, an invalid field value). BusinessRuleViolationError was used specifically for the duplicate-email case. Neither really fits here — there's nothing wrong with the input to whatever calling service is running, and this isn't a data-integrity/uniqueness issue. ApplicationError — the same type update_user used for "user not found" — fits better as a general "this specific action is not permitted right now" signal, distinct from both.

# 7. Design discussion

# Why is this a small, separate, reusable guard function instead of being inlined into each service that needs it (deactivate_user, revoke_superuser_role, etc.)?
# This is the same reasoning you've now seen repeatedly, but it's worth restating here because the payoff is finally visible: this exact check needs to run identically from at least two or three different places, and if this logic were duplicated, a future change (say, adding a new protected role type) would need to be applied consistently everywhere it's copied — a classic source of drift and bugs. Centralizing it here means every caller automatically benefits from any future fix or extension to this rule.

# Trade-off worth naming: this function's early-exit design (if not user.is_superuser: return) means it's safe to call unconditionally on any user, even a non-superuser, without the caller needing to pre-check anything — which is convenient, but it also means a caller could mistakenly think calling this function is sufficient to guard any action, when it's specifically scoped to superuser-protection concerns only, not a general-purpose "can this user be modified" check.

# Why does the founder check happen before the (more expensive) database query, rather than after?
# A deliberate performance ordering — cheap, in-memory checks (user.is_founder, already loaded on the object) should run before anything that hits the database. If the founder check can already answer the question, there's no reason to spend a query finding out something you no longer need to know.

# 8. DIY Recipe — build one like this yourself

# How to build your own "assert this invariant" guard function:

# Name it assert_<the thing that must NOT be true> — the name itself should communicate "call me before doing something risky."
# Start with the cheapest possible early exit. If the check doesn't apply to this input at all, return immediately with no value, before doing any expensive work.
# Order remaining checks from cheapest to most expensive — in-memory attribute checks before database queries.
# Accept a cosmetic parameter (like action) if the same guard needs to produce contextually different messages for different callers, rather than writing separate near-identical guard functions per calling context.
# Reuse existing selectors (like count_active_superusers) rather than rewriting the underlying query — this is exactly what makes a guard function like this cheap to write once your data-access layer is already solid.
# Raise a general-purpose "not permitted" exception type, distinct from your input-validation and business-rule-violation types, for pure "this action cannot happen right now" cases.
# 9. General pattern recognition

# This is the "assert invariant" pattern — new relative to everything else you've shown me, but simple once named:

# python
# def assert_<invariant>(*, <subject>, <context>, <optional message context> = <default>) -> None:
#     if <cheap early-exit condition>:
#         return
#     if <cheap check>:
#         raise SomeError(...)
#     <expensive check, e.g. a query>
#     if <expensive check fails>:
#         raise SomeError(...)

# You'll recognize this shape anywhere a codebase needs to protect an invariant ("at least one admin must remain," "you can't delete the default payment method," "a workspace must have at least one owner") — always guard-first, raise-or-silently-pass, never a meaningful return value.

# 10. Real project usage

# This is almost certainly called at the very top of deactivate_user, right after the target user is fetched and before anything else happens:

# python
# @transaction.atomic
# def deactivate_user(*, actor, target_user_id: str) -> User:
#     require_permission(actor=actor, codename="staff.manage_users")
#     target = get_user(user_id=target_user_id)
#     if target is None:
#         raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
#     assert_not_last_owner(user=target, company_id=target.company_id, action="deactivated")
#     target.is_active = False
#     target.full_clean()
#     target.save()
#     return target

# Notice action="deactivated" here — this is exactly where the cosmetic parameter earns its purpose, producing "Cannot deactivate the last active owner of the company" specifically for this caller, while a different caller (say, revoke_superuser_role) might pass action="demoted" instead.

# 11. Common beginner mistakes

# ❌ Calling this function but ignoring its return value as if it told you something — it doesn't; the entire contract is "raises or doesn't," never a meaningful True/False or object to inspect.

# ❌ Forgetting to call this before the actual mutation, and only remembering to add it after a real incident (a company genuinely losing all its superusers) — this is exactly the kind of guard that's easy to skip when writing a new service that touches superuser status, since nothing forces you to call it.

# ❌ Passing user.id without converting to str(...) when calling count_active_superusers, risking a type mismatch against exclude_ids: Iterable[str].

# ❌ Assuming the founder check makes the last-owner check redundant, or vice versa — they protect genuinely different scenarios and both need to run.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "Before doing anything risky to a superuser, I need one shared place to check: are we about to lock this company out of its own admin capabilities, or touch the one account that should never be touched?"
# What inputs will I need? The user being acted on, which company they belong to (for the count), and a word describing the action, for a clear error message.
# What could go wrong? This function gets called for a non-superuser (should be a cheap no-op); the founder is targeted (should always be refused); the last superuser besides the founder is targeted (should be refused based on a real count).
# How should I report failure? Raise immediately, with a message and code specific to which invariant was violated — founder-protection and last-owner-protection are different problems even though they're checked in the same function.
# What should happen if everything's fine? Nothing — silently return, letting the caller proceed with whatever action prompted the check in the first place.