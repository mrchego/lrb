from __future__ import annotations
from typing import Iterable
from django.db import transaction
from lrb.core.exceptions import ApplicationError
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.core.services.bulk_result import BulkActionResult
from lrb.accounts.services.ownership_guard import assert_not_last_owner

def bulk_delete_users(*, user_ids:Iterable[str], company_id:str, current_user_id:str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids =  [str(uid) for uid in user_ids]
    current_user_id=str(current_user_id)
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        if uid == current_user_id:
            result.add_failure(user_id=uid, reason="You cannot delete your own account")
            continue
        if not user.is_active and not user.can_login:
            result.add_failure(user_id=uid, reason="Already deleted")
            continue
        try:
            assert_not_last_owner(user=user, company_id=company_id, action="deleted")
        except ApplicationError as e:
            result.add_failure(user_id=uid, reason=str(e))
            continue

        try:
            with transaction.atomic():
                user.is_active = False
                user.can_login = False
                user.save(update_fields=["can_login", "is_active"])
            result.add_success(user_id=uid)
        except Exception as e :
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in the company")

    return result

# 1. Purpose — Why this exists

# What problem is this solving?
# The bulk sibling of delete_user — soft-delete a batch of accounts at once (recall: "delete" here means is_active=False and can_login=False, never actually removing the row), while protecting against the same risks bulk_lock_users protects against: don't let staff delete their own account, don't touch someone already deleted, don't violate the ownership invariant.

# Why not just loop and call the single-user delete_user?
# Same efficiency and itemized-reporting reasoning as every bulk function so far.

# When is this used?
# A bulk "delete selected accounts" admin action — offboarding several staff at once, for instance.

# What breaks without it?
# Without the self-delete check: an admin could accidentally deactivate their own account mid-batch. Without the ownership guard actually working correctly (which, as we'll see, it currently doesn't): a company could lose its last owner through a bulk action that was supposed to prevent exactly that.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.core.exceptions import ApplicationError
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult
# from lrb.accounts.services.ownership_guard import assert_not_last_owner

# Same import set as bulk_lock_users, minus the missing-user ApplicationError distinction we'll get to — nothing new mechanically.

# 3. Signature — every symbol explained
# python
# def bulk_delete_users(*, user_ids: Iterable[str], company_id: str, current_user_id: str) -> BulkActionResult:

# Matches the established template exactly — no @transaction.atomic on the function (correct, per-item atomicity), keyword-only, correctly typed collection parameter, current_user_id: str for the self-action check you just traced the origin of, correct return hint.

# 4. Classes

# No class defined — same as every sibling.

# 5. Body — line by line
# python
# result = BulkActionResult()
# normalized_ids = [str(uid) for uid in user_ids]
# current_user_id = str(current_user_id)
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# All correct — found_ids built from .id (the bulk_lock_users bug is not repeated here), transformed collection given its own name.

# The guard chain
# python
# for user in users:
#     uid = str(user.id)
#     if uid == current_user_id:
#         result.add_failure(user_id=uid, reason="You cannot delete your own account")
#         continue
#     if not user.is_active and not user.can_login:
#         result.add_failure(user_id=uid, reason="Already deleted")
#         continue

# Two cheap, in-memory guard checks, each correctly followed by continue — self-delete protection, then an "already in target state" check mirroring bulk_restore_users's "already active" branch, but for the opposite direction: if both flags are already False, there's nothing left to delete.

# Bug 1 — the missing continue
# python
#     try:
#         assert_not_last_owner(user=user, company_id=company_id, action="deleted")
#     except ApplicationError as e:
#         result.add_failure(user_id=uid, reason=str(e))

#     try:
#         with transaction.atomic():
#             user.is_active = False
#             user.can_login = False
#             user.save(update_fields=["can_login", "is_active"])
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e.message))

# Compare this directly against bulk_lock_users's equivalent block:

