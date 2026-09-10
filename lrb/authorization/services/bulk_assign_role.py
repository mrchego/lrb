from typing import Iterable

from django.db import transaction

from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_role import get_role
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.services.bulk_result import BulkActionResult


def bulk_assign_role(
    *, user_ids: Iterable[str], role_id: str, company_id: str
) -> BulkActionResult:
    result = BulkActionResult()
    role = get_role(role_id=role_id, company_id=company_id)
    if not role:
        result.add_failure(user_id="*",reason= "Role not found.")
        return result
    normalized_ids = [str(uid) for uid in user_ids]
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        try:
            with transaction.atomic():
                _, created = UserRole.objects.get_or_create(user=user, role=role)
                if created:
                    invalidate_user_permissions_cache(user_id=user.id)
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")

    return result


# Teaching: bulk_assign_role

# This is the most structurally complex file you've been given so far — it combines almost every pattern from the whole conversation (selectors, get_or_create, transactions, set operations, cache invalidation) into one bulk operation, plus introduces a few genuinely new ideas: per-item error isolation using a nested with transaction.atomic(): block, and a result-collector object pattern (BulkActionResult). Let's go through it carefully — there's a lot of design reasoning packed into this one.

# 1. What is it?

# A service that assigns the same role to many users at once, but does so in a way where one user's failure doesn't stop the others — collecting a full report of which assignments succeeded and which failed, and why.

# New pieces:

# from typing import Iterable
# BulkActionResult() and .add_failure(...)/.add_success(...)
# for user in users: try: with transaction.atomic(): ... except Exception as e:
# UserRole.objects.get_or_create(user=user, role=role)
# No @transaction.atomic decorator on the whole function — a deliberate absence
# 2. How is it written?

# from typing import Iterable
# A typing tool that means "anything you can loop over with for x in this" — lists, tuples, sets, generators, querysets, all qualify. It's a broader, more permissive hint than list[str] would be: Iterable[str] tells the caller "give me anything loopable containing strings," without requiring them to specifically hand over a list. This is good practice when a function only ever loops through its input once and doesn't need list-specific behavior (like indexing).

# result = BulkActionResult()
# Calling a class with () and no arguments — creates a new, presumably empty, instance of this custom result-tracking object (imported from lrb.core.services.bulk_result, so it's a shared utility, not something local to this file — used earlier too, indirectly, since to_bulk_payload in your mutations file likely converts one of these into GraphQL form). This is the collector pattern: instead of returning a single success/failure, build up a running report object across many small operations, then return the whole report at the end.

# role = get_role(role_id=role_id, company_id=company_id)
# Reuses your very own get_role selector directly (not inlined this time!) — a nice example of a service actually composing an existing selector, unlike some earlier files that inlined their own .filter() calls instead.

# result.add_failure("*", "Role not found.")
# The "*" here is a convention, not special syntax — a stand-in "user ID" meaning "this failure isn't about any specific user, it's about the whole batch" (the role itself doesn't exist, so nothing about which user is relevant). Worth recognizing: this is a design choice by whoever wrote BulkActionResult, using a wildcard-like string as a sentinel value for "not applicable to one specific item," similar in spirit to how None is used as a sentinel elsewhere.

# normalized_ids = [str(uid) for uid in user_ids]
# A list comprehension (you've seen the dict/set versions — this is the simplest form, just [expr for item in iterable], no filtering). Converts every ID in the input to a plain string. Same defensive reasoning as str(user.company_id) from earlier files: IDs might arrive as UUID objects or strings depending on where they came from, and normalizing everything to str up front means every later comparison (found_ids, set differences) compares on equal footing.

# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# One query, fetching every valid user at once — wrapped in list(...) because (same reasoning as create_role) this result gets used more than once below (once to loop through, once to build found_ids).

# found_ids = {str(u.id) for u in users}
# A set comprehension — "the IDs of every user that was actually found," as a set for fast membership checking and clean set-difference math later.

# for user in users: try: with transaction.atomic(): ...
# This is the structurally new part — a with block nested inside a try, itself inside a for loop. Read it layer by layer:

# The for loop processes one user at a time.
# try: wraps each iteration, so if this one user's assignment fails for any reason, the loop can catch it and move on to the next user, instead of crashing the entire function.
# with transaction.atomic(): — you've only seen @transaction.atomic as a decorator on a whole function before. Here it's used as a context manager instead (the with keyword) — same underlying tool, different syntax, used to wrap just this one small block of code (one user's assignment) in its own mini-transaction, rather than the entire function.

