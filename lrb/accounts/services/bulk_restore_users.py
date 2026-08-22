from __future__ import annotations
from typing import Iterable
from django.db import transaction
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.core.services.bulk_result import BulkActionResult

def bulk_restore_users(*, user_ids:Iterable[str], company_id:str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}
    
    for user in users:
        uid = str(user.id)
        if user.is_active and user.can_login:
            result.add_failure(user_id=uid, reason="Not deleted — nothing to restore.")
            continue
        try:
            with transaction.atomic():
                user.is_active=True
                user.can_login=True
                user.save(update_fields=["is_active", "can_login"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))
        
    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")
        
    return result

# 1. Purpose — Why this exists

# What problem is this solving?
# This is the reverse of a bulk soft-delete — restoring accounts that were previously deactivated (recall delete_user's pattern: is_active = False, can_login = False, without ever actually removing the row). bulk_restore_users flips both flags back for a batch of users at once, while correctly skipping anyone who's already active (nothing to restore) and reporting missing IDs the same way every other bulk function does.

# Why not just call a single-user restore_user in a loop from the resolver?
# Same reasoning as bulk_unlock_users — one shared, company-scoped fetch instead of N queries, and one accumulator giving an itemized report instead of an all-or-nothing outcome.

# When is this used?
# A bulk "restore selected accounts" admin action — reversing accidental or bulk deletions.

# What breaks without it?
# Either N individual queries per restore, or no structured way to report "these were already active, nothing needed doing" versus "these didn't exist at all" versus "these were genuinely restored."

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult

# Identical import set to bulk_unlock_users, for identical reasons — nothing new to explain here mechanically.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def bulk_restore_users(*, user_ids: Iterable[str], company_id: str) -> BulkActionResult:

# Same shape as bulk_unlock_users exactly — @transaction.atomic (with the same open design question from last time about whether batch-wide atomicity is the actual intent), keyword-only *, user_ids: Iterable[str] correctly typed as a collection, company_id: str mandatory, and a correct, present -> BulkActionResult return hint — notice this file didn't repeat the missing-return-hint gap you caught in the original bulk_unlock_users draft.

# 4. Classes

# No class defined here — BulkActionResult is constructed and used, same as before, but not defined in this file.

# 5. Body — line by line
# python
# result = BulkActionResult()
# normalized_id = [str(uid) for uid in user_ids]
# users = list(get_users_by_ids(user_ids=normalized_id, company_id=company_id))
# found_ids = {str(u.id) for u in users}

# Same shape as the fixed version of bulk_unlock_users — construct the accumulator, normalize IDs to strings, fetch the whole batch in one company-scoped query, build a set of found IDs for later subtraction.

# One naming inconsistency worth flagging, following directly from your last question's fix: the variable here is called normalized_id (singular), while the sibling file uses normalized_ids (plural) for the exact same kind of value — a list of multiple IDs. Not a bug (Python doesn't care what you name it), but worth matching across sibling files for the same reason we renamed it away from user_ids last time: consistency makes it obviously clear, at a glance across your codebase, what kind of value a name refers to. I'd rename it to normalized_ids here too.

# The new branch — the "nothing to restore" case
# python
# for user in users:
#     uid = str(user.id)
#     if user.is_active and user.can_login:
#         result.add_failure(user_id=uid, reason="Not deleted — nothing to restore.")
#         continue
#     user.is_active = True
#     user.can_login = True
#     user.save(update_fields=["is_active", "can_login"])
#     result.add_success(uid)

# if user.is_active and user.can_login: — a compound condition using and: both must be true for this branch to trigger. This checks: "is this user already in the fully-restored state?" If both flags are already True, there's genuinely nothing for this function to do for this particular user.

# result.add_failure(user_id=uid, reason="Not deleted — nothing to restore.") — worth pausing on this specific design choice: is "already active" really a failure? It's not an error in the sense of something going wrong — it's more like "no action was needed." Using add_failure here is a real, deliberate design decision (not a bug) to communicate to the caller "this ID didn't get restored," with a reason explaining why, distinguishing it from "this ID doesn't exist at all" (the other add_failure case later in the function) — both land in the same failed list, but with different, informative reasons a UI could distinguish.

# continue — a keyword you haven't seen explicitly named yet in this series, though the concept (skip the rest of this iteration, move to the next one) is implicit in early-return patterns you've seen in functions. Inside a loop, continue means: "stop processing this iteration right here, and jump straight to the next item in the loop" — as opposed to return, which would exit the entire function, not just this one iteration. This is exactly why continue is the right choice here: you want to skip this one user and keep processing the rest of the batch, not abandon the whole bulk operation.

# Below the if block (only reached if the condition was false — meaning at least one of the two flags was False): user.is_active = True, user.can_login = True — direct attribute assignment, restoring both flags. user.save(update_fields=["is_active", "can_login"]) — narrow save, same pattern as every single-flag/multi-flag action you've built.

# 🚩 The bug: result.add_success(uid)

# Compare this against BulkActionResult.add_success's actual signature:

# python
# def add_success(self, *, user_id: str) -> None:

# The lone * forces every argument after self to be passed by keyword. result.add_success(uid) passes uid positionally — no user_id= in front of it. This is exactly the rule you worked through, in detail, two turns ago when we discussed why add_success keeps its * at all — and here's the real-world consequence of that rule actually being enforced: this line will raise