# python
# try:
#     assert_not_last_owner(user=user, company_id=company_id, action="locked")
# except ApplicationError as e:
#     result.add_failure(user_id=uid, reason=str(e.message))
#     continue          # ← present in bulk_lock_users

# This file's except ApplicationError block has no continue. Trace what actually happens when assert_not_last_owner raises — say, this user is the last active owner of their company: the exception is caught, add_failure correctly records the rejection... and then, because there's no continue, execution falls straight through to the very next line and enters the second try block anyway — the one that actually performs the delete. The guard's rejection gets recorded, but the action it was supposed to block happens regardless. This user gets both a failure entry ("last owner, can't delete") and actually deleted, and — since the delete itself succeeds — also a success entry. The exact lockout scenario the entire guard chain exists to prevent happens anyway, just with a confusing paper trail claiming it was blocked.

# Fix:

# python
# try:
#     assert_not_last_owner(user=user, company_id=company_id, action="deleted")
# except ApplicationError as e:
#     result.add_failure(user_id=uid, reason=str(e))
#     continue
# Bug 2 — str(e.message) on a generically-caught exception
# python
# try:
#     with transaction.atomic():
#         ...
#     result.add_success(user_id=uid)
# except Exception as e:
#     result.add_failure(user_id=uid, reason=str(e.message))

# Look carefully at what's being caught here: except Exception as e — this is the wide, generic net, deliberately chosen (as you established with me two turns ago) precisely because you don't know in advance what might go wrong during a save — it could be IntegrityError, or anything else.

# The problem: .message is not a general attribute that all Python exceptions have. It's specific to certain exception types (like Django's ValidationError, in the very particular single-string-construction case you spent real time on many turns ago). A plain IntegrityError, or most other built-in Python exceptions, has no .message attribute at all. Accessing e.message here raises:

# AttributeError: 'IntegrityError' object has no attribute 'message'

# This means the exact scenario this except block exists to handle — a real save failure — currently crashes with a different, more confusing error than the one it was trying to report. Instead of a clean "this user couldn't be saved because X," the caller (and your logs) get an unrelated AttributeError about a missing .message attribute, obscuring what actually went wrong during the save. Compare this directly against every sibling bulk function you've built correctly:

# python
# except Exception as e:
#     result.add_failure(user_id=uid, reason=str(e))   # bulk_unlock_users, bulk_restore_users, bulk_lock_users, bulk_force_password_reset

# Every one of them correctly uses str(e) — converting the whole exception to its string representation, which works for any exception type, not just ones that happen to define .message. str(e) is the general, always-safe tool; .message is a fragile assumption about a specific exception's internal structure — precisely the same category of mistake as the ValidationError.message bugs from create_user, just reappearing in a new spot.

# Fix:

# python
# except Exception as e:
#     result.add_failure(user_id=uid, reason=str(e))

# Worth noting the irony directly: the correct use of str(e.message) earlier in this same series was specifically for ApplicationError — a class you've confirmed always stores a single string message, making .message safe there. But that safety doesn't transfer to a generic except Exception block, which could catch any exception type in the entire language, most of which were never designed with a .message attribute at all. The same code shape (str(e.message)) is correct in one context and a guaranteed crash risk in another, depending entirely on what's actually being caught.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in the company")

# return result

# Correct — consistent with every sibling.

# 6. Beginner questions, answered proactively

# Why does the missing continue matter more here than it might seem?
# Because this isn't just "a failure gets recorded twice" — it's the actual protected write happening despite being rejected. The try/except around assert_not_last_owner was never just about reporting; its entire purpose is to stop execution before reaching the delete. Recording the rejection without also stopping defeats the guard completely — the reporting and the protection are two separate jobs, and this bug keeps one while silently dropping the other.

