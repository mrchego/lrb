from __future__ import annotations
from typing import Iterable
from django.utils import timezone
from django.db import transaction
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.core.services.bulk_result import BulkActionResult
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError


def bulk_lock_users(
    *,
    user_ids: Iterable[str],
    company_id: str,
    current_user_id: str,
    duration_minutes: int = 15,
) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    current_user_id = str(current_user_id)
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}
    locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)

    for user in users:
        uid = str(user.id)

        if uid == current_user_id:
            result.add_failure(user_id=uid, reason="Cannot lock your own account")
            continue
        try:
            assert_not_last_owner(user=user, company_id=company_id, action="locked")
        except ApplicationError as e:
            result.add_failure(user_id=uid, reason=str(e.message))
            continue
        try:
            with transaction.atomic():
                user.locked_until = locked_until
                user.save(update_fields=["locked_until"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")

    return result


# 1. Purpose — Why this exists

# What problem is this solving?
# Bulk-lock a set of user accounts — say, in response to a suspected mass credential-stuffing attack — while still respecting every safety invariant your project has built: don't let staff lock themselves out by accident, don't lock the founder, don't lock the last active owner of a company. This is the most protection-heavy bulk function in the set so far, combining a self-protection check with the existing ownership guard.

# Why not just loop and call a single-user lock function?
# Same efficiency and itemized-reporting reasoning as every other bulk function — one query for the whole batch, one accumulator for the whole outcome.

# When is this used?
# A bulk "lock these accounts" admin action, where the acting staff member's own ID is known and must be excluded from the batch's effect on themselves.

# What breaks without it?
# Without the self-lock check: a staff member could accidentally lock themselves out mid-incident-response. Without the ownership guard: the same lockout risk you've now protected against in demote_owner, deactivate_user, delete_user.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.utils import timezone
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# from lrb.core.exceptions import ApplicationError

# Everything here you've built or seen before — timezone (the same tool lock_user used, for computing an expiry timestamp), assert_not_last_owner and ApplicationError newly combined into a bulk context for the first time. Nothing mechanically new.

# 3. Signature — every symbol explained
# python
# def bulk_lock_users(
#     *,
#     user_ids: Iterable[str],
#     company_id: str,
#     current_user_id: str,
#     duration_time: int = 15,
# ) -> BulkActionResult:

# Familiar shape — keyword-only, user_ids: Iterable[str] correctly typed, company_id: str mandatory. Two things worth naming:

# current_user_id: str — new relative to the sibling bulk functions. This exists specifically to support the "can't lock your own account" check — the function needs to know who's performing the action, not just who's being acted on, precisely because one of its safety checks depends on comparing the two.

# duration_time: int = 15 — matches lock_user's own duration_minutes: int = 15 in spirit, though notice the parameter name differs (duration_time here versus duration_minutes there) for what is conceptually the same value, in minutes. Worth aligning the naming across both — a reader who knows lock_user's signature would reasonably expect the same name here.

# No @transaction.atomic on the function — correctly matches the per-item atomicity pattern you established and confirmed as your project's actual intent for bulk operations.

# 4. Classes

# No class defined — same reasoning as every bulk function.

# 5. Body — line by line
# python
# result = BulkActionResult()
# normalized_ids = [str(uid) for uid in user_ids]
# current_user_id = str(current_user_id)
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))

# Familiar setup — accumulator, normalized target IDs. current_user_id = str(current_user_id) — reassigning the parameter to its own normalized form (the same naming habit we discussed and moved away from for user_ids a few turns ago — worth being consistent here too, e.g. normalized_current_user_id, though the risk is lower since this single value is only compared, never transformed further).

# The bug
# python
# found_ids = {str(u) for u in users}

# Compare this directly against every sibling bulk function you've built:

# python
# found_ids = {str(u.id) for u in users}   # bulk_unlock_users, bulk_restore_users
# found_ids = {str(u) for u in users}      # bulk_lock_users — missing .id

# This is a single missing .id — but the consequence is severe, not cosmetic. str(u) doesn't give you the user's ID at all — it calls Python's built-in string-conversion machinery on the User object itself, which invokes whatever __str__ method is defined on your User model (commonly returning something like the user's email or full name for a human-readable representation in Django's admin panel, logs, etc. — not the primary key).