# TypeError: add_success() takes 1 positional argument but 2 were given

# (the "1" being self, invisible to the caller but still counted) the very first time this function successfully restores anyone. Compare this against the sibling file, which gets it right: result.add_success(user_id=uid).

# Fix:

# python
# result.add_success(user_id=uid)
# The missing-IDs loop
# python
# for missing in set(normalized_id) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# Identical, correct pattern to bulk_unlock_users — same reasoning applies unchanged: both sets are guaranteed all-strings (traceable the same way you just verified yourself last turn), so user_id=missing is a valid string-to-str-hint match.

# python
# return result

# Return the fully populated accumulator.

# 6. Beginner questions, answered proactively

# Why does add_success(uid) crash but add_failure(user_id=uid, ...) right above it in the same loop doesn't?
# Because add_failure is being called correctly, with the keyword — the bug is isolated to exactly one call site in the whole file. This is worth noticing as its own lesson: a bug doesn't have to be systemic to be dangerous — one single incorrect call, sitting three lines below a correct one doing the same conceptual job, is enough to crash the function the moment execution reaches it.

# Why does the loop still reach result.add_success(uid) at all if the "already restored" case uses continue to skip past it?
# Because continue only skips the rest of that one iteration — for any user who does need restoring (at least one flag was False), execution falls through the if block entirely (the condition was false) and proceeds normally to the assignment, save, and add_success call. The bug only manifests for users who genuinely needed and received a real restore — anyone caught by the early continue never reaches the buggy line at all, which is exactly why this kind of bug can hide during casual testing if your test data happens to only include already-active users.

# Is "already active" really the same category as "not found"? Both call add_failure.
# Worth sitting with as a real design question, not just accepting it: they're two different reasons for "we didn't restore this ID," but they get bundled into the same failed list. If your admin UI needs to visually distinguish "no action needed" from "genuinely couldn't find this user," it can — since each carries its own distinct reason string — but if a UI is currently just checking "is this ID in failed, show a red X," both cases would look identical to an operator, which might be misleading (a user who was already fine isn't really a failure in the same sense as one that doesn't exist).

# 7. Design discussion

# Why check user.is_active and user.can_login together instead of restoring them independently — say, if only one of the two happened to be off?
# This mirrors delete_user's own design, which flips both flags together as one unit representing "deleted." Since both flags are set together on delete, checking both together on restore keeps the logic symmetric — "restore" undoes exactly what "delete" did, as one coherent state transition, rather than treating the two flags as independently meaningful.

# Same atomicity question as bulk_unlock_users applies here, unchanged: one uncaught exception partway through this loop, under the current single @transaction.atomic wrapping the whole function, would roll back every restore already completed in this batch. Worth resolving the same way, project-wide, rather than deciding it separately per bulk function.

# 8. DIY Recipe — build one like this yourself
# When a bulk action has a legitimate "nothing to do" case, decide deliberately whether that belongs in succeeded (arguably true — the desired end state is already achieved) or failed (this file's choice — flagging it as "no action taken," which the caller should probably know about).
# Use continue to skip the rest of a loop iteration when an early condition means the remaining lines in that iteration shouldn't run — don't wrap everything below in a nested else when a continue reads cleaner.
# Whenever calling one of your own class's methods, check its signature for * before writing the call — don't assume positional calling works just because it's your own method and the method body seems simple.
# Name transformed collections consistently across sibling files — normalized_ids, not normalized_id, for a list of several IDs.
# 9. General pattern recognition

# Same "batch fetch, per-item action, itemized report" pattern as bulk_unlock_users, with one addition worth naming as its own sub-pattern: the "already in target state" branch — checking whether the desired end state already holds, and reporting a distinct, informative "no action needed" outcome rather than silently skipping or incorrectly reporting success for an action that didn't actually happen.

# 10. Real project usage
# python
# def resolve_bulk_restore_users(self, info, user_ids: list[str]) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     result = bulk_restore_users(user_ids=user_ids, company_id=actor.company_id)
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)
# 11. Common beginner mistakes

# ❌ The exact bug here — calling a keyword-only method positionally, exactly the mistake the * exists to catch, and exactly why it's worth checking a method's own signature every time, not just assuming based on how similar calls look elsewhere in the same loop.

# ❌ Treating "already in the desired state" as either a silent no-op or an unconditional success without deciding deliberately which — and if choosing add_failure, making sure the reason string clearly distinguishes it from a genuine not-found case.

# ❌ Inconsistent naming of near-identical transformed variables across sibling files, making it harder to skim two similar functions side by side and trust they're doing the same thing the same way.

# 12. Think like the original developer
# What problem am I solving? "Restore a batch of previously-deactivated accounts, skipping anyone already active, and reporting exactly what happened to each requested ID."
# What inputs will I need? A collection of IDs and the company to scope the search to — same shape as every other bulk operation in this file family.
# What could go wrong? Some IDs don't exist in this company; some are already fully active with nothing to restore; a positional call to a keyword-only accumulator method crashes the whole successful-restore path.
# How should I report results? Itemized, per ID, distinguishing "genuinely restored," "already fine, nothing done," and "not found" — three meaningfully different outcomes even though two of them currently share the same failed bucket.
# What should happen if everything works? Every requested ID lands in either succeeded or failed with a clear reason, and the two flags that define "deleted" get restored together, symmetrically undoing exactly what delete_user did.