# Why does str(e) work for any exception, when .message doesn't?
# str(e) calls Python's universal string-conversion machinery, which every exception (indeed, every object in Python) supports by default, returning something reasonable — typically whatever message the exception was constructed with, however it stores that internally. .message is a specific attribute name that only exists on classes that explicitly define it. str(e) works no matter how the exception stores its message internally; .message only works if you already know, in advance, that this exact exception class happens to expose it that way.

# 7. Design discussion

# Why is it easy to introduce the missing-continue bug specifically here, when bulk_lock_users got it right?
# Likely because this file's guard-chain block was written by copying the shape of bulk_lock_users's ownership-guard handling, but the actual mutation logic sits much closer below it here — reading top-to-bottom, the eye can slip from "handle the exception" straight into "now do the write" without registering that a continue is what's supposed to separate those two ideas. This is exactly why comparing near-identical sibling files line-by-line (as you're doing across this whole series) catches bugs that reading any single file in isolation wouldn't.

# Why does this file mix str(e) (correct, for ApplicationError) and str(e.message) (incorrect, for generic Exception) in two adjacent blocks?
# Worth naming as its own lesson: consistency-by-habit is dangerous when the underlying rule actually depends on what's being caught, not just "this shape of code worked a few lines up." str(e.message) was safe in the ApplicationError context specifically because you'd already confirmed that class always populates .message. Copying that same access pattern into a differently-scoped except block, catching a completely different (and much broader) category of exception, breaks the assumption that made it safe in the first place.

# 8. DIY Recipe — build one like this yourself
# Every try/except that's meant to stop further processing for this item must end with continue — verify this explicitly for every guard-chain block, not just the ones you remember to check.
# Match your exception-message extraction to what you're actually catching: except YourOwnExceptionType as e: str(e.message) only when you've confirmed that exact class always sets .message. except Exception as e: (or any broad/generic catch) should always use str(e), since you can't assume anything about .message existing on an arbitrary exception.
# When copying a guard-chain pattern from a sibling file, verify each block still has its continue — don't just match the visual shape, trace what happens on both the success and failure path of each try.
# 9. General pattern recognition

# Same "guard chain" pattern as bulk_lock_users — self-action check, then "already in target state" check, then the ownership guard, then the actual write — but this file is a cautionary instance of the pattern partially implemented: the chain's structure is present, but one link (the missing continue) doesn't actually block anything, which is worse than not having the guard at all, since it creates a false sense of protection.

# 10. Real project usage
# python
# def resolve_bulk_delete_users(self, info, user_ids: list[str]) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     result = bulk_delete_users(
#         user_ids=user_ids,
#         company_id=actor.company_id,
#         current_user_id=str(actor.id),
#     )
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)
# 11. Common beginner mistakes

# ❌ The exact bug here — recording a guard rejection without a continue, letting the protected action happen anyway. Worth internalizing as its own named trap: a caught exception that doesn't continue/return after handling it is a silent pass-through, not a block — catching an exception stops the crash, but does nothing on its own to stop the rest of the function from running.

# ❌ The second exact bug here — assuming .message exists on any caught exception, when it's specific to certain exception classes. str(e) is the safe, general default; .message is an assumption that needs to be verified per exception type.

# ❌ Copying a code pattern from a nearby correct block without checking whether the surrounding context (what's being caught, what should happen next) actually matches.

# 12. Think like the original developer
# What problem am I solving? "Bulk soft-delete accounts, protecting against self-deletion, redundant deletion, and ownership-invariant violations, with an accurate itemized report."
# What inputs will I need? Target IDs, company scope, and the acting user's own ID for self-protection.
# What could go wrong? Self-deletion; deleting an already-deleted account; violating the last-owner/founder invariant — and if any of those checks catch a real violation, that must actually stop the delete from happening, not just log that it should have.
# How should I report failure? Distinctly per cause, and — critically — a recorded failure must correspond to an action that actually didn't happen, or the report itself becomes untrustworthy.
# What should happen if everything works? Both flags flip together, saved narrowly, with every guard that fired actually having prevented the write it was meant to prevent — not just noted it after the fact.