# Trace the consequence all the way through, the same way we traced missing's type a few turns ago: found_ids now contains a set of emails (or whatever __str__ returns) — a completely different vocabulary of strings than normalized_ids, which contains ID strings. Later:

# python
# for missing in set(normalized_ids) - found_ids:

# Since found_ids contains emails and normalized_ids contains IDs, no element of normalized_ids will ever match anything in found_ids — set subtraction finds nothing in common, so the result is effectively set(normalized_ids) unchanged. This means: every single user you actually found and locked (or attempted to lock) in the loop above will also be reported as "User not found in this company." — even the ones that succeeded moments earlier in the exact same function call.

# Concretely: lock 10 users, all 10 succeed and get added to result.succeeded. Then this final loop runs, and because found_ids never actually matched any real ID, all 10 of those same, genuinely-found users get also appended to result.failed with a false "not found" reason. The caller gets back a BulkActionResult claiming 10 successes and 10 not-found failures for the exact same 10 people — actively misleading, not just incomplete.

# Fix:

# python
# found_ids = {str(u.id) for u in users}

# Why this specific typo is easy to make and easy to miss on a skim: str(u) is valid Python — it runs without error, produces a set, and the line itself looks structurally identical to its correct sibling at a glance. The bug only reveals itself by tracing what str(u) actually returns for a User object versus str(u.id) — exactly the "walk the chain back to its source" verification habit from a couple of turns ago, applied here in reverse (catching a place where the value doesn't match).

# python
# locked_until = timezone.now() + timezone.timedelta(minutes=duration_time)

# Computed once, outside the loop — sensible, since every user in this batch gets locked until the same moment (versus computing it fresh inside the loop, which would give each user a very slightly different expiry due to per-iteration timing — a small but real correctness detail this version gets right by hoisting it out).

# The main loop
# python
# for user in users:
#     uid = str(user.id)

#     if uid == current_user_id:
#         result.add_failure(user_id=uid, reason="Cannot lock your own account")
#         continue

# The new safety check — compare each target's ID against the acting user's own ID (both normalized to strings, so the comparison is reliable regardless of the underlying ID type). If they match, refuse and move to the next user via continue — same pattern as the "already restored" skip in bulk_restore_users.

# python
#     try:
#         assert_not_last_owner(user=user, company_id=company_id, action="locked")
#     except ApplicationError as e:
#         result.add_failure(user_id=uid, reason=str(e.message))
#         continue

# This is genuinely new — the first bulk function to call assert_not_last_owner at all, and it has to handle it differently than a single-user service does, because assert_not_last_owner raises on violation rather than returning a value — and inside a bulk loop, you don't want one user's ownership violation to crash the whole batch (matching the pattern you established for save failures). Wrapping the call in its own try/except ApplicationError converts a raised exception into a recorded failure, then continues to the next user — consistent with every other per-user failure path in this function.

# str(e.message) — accessing .message on the caught ApplicationError. Worth distinguishing this from the .message trap you hit with Django's ValidationError several files back: that trap was specifically about ValidationError's dict-based construction only sometimes populating .message. ApplicationError is your own custom exception class, and based on every place you've constructed one (ApplicationError("User Not Found", code=ErrorCode.USER_NOT_FOUND)), it's always built from a single message string — so .message reliably existing here is a reasonable assumption, genuinely different from the Django case, provided ApplicationError.__init__ actually stores its first argument as self.message (worth a quick confirmation against that class's own definition if you haven't already, but not the same fragile pattern as before).

# python
#     try:
#         with transaction.atomic():
#             user.locked_until = locked_until
#             user.save(update_fields=["locked_until"])
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e))

# Exactly the per-item atomicity pattern from bulk_unlock_users/bulk_restore_users, correctly applied here too — narrow transaction scope, catch-and-report on failure, add_success correctly called with the keyword.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# return result

# Structurally identical to the sibling functions — correct in shape, but poisoned by the found_ids bug above, so it will currently misreport for every genuinely-found user.

# 6. Beginner questions, answered proactively

# Why does the self-lock check come before the ownership guard, rather than after?
# Ordering by cheapest-check-first, same principle as assert_not_last_owner's own internal ordering (founder check before the database query) — comparing two already-in-memory strings is essentially free, while assert_not_last_owner potentially runs a database query (count_active_superusers). Checking the cheap thing first means you never pay for the expensive check on a user you were going to reject anyway.

