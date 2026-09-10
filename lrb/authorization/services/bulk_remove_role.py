from typing import Iterable

from django.db import transaction

from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_role import get_role
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.services.bulk_result import BulkActionResult


def bulk_remove_role(*, user_ids: Iterable[str], role_id: str, company_id:str) -> BulkActionResult:
    result = BulkActionResult()
    role = get_role(role_id=role_id, company_id=company_id)
    if not role:
        result.add_failure(user_id="*", reason="Role not found")
        return result
    normalized_ids = [str(uid) for uid in user_ids]
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        try:
            with transaction.atomic():
                deleted, _ = UserRole.objects.filter(user=user, role=role).delete()
                if deleted:
                    invalidate_user_permissions_cache(user_id=user.id)
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")

    return result

# Teaching: bulk_remove_role

# This is the direct mirror of bulk_assign_role — same skeleton, same imports, same overall shape. Which makes it the perfect place to practice something you've now done many times in this conversation: read a new file by diffing it against its sibling, rather than starting from scratch. And this time, that comparison actually surfaces a real, meaningful bug — a good one to catch yourself before I point it out.

# 1. What is it?

# A bulk operation that removes a role assignment from many users at once, isolating failures per-user, just like bulk_assign_role. Structurally identical setup: validate the role exists, fetch and normalize the target users, loop with per-item transactions, report missing users separately.

# No new syntax at all in this file — everything (Iterable[str], BulkActionResult, with transaction.atomic():, .filter().delete() returning a tuple, set difference for missing users) is something you've already learned. So instead of re-teaching syntax, let's go straight to comparing this function against bulk_assign_role, line by line, since that's where the real content is.

# 2 & 3. Signature — quick pass
# python
# def bulk_remove_role(*, user_ids: Iterable[str], role_id: str, company_id: str) -> BulkActionResult:

# Identical shape to bulk_assign_role's signature — same three inputs, same return type. Nothing to add here.

# 4. Body — line by line, with direct comparison
# python
# result = BulkActionResult()
# role = get_role(role_id=role_id, company_id=company_id)
# if not role:
#     result.add_failure(user_id="*", reason="Role not found")
#     return result

# Identical to bulk_assign_role (tiny style difference: add_failure(user_id="*", reason=...) here uses keyword arguments explicitly, while bulk_assign_role passed them positionally, add_failure("*", "Role not found.") — functionally the same, just a minor style inconsistency, not a bug).

# python
# normalized_ids = [str(uid) for uid in user_ids]
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# Byte-for-byte identical logic to bulk_assign_role. You should recognize this instantly now.

# python
# for user in users:
#     uid = str(user.id)
#     try:
#         with transaction.atomic():
#             deleted, _ = UserRole.objects.filter(user=user, role=role).delete()
#             if deleted:
#                 invalidate_user_permissions_cache(user_id=user.id)
#                 result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason="Role was not assigned.")

# This is where the real difference is — and it's where the bug lives. Compare the shape against bulk_assign_role's loop body:

# bulk_assign_role:

# python
# with transaction.atomic():
#     _, created = UserRole.objects.get_or_create(user=user, role=role)
#     if created:
#         invalidate_user_permissions_cache(user_id=user.id)
# result.add_success(user_id=uid)          # <- OUTSIDE the with block, ALWAYS runs if no exception

# bulk_remove_role:

# python
# with transaction.atomic():
#     deleted, _ = UserRole.objects.filter(user=user, role=role).delete()
#     if deleted:
#         invalidate_user_permissions_cache(user_id=user.id)
#         result.add_success(user_id=uid)  # <- INSIDE the if, only runs when deleted > 0

# Notice exactly where result.add_success(...) sits. In bulk_assign_role, it's positioned after the with block, at the same indentation as with itself — meaning it runs unconditionally, every time no exception was thrown (whether the assignment was newly created or already existed). In bulk_remove_role, result.add_success(...) is nested one level deeper, inside the if deleted: block — meaning it only runs when a row was actually deleted.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# return result

# Identical closing logic to bulk_assign_role.

# 5. Why? — and the real bug this comparison reveals

# Trace through what happens when a user in the batch simply didn't have this role assigned to begin with (a completely normal, expected case — not every user in a bulk-remove request necessarily has the role):

# UserRole.objects.filter(user=user, role=role).delete() runs. No matching row exists, so deleted = 0. No exception is raised — a bulk .delete() matching zero rows is not an error condition in Django; it's a perfectly normal, successful "deleted nothing" outcome (same as you learned back in remove_role, where deleted=0 was handled with an explicit, deliberate check — but there, that was the single-item version, which raised on this case on purpose).
# Back in this loop: if deleted: — 0 is falsy, so this whole block is skipped.
# Because result.add_success(...) is nested inside that if deleted: block, it never runs either.
# No exception occurred, so the except Exception as e: clause never runs.
# The loop silently moves to the next user — this user's outcome is never recorded in result at all. Not a success, not a failure. That user simply vanishes from the report.

# This is a genuinely serious bug: the caller (an admin doing a bulk role removal across, say, 50 users) would get back a BulkActionResult where some users are just... missing, with no explanation and no visible signal that anything happened to them differently. Compare this against bulk_assign_role, where "already had the role" is correctly treated as a success (nothing needed to change, but the end state — "user does not have extra unwanted role attached — wait, actually it's the reverse for assign; "user has the role" was already achieved) — and every user ends up in exactly one of: success, failure (real error), or not-found. bulk_remove_role breaks that guarantee.

