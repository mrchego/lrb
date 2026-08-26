from __future__ import annotations
from typing import Iterable
from django.db import transaction
from lrb.core.exceptions import ApplicationError
from lrb.core.services.bulk_result import BulkActionResult
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.accounts.services.ownership_guard import assert_not_last_owner

def bulk_deactivate_users(*, user_ids: Iterable[str], company_id:str, current_user_id:str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    current_user_id = str(current_user_id)
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        if uid == current_user_id:
            result.add_failure(user_id=uid, reason="You cannot deactivate your own account")
            continue

        if not user.is_active:
            result.add_failure(user_id=uid, reason="user is not active")
            continue

        try:
            assert_not_last_owner(user=user, company_id=company_id, action="deactivated")
        except ApplicationError as e:
            result.add_failure(user_id=uid, reason=str(e.message))
            continue

        try:
            with transaction.atomic():
                user.is_active = False
                user.save(update_fields=["is_active"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in company")

    return result


# bulk_deactivate_users — Full Walkthrough

# This one is correct — every lesson from the last two files has actually been applied. Let's verify each specifically rather than just declare it clean, then do the full walkthrough.

# Verification pass — checking against the two bugs you just fixed elsewhere

# The missing continue from bulk_delete_users:

# python
# try:
#     assert_not_last_owner(user=user, company_id=company_id, action="deactivated")
# except ApplicationError as e:
#     result.add_failure(user_id=uid, reason=str(e.message))
#     continue

# Present. A rejection here genuinely stops execution for this user — it will not fall through into the delete/deactivate block below it.

# The .message vs str(e) mixup from bulk_delete_users:

# python
# except ApplicationError as e:
#     result.add_failure(user_id=uid, reason=str(e.message))   # ← ApplicationError, confirmed to store a plain message — correct here
# ...
# except Exception as e:
#     result.add_failure(user_id=uid, reason=str(e))            # ← generic catch — correct, general-purpose

# Both are used in exactly the right place this time — .message only where the caught type is your own ApplicationError (safe, confirmed), and str(e) for the wide, generic except Exception (safe for any exception type). This is the precise distinction we walked through last turn, correctly applied here.

# found_ids built from .id, not the bare str(u) mistake from bulk_lock_users:

# python
# found_ids = {str(u.id) for u in users}

# Correct.

# Nothing left to fix. On to the full walkthrough.

# 1. Purpose — Why this exists

# What problem is this solving?
# The bulk sibling of deactivate_user — suspend a batch of accounts at once (setting is_active=False, distinct from delete_user's two-flag soft-delete), while protecting against self-deactivation, redundant deactivation, and ownership-invariant violations, with a full itemized report.

# Why not just loop and call the single-user deactivate_user?
# Same efficiency and reporting reasoning as every bulk function in this family.

# When is this used?
# A bulk "suspend these accounts" admin action — reversible via activate_user, unlike delete_user's more permanent-feeling can_login=False combination.

# What breaks without it?
# N individual lookups instead of one batch fetch, and no itemized way to see which accounts were skipped and why.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.core.exceptions import ApplicationError
# from lrb.core.services.bulk_result import BulkActionResult
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.accounts.services.ownership_guard import assert_not_last_owner

# Identical set to bulk_delete_users — same tools, same reasons, nothing new mechanically.

# 3. Signature — every symbol explained
# python
# def bulk_deactivate_users(*, user_ids: Iterable[str], company_id: str, current_user_id: str) -> BulkActionResult:

# Matches the established template exactly — same shape as bulk_delete_users and bulk_lock_users, since this function carries the same category of risk (removing standing/access) as both.

# 4. Classes

# No class defined — consistent with every sibling.

# 5. Body — line by line
# python
# result = BulkActionResult()
# normalized_ids = [str(uid) for uid in user_ids]
# current_user_id = str(current_user_id)
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# Correct setup, matching the template precisely.

# python
# for user in users:
#     uid = str(user.id)
#     if uid == current_user_id:
#         result.add_failure(user_id=uid, reason="You cannot deactivate your own account")
#         continue

#     if not user.is_active:
#         result.add_failure(user_id=uid, reason="user is not active")
#         continue

# Two cheap guard checks — self-action protection (same mechanism, same origin as current_user_id you traced back to the resolver last turn), and an "already in target state" check. Notice this one is simpler than bulk_delete_users's equivalent (not user.is_active and not user.can_login) — here there's only one flag being changed (is_active), so checking just that one flag's current state is the correct, proportionate equivalent, not an oversight.

# python
#     try:
#         assert_not_last_owner(user=user, company_id=company_id, action="deactivated")
#     except ApplicationError as e:
#         result.add_failure(user_id=uid, reason=str(e.message))
#         continue

# Correctly structured guard-chain block — the continue actually stops this user from reaching the write below it if they're the founder or the last active owner.

# python
#     try:
#         with transaction.atomic():
#             user.is_active = False
#             user.save(update_fields=["is_active"])
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e))

# Correct per-item atomicity pattern, matching every sibling — narrow transaction scope, generic exception catch using the safe str(e), keyword-correct add_success.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in company")

# return result

# Correct, consistent with the whole family.

# 6. Beginner questions, answered proactively

# Why does bulk_delete_users check two flags (not is_active and not can_login) for "already done," but this file checks only one (not is_active)?
# Because each function's notion of "done" matches exactly what that function itself changes. delete_user/bulk_delete_users define "deleted" as both flags being False together — checking only one would incorrectly treat a user who's merely deactivated (but can still theoretically log in once reactivated) as "already deleted." deactivate_user/bulk_deactivate_users only ever touch is_active — so checking that one flag alone correctly and completely captures "is there anything left for this specific action to do."

# Why does the ownership guard matter here specifically, when it didn't for activate_user or bulk_force_password_reset?
# Because deactivating someone is exactly the kind of action assert_not_last_owner exists for — it removes the target's ability to act (an inactive user presumably can't log in or perform any staff actions), which is precisely the "could this leave the company with no working owner" question the guard is built to answer. This sits in the same category as demote_owner, lock_user, and delete_user — all actions that reduce someone's standing — correctly distinct from activate_user's or bulk_force_password_reset's risk profile, which don't.

# 7. Design discussion

# Is there a design reason bulk_deactivate_users and bulk_delete_users exist as two separate functions rather than one function with a "how much to deactivate" flag?
# Worth naming, since you've now built both: they represent two meaningfully different real-world actions with different reversibility and different intent — a suspension you expect to lift (is_active only, reversible via activate_user) versus something closer to an offboarding (is_active and can_login together). Keeping them as separate, explicitly-named functions makes each call site self-documenting — a reviewer reading bulk_deactivate_users(...) in a resolver instantly knows the scope of what's happening, without needing to check what flag value was passed to a more generic combined function.

# 8. DIY Recipe — build one like this yourself

# By this point in the series, this file is the recipe, executed correctly — the checklist to run against any new bulk action in this family:

# Accumulator, normalized IDs (own name), one batch fetch, found_ids from .id.
# Self-action guard, if the action could plausibly harm the actor themselves.
# "Already in target state" guard, checking exactly the flag(s) this specific action changes — no more, no less.
# Ownership guard, wrapped in try/except ApplicationError, with continue, only if this action actually reduces someone's standing or access.
# Per-item atomic write, wrapped in try/except Exception, using str(e).
# Missing-ID report at the end, using the same normalized/found sets.
# 9. General pattern recognition

# The "guard chain" pattern, now seen fully correct end-to-end — self-check, state-check, invariant-check, write — every link actually blocking what it's supposed to block. Comparing this file against bulk_delete_users's broken version is a good concrete lesson in why tracing every continue matters as much as recognizing the overall shape.

# 10. Real project usage
# python
# def resolve_bulk_deactivate_users(self, info, user_ids: list[str]) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     result = bulk_deactivate_users(
#         user_ids=user_ids,
#         company_id=actor.company_id,
#         current_user_id=str(actor.id),
#     )
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)
# 11. Common beginner mistakes

# ❌ Checking the wrong set of flags for "already done" — always match the check to exactly what the specific action modifies, not a broader or narrower set borrowed from a similar-looking sibling function.

# ❌ Forgetting continue after any guard rejection — the exact bug from the previous file; worth checking explicitly every time, since it's invisible unless you specifically trace what happens after the except block runs.

# ❌ Applying .message or str(e) inconsistently without checking which exception type is actually being caught in each specific block.

# 12. Think like the original developer
# What problem am I solving? "Bulk-suspend accounts, protecting against self-deactivation, redundant deactivation, and ownership-invariant violations, with an accurate report."
# What inputs will I need? Target IDs, company scope, acting user's ID.
# What could go wrong? Self-deactivation; deactivating an already-inactive account; violating the last-owner/founder invariant — and each of those must genuinely prevent the write, not just report it happened.
# How should I report failure? Distinctly per cause, matching exactly what changed (or didn't).
# What should happen if everything works? is_active flips, saved narrowly, with every guard that fired having actually done its job.