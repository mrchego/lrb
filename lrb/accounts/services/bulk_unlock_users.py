from __future__ import annotations
from typing import Iterable
from django.db import transaction
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
from lrb.core.services.bulk_result import BulkActionResult


def bulk_unlock_users(*, user_ids: Iterable[str], company_id: str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        try:
            with transaction.atomic():
                user.locked_until = None
                user.failed_login_attempts = 0
                user.save(update_fields=["locked_until", "failed_login_attempts"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="User not found in this company.")

    return result


# 1. Purpose — Why this exists

# What problem is this solving?
# Sometimes a staff member needs to unlock several accounts at once — say, after a bulk brute-force lockout event, or when reversing a mass lockout caused by a bug. Rather than calling a hypothetical single unlock_user in a loop from the resolver (which would mean the resolver owns the batching logic), this function owns the whole batch operation itself: find which of the requested users actually exist (scoped to a company), unlock each one, and report back exactly what happened to each ID.

# Why not just loop over IDs and call a single-user unlock function from the resolver?
# Because this function needs to report a rich, itemized result (BulkActionResult) rather than an all-or-nothing outcome, and it needs one shared, company-scoped fetch (get_users_by_ids) rather than one query per user — the exact efficiency reasoning that motivated get_users_by_ids's design in the first place.

# When is this used?
# A bulk "unlock selected accounts" action on an admin screen — multi-select several locked users, click one button, get back a report of which succeeded and which weren't found.

# What breaks without it?
# Either a resolver doing N individual queries and N individual unlock calls (inefficient, and awkward to report partial results from), or a bulk function with no structured way to report per-user outcomes.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult

# Nothing genuinely new here — Iterable (a collection you can loop over, same as count_active_superusers's exclude_ids), transaction for the atomic decorator, get_users_by_ids via direct submodule import (matching your established convention), and BulkActionResult — the accumulator class you just built, imported from lrb.core.services.bulk_result. That import path itself is informative: BulkActionResult lives in core, not accounts — meaning it's meant to be a generic reusable accumulator for any bulk action across the whole project (bulk role changes, bulk deletions elsewhere), not something tied specifically to user accounts.

# 3. Signature — every symbol explained
# python
# @transaction.atomic
# def bulk_unlock_users(*, user_ids: Iterable[str], company_id: str):

# @transaction.atomic — familiar decorator, though we'll examine in Section 7 whether it's actually doing the right thing here, because bulk operations raise a genuinely new question about what "atomic" should mean.

# (*, user_ids: Iterable[str], company_id: str) — keyword-only, consistent with everything else. user_ids: Iterable[str] correctly typed as a collection (learned from the get_users_by_ids bug fix earlier). company_id: str — mandatory, no default, matching the safer "force the caller to be explicit about scope" design from that same earlier fix.

# Missing: a return type hint. Every other multi-line service function in this project has one (-> User, -> None). This function clearly returns a BulkActionResult (see the final return result line) — the signature should read:

# python
# def bulk_unlock_users(*, user_ids: Iterable[str], company_id: str) -> BulkActionResult:

# This isn't cosmetic — without it, a caller has to read the whole function body to discover what they'll get back, exactly the gap you already caught in get_users_by_ids several turns ago.

# 4. Classes

# No class defined in this file — but this is the first bulk function to actually use a class you built (BulkActionResult) as its core working data structure, rather than just returning a plain value. result = BulkActionResult() — same construction mechanism as User(...) — builds one fresh, empty instance.

# 5. Body — line by line
# python
# result = BulkActionResult()

# Construct one fresh accumulator — its succeeded and failed lists both start empty, thanks to field(default_factory=list).

# python
# user_ids = [str(uid) for uid in user_ids]

# This is a list comprehension — a compact way of writing "build a new list by transforming each item in an existing collection." Read it as: for each uid found while looping over user_ids, put str(uid) into the new list. This normalizes every ID to a plain string, in case the caller passed something else (integers, UUID objects) — the same defensive str(...) conversion habit you applied yourself in assert_not_last_owner's call sites.

# Worth flagging as a naming habit, not a bug: the result is stored back into a variable named user_ids — the same name as the original parameter. This is legal and common, but means the original, un-normalized user_ids the caller passed in no longer exists anywhere after this line; only the normalized version remains. It works fine here because nothing downstream needs the original, but it's worth being conscious of: reusing a parameter's name for a transformed version of itself can make debugging harder later ("wait, is this the original or the normalized one?") if the function grows more complex.

# python
# users = list(get_users_by_ids(user_ids=user_ids, company_id=company_id))

# Calling the selector you reviewed a few turns ago — remember, it returns a lazy queryset by design, so wrapping it in list(...) here forces exactly one database query to actually run, fetching every matching user in this one call, company-scoped. This is the direct payoff of get_users_by_ids's design: one query for the whole batch, not one query per ID.

# python
# found_ids = {str(u.id) for u in users}

# This is a set comprehension — same shape as the list comprehension above, but built with {} instead of [], producing a set (a collection of unique values, unordered, with fast membership testing) instead of a list. For each u in users, take str(u.id). The choice of a set here, rather than a list, is deliberate and important — it's what makes the next part of the function efficient.

# python
# for user in users:
#     uid = str(user.id)
#     user.locked_until = None
#     user.failed_login_attempts = 0
#     user.save(update_fields=["locked_until", "failed_login_attempts"])
#     result.add_success(user_id=uid)

# A for loop over every user that was actually found. For each one: grab their ID as a string, reset both locked_until (to None — "not locked") and failed_login_attempts (to 0 — a fresh start, presumably preventing an immediate re-lock from stale attempt counts), save narrowly with update_fields covering exactly those two changed columns, then record the success into the accumulator via the method you fixed a few turns ago.

# Notice: no full_clean() here, matching the established "single/simple-flag change, nothing meaningful to validate" reasoning from force_password_reset and activate_user.

# python
# for missing in set(user_ids) - found_ids:
#     result.add_failure(user_id=missing, reason="User not found in this company.")

# The - between two sets is set subtraction — "give me everything in the left set that is not in the right set." set(user_ids) — every ID the caller originally asked for, converted to a set. found_ids — every ID that was actually found in the database (already a set from the comprehension above). Subtracting gives you exactly the IDs that were requested but never found — either they don't exist at all, or they exist but belong to a different company (since get_users_by_ids scoped the query to company_id).

# This is precisely why found_ids needed to be a set and not a list — set subtraction is a fast, direct way to compute "what's missing," compared to manually looping and checking if uid not in found_ids_list for every ID (which would work, but far less efficiently and less readably for large batches).

# python
# return result

# Hand back the fully populated accumulator — every requested ID accounted for, either in succeeded or failed.

# 6. Beginner questions, answered proactively

# Why loop over users (the found objects) for successes, but loop over set(user_ids) - found_ids (just ID strings) for failures?
# Because you have genuinely different information available for each case. For a found user, you have the full User object — you need it anyway to mutate and save it. For a missing ID, there's no object at all — there's nothing in the database to loop over — so the only thing you can report is the bare ID string that never matched anything.

# Why is "User not found in this company." used as the one blanket reason for every missing ID, even though "doesn't exist at all" and "exists but wrong company" are different situations?
# Worth flagging as a genuine design question rather than assuming it's fine: get_users_by_ids's company scoping means this function structurally cannot tell these two cases apart — both produce the exact same "not in found_ids" outcome. If distinguishing them mattered for your admin UI (arguably it might — "wrong company" could indicate someone probing IDs across company boundaries, worth flagging differently than a genuine typo), you'd need an unscoped lookup as a secondary check specifically for building a more precise failure reason — a real trade-off between simplicity and diagnostic precision.

# Why compute found_ids as a whole separate set instead of just checking len(users) == len(user_ids) and reporting all-or-nothing?
# Because a caller genuinely needs to know which specific IDs were missing, not just "some were missing" — this is exactly the granularity BulkActionResult exists to provide, and a simple length comparison would throw that away.

# 7. Design discussion — the real question: what should @transaction.atomic mean for a bulk operation?

# This is worth genuine scrutiny, because it's a real tension between two ideas that both sound reasonable individually, but conflict with each other here.

# What @transaction.atomic actually guarantees: every database write inside this function either all commit together, or — if any exception escapes the function uncaught — all get rolled back together, as if none of them happened.

# What BulkActionResult implies as a design intent: "some of this batch can succeed while others fail" — the entire reason the class has separate succeeded/failed lists rather than a single pass/fail flag.

# Here's the conflict, made concrete: imagine unlocking 50 users. The loop successfully unlocks and saves the first 40. On user #41, something throws an uncaught exception during .save() — say, a genuine IntegrityError from some constraint you haven't anticipated. That exception is not caught anywhere in this function — there's no try/except around the loop body at all. It propagates straight out of bulk_unlock_users, and because of @transaction.atomic, Django rolls back every write in this entire function — including the 40 users that had already succeeded moments earlier. The caller never even gets a BulkActionResult back at all; they get a raised exception instead, and every "successful" unlock silently vanishes from the database, with zero record of which 40 had actually worked.

# In other words: this function currently has all the scaffolding for graceful partial success (the accumulator, the two lists, the per-item failure reasons) but none of the actual exception handling that would make partial success genuinely possible. As written, it's actually all-or-nothing at the database level, just with reporting logic that implies otherwise for a category of failure (missing IDs) that happens to not need the database at all to detect.

# What would need to change to make partial success real, if that's the actual intent: wrap each iteration's save in its own try/except, and reconsider whether the whole operation should be one atomic block, or whether each individual user's unlock should be its own smaller atomic unit:

# python
# for user in users:
#     uid = str(user.id)
#     try:
#         with transaction.atomic():
#             user.locked_until = None
#             user.failed_login_attempts = 0
#             user.save(update_fields=["locked_until", "failed_login_attempts"])
#         result.add_success(user_id=uid)
#     except Exception as e:
#         result.add_failure(user_id=uid, reason=str(e))

# Using transaction.atomic() as a context manager (the with syntax) per user inside the loop, rather than one @transaction.atomic wrapping the whole function, means one user's failure rolls back only that user's changes, while everything already committed for earlier users in the batch stays committed.

# This is worth raising as a real open question to whoever owns this code, not silently "fixing" on the assumption I know the intended behavior — some teams genuinely do want bulk operations to be all-or-nothing (safer, simpler to reason about, easier to retry cleanly). If that's the actual intent here, the current code is already correct, and the accumulator's real value is just for reporting the missing-ID case (which never touches the database, so it was never at risk anyway). But if partial success across real save failures was actually intended, the current single outer @transaction.atomic quietly defeats that goal.

# 8. DIY Recipe — build one like this yourself
# Normalize input IDs to a consistent type up front (str(uid) for uid in user_ids) before using them for lookups or comparisons.
# Fetch the whole batch in one query via a company/scope-aware selector, wrapped in list(...) to materialize it once.
# Build a set of found IDs, not a list, specifically to enable fast set-subtraction against the originally requested IDs.
# Loop over found objects for the "happy path," mutating and saving each, recording each success into your accumulator.
# Compute the missing IDs via set subtraction (requested - found) and record each as a failure with a clear, consistent reason.
# Explicitly decide, and document, whether the whole batch should be one atomic transaction or per-item atomic units — don't let this default silently to "all-or-nothing" just because @transaction.atomic was copy-pasted from a single-user function without reconsidering what it means at batch scale.
# Give the whole function an explicit return type hint naming the accumulator class it returns.
# 9. General pattern recognition

# This is the "batch fetch, per-item action, itemized report" pattern — the natural extension of "single-flag action" (activate_user) to a batch:

# python
# @transaction.atomic  # or per-item, per the discussion above
# def bulk_<verb>_<things>(*, thing_ids: Iterable[str], company_id: str) -> BulkActionResult:
#     result = BulkActionResult()
#     thing_ids = [str(i) for i in thing_ids]
#     things = list(get_things_by_ids(thing_ids=thing_ids, company_id=company_id))
#     found_ids = {str(t.id) for t in things}
#     for thing in things:
#         <mutate and save>
#         result.add_success(user_id=str(thing.id))
#     for missing in set(thing_ids) - found_ids:
#         result.add_failure(user_id=missing, reason="Not found in this company.")
#     return result

# You'll reuse this exact shape for bulk_deactivate_users, bulk_revoke_role, or any other "act on many, report per-item" operation.

# 10. Real project usage
# python
# def resolve_bulk_unlock_users(self, info, user_ids: list[str]) -> BulkActionPayload:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.manage_users")
#     result = bulk_unlock_users(user_ids=user_ids, company_id=actor.company_id)
#     return BulkActionPayload(succeeded=result.succeeded, failed=result.failed)
# 11. Common beginner mistakes

# ❌ Assuming @transaction.atomic and a partial-success accumulator naturally coexist — as this file shows, they actively conflict unless you deliberately scope the atomic boundary to each item, not the whole batch.

# ❌ Using a list instead of a set for found_ids, making the "what's missing" computation slower and more awkward to express than a clean set subtraction.

# ❌ Forgetting to normalize ID types before comparing/looking them up — a UUID object and its string representation won't match in a set/dict comparison even though they "look the same."

# ❌ Skipping the return type hint on a function whose return type isn't a plain built-in — exactly the same gap flagged in get_users_by_ids and now repeated here.

# 12. Think like the original developer
# What problem am I solving? "Unlock a batch of users at once, scoped to one company, and tell the caller exactly which succeeded and which weren't found."
# What inputs will I need? A collection of IDs (not a single one — this is fundamentally batch-shaped) and the company to scope the search to.
# What could go wrong? Some requested IDs don't exist, or belong to a different company; a normalization mismatch between ID types; and — the subtle one — an uncaught failure partway through silently discarding all prior progress if the transaction boundary isn't deliberately chosen.
# How should I report results? An itemized accumulator, not a single pass/fail — since "which specific ones failed and why" is exactly the information a bulk admin action needs to be actionable.
# What should happen if everything works? Every requested ID ends up in either succeeded or failed, with no ID unaccounted for — and a real decision, made deliberately rather than by default, about whether one item's failure should affect any others already processed in the same batch.

# letsfix this -> 

# from __future__ import annotations
# from typing import Iterable
# from django.db import transaction
# from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids
# from lrb.core.services.bulk_result import BulkActionResult


# @transaction.atomic
# def bulk_unlock_users(*, user_ids: Iterable[str], company_id: str) -> BulkActionResult:
#     result = BulkActionResult()
#     user_ids = [str(uid) for uid in user_ids]
#     users = list(get_users_by_ids(user_ids=user_ids, company_id=company_id))
#     found_ids = {str(u.id) for u in users}

#     for user in users:
#         uid = str(user.id)
#         user.locked_until = None
#         user.failed_login_attempts = 0
#         user.save(update_fields=["locked_until", "failed_login_attempts"])
#         result.add_success(user_id=uid)

#     for missing in set(user_ids) - found_ids:
#         result.add_failure(user_id=missing, reason="User not found in this company.")

#     return result ->Worth flagging as a naming habit, not a bug: the result is stored back into a variable named user_ids — the same name as the original parameter. This is legal and common, but means the original, un-normalized user_ids the caller passed in no longer exists anywhere after this line; only the normalized version remains. It works fine here because nothing downstream needs the original, but it's worth being conscious of: reusing a parameter's name for a transformed version of itself can make debugging harder later ("wait, is this the original or the normalized one?") if the function grows more complex.
    
    
#     What actually changed, and why each spot needed it

# user_ids = [str(uid) for uid in user_ids] → normalized_ids = [str(uid) for uid in user_ids]

# The right side still reads from the original parameter user_ids — that hasn't changed, and it's the last moment in the function where the original, un-normalized collection is ever touched. The left side now stores the result under a distinct name, normalized_ids, instead of overwriting user_ids.

# get_users_by_ids(user_ids=user_ids, ...) → get_users_by_ids(user_ids=normalized_ids, ...)

# This is the one place that has to change to keep using the normalized list — remember, get_users_by_ids's own parameter is also named user_ids (that's the "key," per your earlier question — belongs to get_users_by_ids's own signature), but the value now comes from normalized_ids instead.

# set(user_ids) - found_ids → set(normalized_ids) - found_ids

# Same reasoning — this needs the normalized, string-consistent collection to correctly subtract against found_ids (which is also built from str(...) conversions). If this had accidentally kept reading the raw user_ids parameter instead, and the caller had passed non-string IDs, the subtraction could produce wrong "missing" results due to type mismatches between the two sets.

# Why this is worth doing, concretely, not just as a style preference

# With the old version, if you added a debugging line or a log statement after the normalization step — say, to record what the caller originally asked for — user_ids at that point would already be the transformed version, and the original request would be unrecoverable without re-deriving it. With normalized_ids as a distinct name, both versions stay available and distinguishable for as long as either is needed, at zero cost — the rename doesn't change what the function does, only how easy it is to reason about later.


# What changed, and why each change matters

# The @transaction.atomic decorator on the function itself is gone. This is the key move — without it, the function as a whole no longer wraps everything in one transaction. Each user's write now stands or falls entirely on its own.

# with transaction.atomic(): inside the loop, one per user. This is transaction.atomic used as a context manager rather than a decorator — same underlying tool, different syntax for a different scope. A decorator wraps an entire function's execution; a with block wraps just the lines indented beneath it. Here, that's exactly the two field assignments and the save for one user — if anything inside that specific with block raises, only that block's writes get rolled back, leaving every previously-committed user from earlier loop iterations untouched.

# try: / except Exception as e: wrapping the whole per-user block. This is what actually catches the failure instead of letting it propagate out of the function. Previously, nothing caught a save failure at all — it would crash straight through. Now, if .save() raises anything (an IntegrityError, a validation problem, whatever), the except catches it, and instead of the whole function dying, this one user gets recorded as a failure with str(e) as the reason, and the loop continues to the next user.

# Why except Exception and not something narrower, like except IntegrityError? Because at this point in the code, you genuinely don't know every way a single save might fail, and the whole point of this design is resilience — one bad user shouldn't take down the batch, regardless of why that one user failed. This is a deliberate, wide net, appropriate specifically because each failure is being captured and reported, not silently swallowed — you still see exactly what went wrong for that one ID.

# The trade-off you're accepting with this choice, stated plainly

# This version runs one small transaction per user instead of one transaction for the whole batch — slightly more overhead per item, and it means a genuinely transient database issue (a brief connection blip) could cause a handful of scattered, unrelated-looking failures across the batch rather than one clean "the whole operation failed, try again" signal. For a bulk admin action processing tens of users, that overhead is negligible; if this pattern ever needed to scale to processing thousands of items per call, you'd want to revisit whether per-item transactions are still the right granularity — but at the scale everything in this project has shown so far, this is the right default.