# Why continue after the ownership-guard failure but not restructure it as an if/else?
# Same reasoning as bulk_restore_users's "already active" branch — continue cleanly expresses "nothing more to do for this one, move on," without needing to indent the entire rest of the loop body inside an else block.

# 7. Design discussion

# Why does this function need current_user_id passed in explicitly, rather than looking it up some other way?
# Because a service function like this shouldn't know anything about how the caller determined who's authenticated — that's a resolver/GraphQL concern (recall get_current_user(info) from several turns ago). Keeping this function's inputs limited to plain data (IDs, a company, a duration) rather than a GraphQL info object keeps it testable and reusable independent of the web layer — exactly the separation-of-concerns principle behind your whole selector/service architecture.

# Trade-off worth naming for the found_ids bug specifically: this is a strong argument for automated tests over manual code review alone. A test asserting "locking 3 valid users should produce exactly 3 successes and 0 failures" would have caught this immediately — the bug only shows up when you actually run the function against real found users, not from reading the code casually, since str(u) "looks" plausible next to str(u.id) unless you specifically know what a bare str() on a model instance returns.

# 8. DIY Recipe — build one like this yourself
# When building found_ids for a missing-ID comparison, always extract the specific identifying field explicitly (u.id), never rely on the object's default string conversion — str(some_object) almost never means what you want unless you've specifically confirmed what __str__ returns for that model.
# When a bulk operation needs to protect against "acting on yourself," accept the actor's ID as an explicit parameter, and check it early, before any expensive per-item work.
# When composing an existing raise-based guard function (assert_not_last_owner) into a bulk loop, wrap the call in its own try/except, converting the raise into a recorded failure and continue-ing, exactly matching how you already handle save failures.
# After writing a missing-ID comparison, sanity-check it by hand once: pick one user you know will be found, and verify their ID would actually appear in both sets being compared — this is exactly the trace that reveals the str(u) bug.
# 9. General pattern recognition

# Same "batch fetch, per-item action, itemized report" pattern as its siblings, now combined with two independent per-item guard checks stacked in sequence (self-lock check, then ownership guard) before the actual write — each with its own continue on rejection. This is a reusable shape worth naming: "guard chain" — run each precondition in cheapest-first order, bail out of just this iteration the moment one fails, only reach the actual mutation if every guard passed.

# 10. Real project usage
# python
# def resolve_bulk_lock_users(self, info, user_ids: list[str], duration_time: int = 15) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     result = bulk_lock_users(
#         user_ids=user_ids,
#         company_id=actor.company_id,
#         current_user_id=str(actor.id),
#         duration_time=duration_time,
#     )
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)
# 11. Common beginner mistakes

# ❌ The exact bug here — str(u) instead of str(u.id) when building a set meant for ID comparison. Passes no error, produces a set, looks correct at a glance — and silently corrupts every downstream comparison against it.

# ❌ Forgetting to wrap a raise-based guard function in try/except inside a bulk loop, letting one user's ownership violation crash the entire batch instead of being recorded as that one user's failure.

# ❌ Inconsistent parameter naming for the same concept across sibling functions (duration_time here vs. duration_minutes in lock_user) — small, but adds friction when reading two related functions side by side.

# 12. Think like the original developer
# What problem am I solving? "Lock a batch of accounts at once, while never letting the acting staff member lock themselves out, and never violating the ownership invariants already protected elsewhere."
# What inputs will I need? The target IDs, the company scope, the acting user's own ID (for self-protection), and how long to lock for.
# What could go wrong? A staff member accidentally includes their own ID in the batch; locking someone would violate the last-owner/founder invariant; a save fails for an unrelated reason; and — the actual bug here — building the "found" comparison set from the wrong attribute entirely, silently poisoning the missing-ID report for the whole batch.
# How should I report results? Itemized, same as every bulk function — but this one needs the comparison set to be built correctly for that reporting to mean anything at all.
# What should happen if everything works? Every valid, permitted target gets locked until the same computed timestamp, self-locks and ownership violations are cleanly rejected per-item, and only genuinely absent IDs — correctly detected — land in the final missing-report loop.