# _, created = UserRole.objects.get_or_create(user=user, role=role)
# A new manager method: get_or_create(...) returns a tuple (object, created_boolean) — object is the matching row (whether it already existed or was just made), and created is True if a new row was made, False if one already existed and was simply fetched. This is a simpler cousin of update_or_create — it doesn't update anything on an existing match, it only creates-if-missing and always returns whatever exists. _ throws away the actual UserRole object (not needed here), keeping only created.

# if created: invalidate_user_permissions_cache(user_id=user.id)
# Only bother invalidating the cache if a new assignment was actually made — if the user already had this role (created=False), nothing about their effective permissions changed, so there's no reason to invalidate anything. A nice, precise efficiency detail.

# except Exception as e: result.add_failure(user_id=uid, reason=str(e))
# Catches any exception (Exception is a very broad base class — almost everything inherits from it), not a specific type like IntegrityError or ApplicationError. str(e) converts whatever exception occurred into its string message, to store as the failure reason.

# for missing in set(normalized_ids) - found_ids:
# Same set-difference pattern you learned in create_role — "which requested IDs were never found at all" (as opposed to found-but-failed-to-assign, handled separately above).

# 3. Signature — broken into pieces
# python
# def bulk_assign_role(
#     *, user_ids: Iterable[str], role_id: str, company_id: str
# ) -> BulkActionResult:
# Piece	Meaning
# *,	keyword-only
# user_ids: Iterable[str]	any loopable collection of user ID strings
# role_id: str	which role to assign to all of them
# company_id: str	security scope
# -> BulkActionResult	returns a structured report object, not a plain bool or list

# Fully typed — matches set_permission_override's good example. No @transaction.atomic decorator on the function itself — this is deliberate, and it's the single most important design decision in this whole file (explained fully in section 5).

# 4. Body — line by line
# python
# result = BulkActionResult()
# role = get_role(role_id=role_id, company_id=company_id)
# if not role:
#     result.add_failure("*", "Role not found.")
#     return result

# Start the report. If the role itself doesn't exist (or belongs to another company), there's nothing meaningful to attempt for anyone — record one whole-batch failure and return immediately, without touching any users.

# python
# normalized_ids = [str(uid) for uid in user_ids]
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# Normalize input IDs, fetch every valid, company-scoped user in one query, and record which IDs were actually found.

# python
# for user in users:
#     uid = str(user.id)
#     try:
#         with transaction.atomic():
#             _, created = UserRole.objects.get_or_create(user=user, role=role)
#             if created:
#                 invalidate_user_permissions_cache(user_id=user.id)
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e))

# For each found user: attempt the assignment inside its own small transaction. If it works, record a success. If anything goes wrong for this one user, catch it, record the failure with a reason, and — critically — move on to the next user in the loop, since the exception was caught, not re-raised.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# For any requested ID that didn't correspond to a real, company-scoped user at all, record that as its own distinct failure reason.

# python
# return result

# Hand back the complete report: some successes, some per-user failures, some "not found" failures.

# 5. Why? — the core design decision in this file

# Why is there no @transaction.atomic wrapping the whole function, when your project convention says "atomic on all write services"?

# This is the most important thing to understand here, and it's a deliberate, correct exception to the general rule — not an oversight. Think about what a single, outer @transaction.atomic would mean: if any single user's assignment failed partway through the loop and raised an exception that escaped the function, Django would roll back the entire transaction — undoing every successful assignment made to every other user in the same batch, just because one user (maybe one with bad data, or a rare conflict) failed. That would completely defeat the purpose of a "bulk" operation that's supposed to report partial success.

# Instead, this function does the opposite: it wraps each individual user's assignment in its own small with transaction.atomic(): block. This means each user's assignment is atomic by itself (can't half-complete for that one user), but a failure for user #7 has zero effect on whether user #6 or user #8's assignment succeeds and stays committed. This is a genuinely important, reusable pattern: atomicity should be scoped to the unit of work that needs to succeed or fail together — not automatically applied to the largest possible unit just because a decorator makes it easy.

# Why catch a broad except Exception instead of something more specific like IntegrityError?
# Because this loop needs to survive any possible failure for one user — not just a duplicate-assignment conflict, but potentially anything unexpected (a database connectivity blip, a signal handler raising something, etc.) — without that one failure taking down the whole batch or the whole function. This is one of the rare, legitimate uses of a broad except Exception: at the boundary of a per-item loop in a bulk operation, where the explicit design goal is "isolate failures, keep going." (Contrast this with catching broad exceptions carelessly elsewhere in a codebase, which is usually considered bad practice because it can hide real bugs — here, it's justified by the specific bulk-isolation goal, and every failure is still captured and reported, not silently swallowed.)

# Why get_or_create instead of .create() + catching IntegrityError (like assign_role did)?
# Because in a bulk context, "this user already has this role" isn't really a failure worth reporting the same way assign_role's single-item ALREADY_ASSIGNED error was — it's a perfectly fine, quiet outcome for one user among many (maybe some users in the batch already had the role, some didn't). get_or_create treats "already exists" as a normal, successful outcome (created=False), letting the loop record it as a success without needing special-case error handling for that one situation.

