from __future__ import annotations
from typing import Iterable
from django.db import transaction
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.core.services.bulk_result import BulkActionResult
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError
def bulk_force_password_reset(*, user_ids: Iterable[str], company_id: str, current_user_id: str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    current_user_id = current_user_id
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        if uid == current_user_id:
            result.add_failure(user_id=uid, reason="Cannot force password reset on your on account")
            continue
        try:
            assert_not_last_owner(user=user, company_id=company_id, action="force password rest")
        except ApplicationError as e:
            result.add_failure(user_id=uid, reason=str(e))
            continue

        try:
            with transaction.atomic():
                user.password_reset_required = True
                user.save(update_fields = ["password_reset_required"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")

    return result


# 1. Purpose — Why this exists

# What problem is this solving?
# The bulk sibling of force_password_reset — flag many accounts at once as requiring a password reset, in one batch operation, with an itemized report of which succeeded and which didn't exist in this company.

# Why not just loop and call the single-user force_password_reset from the resolver?
# Same reasoning as every bulk function — one company-scoped query for the whole batch instead of N separate lookups, and one accumulator giving a structured, itemized outcome instead of the resolver having to build that itself.

# When is this used?
# A bulk security action — say, after discovering a shared or leaked password pattern across several accounts, forcing all of them to set a new password on next login.

# What breaks without it?
# N individual lookups per user instead of one batch fetch, and no structured way to report which of the requested IDs weren't actually found.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult

# Nothing new — the exact minimal import set for a bulk function that doesn't need the ownership guard (no assert_not_last_owner, no ApplicationError — we'll confirm in Section 7 why that's correct, not an oversight).

# 3. Signature — every symbol explained
# python
# def bulk_force_password_reset(*, user_ids: Iterable[str], company_id: str) -> BulkActionResult:

# Textbook match to the established pattern: no @transaction.atomic on the function (correct — per-item atomicity is your project's confirmed intent for bulk operations), keyword-only *, user_ids: Iterable[str] correctly typed as a collection, company_id: str mandatory, and a correct, present -> BulkActionResult return hint.

# 4. Classes

# No class defined here — BulkActionResult constructed and used, not defined, same as every sibling.

# 5. Body — line by line
# python
# result = BulkActionResult()
# normalized_ids = [str(uid) for uid in user_ids]
# users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# Correct on every count worth double-checking against what you've learned across this whole series: the transformed list gets its own distinct name (normalized_ids, not reusing user_ids — the exact fix from several turns ago), and found_ids correctly extracts .id (not the bare str(u) mistake from bulk_lock_users) — so the later set-subtraction will actually work as intended.

# python
# for user in users:
#     uid = str(user.id)
#     try:
#         with transaction.atomic():
#             user.password_reset_required = True
#             user.save(update_fields=["password_reset_required"])
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e))

# Exactly the per-item atomicity pattern you settled on as your project's standard: with transaction.atomic(): scoped tightly around just the assignment and narrow save, try/except Exception catching any save failure and converting it into a recorded per-item failure rather than crashing the batch, add_success(user_id=uid) correctly using the keyword.

# python
# for missing in set(normalized_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# return result

# Correct — both sets built from consistent, string-normalized IDs (traced the same way you verified for yourself two turns ago), so this subtraction will correctly identify genuinely-missing IDs without also poisoning the report for users that were actually found and processed above.

# 6. Beginner questions, answered proactively

# Why does this file not need the "can't act on your own account" check bulk_lock_users had?
# Worth asking explicitly rather than assuming symmetry between similar-looking bulk functions. Locking your own account mid-action is a genuine operational hazard — you could lose your own access while performing the action. Forcing your own password reset isn't remotely comparable in risk — at worst, you'd need to set a new password on your next login, which isn't a lockout, isn't unusual, and isn't something worth specifically guarding against. Different actions carry different actual risks, and the presence or absence of a self-action guard should track that, not just mirror whatever the previous file happened to include.

# Why no full_clean() before the save?
# Same reasoning as force_password_reset and activate_user — a single boolean flip has nothing meaningful to validate, so full_clean() would add overhead without protecting against anything relevant to this specific change.

# 7. Design discussion — does this need the ownership guard?

# This is the deliberate check worth running, given the last file's actual bug lived in a different spot but the last file's concept (composing assert_not_last_owner into a bulk loop) is fresh. Apply the same test from activate_user's design discussion: what specific harm does assert_not_last_owner protect against, and could this action cause that harm?

# assert_not_last_owner protects against a company ending up with zero active superusers, and against ever modifying the founder's account. Forcing a password reset does neither of those things — it doesn't touch is_superuser, doesn't touch is_active, doesn't remove anyone's standing or capability to act as an owner in any way. A superuser who's forced to reset their password is still a superuser, still active, still fully capable of managing the company the moment they set a new password. The specific risk the guard exists to prevent simply doesn't apply here, exactly as it didn't apply to activate_user.

# Correctly omitted, not a gap. This is a good instance of the discipline you're building: not reflexively adding every safety check to every function that touches a User, but reasoning about which specific risks each specific action actually carries.

# One thing genuinely worth asking, though, as a real design question rather than a bug: should the founder be exempt from having their password reset forced on them by another staff member, on the theory that the founder shouldn't be actionable by ordinary staff at all, even in ways that don't touch ownership standing? That's a legitimate policy question your team would need to answer — but it's a different kind of protection than what assert_not_last_owner provides (which is specifically about ownership continuity, not about founder-untouchability in general), so it wouldn't be solved by reusing that same guard function even if the answer is "yes."

# 8. DIY Recipe — build one like this yourself
# Start from the established bulk template: accumulator, normalized IDs (own variable name), one batch query, found_ids built from .id specifically.
# For each per-item action, ask what specific harms are possible, and only add the guards that address those specific harms — don't copy a sibling function's guard checks just because the files look similar.
# Keep per-item atomicity and exception handling identical across every bulk function in the family, for predictable, consistent behavior no matter which bulk action a caller is using.
# Verify found_ids is built from the correct field every time you write this pattern — this is the one line worth double-checking by hand, given how easily it goes wrong invisibly.
# 9. General pattern recognition

# The cleanest example yet of the "batch fetch, per-item action, itemized report" pattern, with zero extra guard chains — worth keeping as your mental reference template for what this pattern looks like at its simplest, to compare future bulk functions against when deciding whether they need additional guards layered in.

# 10. Real project usage
# python
# def resolve_bulk_force_password_reset(self, info, user_ids: list[str]) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.force_password_reset")
#     result = bulk_force_password_reset(user_ids=user_ids, company_id=actor.company_id)
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)