# What was probably intended here, and this connects directly to the idempotency lesson from clear_permission_override: "the user doesn't have this role" should almost certainly be treated as a success for a remove operation (the end goal — "this user does not have this role" — is already true), matching the same idempotent philosophy you learned there. The fix is likely as simple as moving add_success back outside the if:

# python
# with transaction.atomic():
#     deleted, _ = UserRole.objects.filter(user=user, role=role).delete()
#     if deleted:
#         invalidate_user_permissions_cache(user_id=user.id)
# result.add_success(user_id=uid)   # unconditional, matching bulk_assign_role's shape

# This would also match bulk_assign_role's structure exactly — cache invalidation stays conditional (only when something actually changed), but recording the outcome as a success does not depend on whether a change occurred.

# A second, smaller issue in the same loop: the except Exception as e: result.add_failure(user_id=uid, reason="Role was not assigned.") line has a misleading error message, similar in spirit to the assign_role bug you caught earlier (message=IntegrityError). This except block catches any unexpected exception — a database error, a signal failure, anything — but hardcodes the reason as "Role was not assigned.", which is factually about something completely different (it describes the no-op case, not a real failure!). If a genuine database error occurred here, the caller would be told "Role was not assigned" — actively misleading, since the role removal may have partially run into a real problem, not simply "there was nothing to remove." A more honest version would use the actual exception, the same way remove_role's (correctly written) sibling functions do: reason=str(e)).

# So, put together: this loop currently has no way to correctly report the very common, totally normal case of "this user didn't have the role" as a success — that case either gets silently dropped (if no exception occurs, which is the actual real-world behavior) or, if it were to somehow trigger the except block, would get mislabeled with a hardcoded, inaccurate reason.

# 6. Connections

# What comes in / goes out: identical to bulk_assign_role — same inputs, same BulkActionResult shape, feeding the same to_bulk_payload conversion in the resolver layer.
# Where this fits: the batch-removal counterpart to bulk_assign_role, and the batch counterpart to remove_role — but notice it does not replicate remove_role's "raise if not assigned" behavior at all; instead it silently drops the item, which is neither remove_role's explicit-error behavior nor clear_permission_override's explicit-success behavior. It falls into a third, unintended category: no behavior at all.

# 7. Advanced concepts

# A) "No exception, no explicit success call" is a genuine, sneaky control-flow gap
# This bug is a great example of a broader lesson: when you write conditional logic inside a try block where the except only fires on real exceptions, it's easy to accidentally create a third silent path — neither the success branch nor the exception branch — where a completely valid, exception-free execution just falls through, doing nothing that the caller can observe. Whenever you write a try/except around a loop body, ask explicitly: "for every possible outcome of this block — success, deliberate no-op, and real exception — is each one being recorded somewhere?" This file shows what happens when one of those three paths is forgotten.

# B) Consistency-by-copy-paste is a double-edged sword
# This file was clearly written by copying bulk_assign_role's structure (same imports, same variable names, same overall shape) and adapting it for removal. That's a completely reasonable way to write similar code — but it also means a small, easy-to-miss placement error (indenting add_success one level too deep) slipped through, because the copy looked structurally right at a glance. This is exactly why comparing two similar functions line by line, as we just did, is such a powerful bug-finding technique — the bug is nearly invisible reading this file alone, but glaring once placed side-by-side with its sibling.

# 8. Small example (demonstrating the actual bug)
# python
# results = {"success": [], "failure": []}
# assignments = {"u1"}   # only u1 currently has the role

# def bulk_remove_role(user_ids):
#     for uid in user_ids:
#         try:
#             deleted = uid in assignments
#             if deleted:
#                 assignments.discard(uid)
#                 results["success"].append(uid)   # BUG: nested under `if`
#         except Exception as e:
#             results["failure"].append((uid, str(e)))
#     return results

# bulk_remove_role(["u1", "u2"])
# print(results)
# # {'success': ['u1'], 'failure': []}
# # u2 never had the role — but it's completely absent from BOTH lists!
# 9. What you should remember
# When adapting one function into a near-identical sibling, diff them line by line before trusting the copy — a single misplaced indentation level (add_success nested inside if deleted: instead of after the with block) can silently break a whole category of expected outcomes.
# Every possible outcome inside a loop's try block needs an explicit destination — success, deliberate no-op-but-still-success, and real failure should each be accounted for; a silent fourth "nothing recorded" path is a real bug, not a harmless gap.
# Idempotent-style operations ("ensure this role is removed") should treat "already in the desired state" as a success, not a non-event — this file gets that principle right in intent (mirroring clear_permission_override's philosophy) but wrong in implementation (the success call never actually fires for that case).
# A hardcoded error message inside a broad except Exception block is dangerous — it can misreport what actually went wrong; prefer reason=str(e) (as correctly modeled in earlier files) so the real cause is preserved and reported honestly.
# This is exactly the kind of subtle, real-world bug that only becomes visible through comparison — you've now built the instinct, across this whole conversation, to read a new function not just for what it says, but for how it diverges from the patterns its siblings already established. That instinct just caught a genuine bug a surface-level read would miss entirely.