# Why check found_ids separately, in a second loop, instead of handling "not found" inside the main loop?
# Because users (from get_users_by_ids) only ever contains users that were found — there's no way to loop through a "missing" user inside the first loop, since they were never fetched at all. The second loop, using set difference, is the only way to identify which requested IDs never showed up in the results at all — a structurally different kind of "failure" from "found the user, but the assignment itself failed."

# 6. Connections

# What comes in: a batch of user IDs, one role ID, and the company scope.
# What goes out: a BulkActionResult — recall from your very first UserMutation file, to_bulk_payload(result) is exactly what converts this kind of object into a GraphQL-friendly BulkActionPayload. This confirms the full round trip: bulk_assign_role builds the report here; the resolver you read weeks ago just passes it straight through to_bulk_payload.
# Reuses: get_role (selector), get_users_by_ids (a new selector, following the exact same shape you'd now recognize instantly even without seeing its code), and invalidate_user_permissions_cache (the same per-user cache you've now seen cleared by assign_role, remove_role, set_permission_override, and clear_permission_override).

# 7. Advanced concepts

# A) Nested/scoped transactions — matching atomicity boundaries to the real unit of work
# This is the single biggest lesson in this file, worth restating clearly: don't reach for @transaction.atomic on an entire function by default just because your project convention says "use it on writes." Ask: what is the smallest set of operations that must succeed or fail together, as one unit? Here, that unit is "one user's role assignment" — not "the entire batch." Wrapping too large a scope in one transaction can turn "99 successes and 1 failure" into "0 successes," which is often the opposite of what a bulk operation should do.

# B) get_or_create vs create()+IntegrityError vs update_or_create — three tools, three intents
# You've now learned all three siblings:

# .create() + catch IntegrityError (from create_role, assign_role) — "this must be new; treat a duplicate as an error."
# .get_or_create(...) (this file) — "give me this row, making it if needed; existing-and-new are both fine, just tell me which happened."
# .update_or_create(..., defaults={...}) (from set_permission_override) — "give me this row, making it if needed, and force these specific fields to these values either way."
# Recognizing which of these three matches your actual intent is a real, recurring Django design decision.

# C) Broad except Exception as a deliberate boundary, not a shortcut
# General programming wisdom says "catch specific exceptions, not broad ones" — and that's still usually right. This file is one of the legitimate exceptions to that rule: at a per-item boundary inside a loop whose entire purpose is fault isolation, catching broadly and recording the failure (rather than silently ignoring it) is the correct, intentional choice — the failure is never lost, just contained and reported per-item instead of allowed to propagate and cancel everything else.

# 8. Small example
# python
# class BulkResult:
#     def __init__(self):
#         self.successes = []
#         self.failures = []
#     def add_success(self, user_id):
#         self.successes.append(user_id)
#     def add_failure(self, user_id, reason):
#         self.failures.append((user_id, reason))

# assignments = set()  # (user_id, role_id) pairs already assigned

# def bulk_assign(*, user_ids, role_id):
#     result = BulkResult()
#     for uid in user_ids:
#         try:
#             if uid == "bad":
#                 raise ValueError("simulated failure")
#             assignments.add((uid, role_id))
#             result.add_success(uid)
#         except Exception as e:
#             result.add_failure(uid, str(e))
#     return result

# r = bulk_assign(user_ids=["u1", "bad", "u3"], role_id="r1")
# print(r.successes)  # ['u1', 'u3']
# print(r.failures)   # [('bad', 'simulated failure')]

# Notice: "bad" failing doesn't stop "u3" from succeeding right after it — exactly the isolation this file's try/except inside the loop achieves.

# 9. What you should remember
# Match the scope of a transaction to the actual unit of work that must succeed or fail together — not automatically to "the whole function." A bulk operation processing independent items almost always wants per-item transactions, not one giant one.
# with transaction.atomic(): (context manager) and @transaction.atomic (decorator) are the same underlying tool, chosen based on whether you need to wrap an entire function or just a smaller block inside it.
# A broad except Exception is acceptable, even good practice, specifically at a per-item isolation boundary in a loop — as long as every failure is still captured and reported, never silently discarded.
# get_or_create, update_or_create, and create()+catch each express a different intent about what "already exists" should mean — pick based on whether an existing match should be treated as success, updated, or an error.
# A "collector" result object (BulkActionResult), built up across a loop and returned once at the end, is the standard shape for any bulk operation that needs to report partial success/failure per item — recognize this pattern whenever a function processes many independent items and can't just succeed-or-raise as a whole.