# Notice the permission codename matches the narrow, specific one from single-user force_password_reset's real-usage example — this bulk action should require the same specific permission as its single-user counterpart, not a broader one.

# 11. Common beginner mistakes

# ❌ Adding assert_not_last_owner here "to be consistent" with bulk_lock_users, without checking whether this specific action actually risks what that guard protects against.

# ❌ Forgetting the .id on found_ids — the exact bug from the previous file — worth treating as a standing checklist item every time this template gets reused.

# ❌ Reusing the parameter name for the normalized list instead of giving it its own name — the habit this whole series has been reinforcing since a few turns back.

# 12. Think like the original developer
# What problem am I solving? "Force a batch of accounts to reset their password on next login, with a clean itemized report of what happened to each requested ID."
# What inputs will I need? The target IDs and the company scope — no acting-user context needed, since this action carries no self-harm risk worth guarding against.
# What could go wrong? Some IDs don't exist in this company; an individual save fails for an unrelated reason — nothing here risks violating an ownership invariant, so no guard chain is needed beyond existence-checking.
# How should I report results? The standard itemized accumulator — same shape as every sibling bulk function.
# What should happen if everything works? Every found user gets flagged for a mandatory reset, every genuinely missing ID gets reported as such, and one user's unexpected save failure never threatens anyone else's already-completed reset in the same batch.

# i have a question -> in bulk lock user ->

# from __future__ import annotations
# from typing import Iterable
# from django.utils import timezone
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# from lrb.core.exceptions import ApplicationError


# def bulk_lock_users(
#     *,
#     user_ids: Iterable[str],
#     company_id: str,
#     current_user_id: str,
#     duration_minutes: int = 15,
# ) -> BulkActionResult:
#     result = BulkActionResult()
#     normalized_ids = [str(uid) for uid in user_ids]
#     current_user_id = str(current_user_id)
#     users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
#     found_ids = {str(u.id) for u in users}
#     locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)

#     for user in users:
#         uid = str(user.id)

#         if uid == current_user_id:
#             result.add_failure(user_id=uid, reason="Cannot lock your own account")
#             continue
#         try:
#             assert_not_last_owner(user=user, company_id=company_id, action="locked")
#         except ApplicationError as e:
#             result.add_failure(user_id=uid, reason=str(e.message))
#             continue
#         try:
#             with transaction.atomic():
#                 user.locked_until = locked_until
#                 user.save(update_fields=["locked_until"])
#             result.add_success(user_id=uid)
#         except Exception as e:
#             result.add_failure(user_id=uid, reason=str(e))

#     for missing in set(normalized_ids) - found_ids:
#         result.add_failure(user_id=missing, reason="User not found in this company.")

#     return result
#  -> how are you sure is the current _user_id where  is it coming from or when you use it is when you define the current user id

