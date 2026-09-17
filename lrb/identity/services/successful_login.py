from django.utils import timezone

from lrb.accounts.services.unlock_user import unlock_user


def handle_successful_login(*, user):
    if user.failed_login_attempts > 0 or user.locked_until:
        unlock_user(user_id=user.id)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])


# 1. Purpose

# This function runs right after a successful login — the mirror image of handle_failed_login from earlier. Its two jobs: if the account had any failed attempts or was locked, clear that state; and record when this login happened. This is the piece that resets exactly the fields you saw _set_new_password and unlock_user (implied) touch — closing the loop on the account-lockout feature you've now seen from multiple angles.

# No crashing bugs here. I'll walk through it, then flag one real gap and one subtlety worth understanding.

# 2. Imports

# Both already familiar from earlier files: timezone for safe current-time handling, and unlock_user — a service import following the exact same lrb.<app>.services.<file> pattern as lock_user in handle_failed_login. Same architectural signal as before: "unlocking" is its own reusable concept, not inlined here.

# 3. Signature
# python
# def handle_successful_login(*, user):

# Same shape as every service function you've reviewed: * forces user to be passed as a keyword. No type hint on user, no -> None return hint — the same recurring, now-familiar gap in this codebase's consistency. You've spotted this pattern enough times now that it should jump out to you immediately without me needing to explain it fresh each time.

# 4. Body — step by step
# python
#     if user.failed_login_attempts > 0 or user.locked_until:
#         unlock_user(user_id=user.id)
# or — Python's logical-or operator: the whole condition is True if either side is True. Two separate reasons to unlock:
# user.failed_login_attempts > 0 — there's a nonzero failure count, even if the account was never actually locked (e.g., 2 failed attempts, threshold is 5 — never locked, but the counter should still reset on a good login).
# user.locked_until — truthy check: None is falsy, any actual datetime value is truthy — regardless of whether that datetime is in the past or future. This means even an expired lock (one that's already passed but never got cleaned up) still correctly triggers a cleanup call here.
# If either is true, calls unlock_user(user_id=user.id) — passing just the ID, not the whole user object, matching the same interface style as lock_user from before.
# python
#     user.last_login = timezone.now()
#     user.save(update_fields=["last_login"])
# Sets the in-memory last_login attribute to right now, then persists only that column via update_fields.
# 5. A subtlety worth understanding: the in-memory user object goes stale

# unlock_user(user_id=user.id) is passed an ID, not the user object itself. That almost certainly means unlock_user does its own separate database write internally — either fetching its own fresh copy of the user, or issuing a queryset-level .update() (like the bulk update pattern you saw in generate_verification_code). Either way, the user object sitting in this function's memory is never told about that change.

# Is this a bug? Not within this function — because the very next line uses update_fields=["last_login"], which only ever writes the last_login column, so this function can't accidentally overwrite unlock_user's work with stale in-memory values. That's actually the same defensive pattern you praised in earlier files.

# But it is a trap for whoever calls this function afterward. If the calling code (say, a login GraphQL resolver) does something like:

# python
# handle_successful_login(user=user)
# return {"locked": bool(user.locked_until)}  # still shows the OLD value!

# user.locked_until in Python memory still holds whatever it was before unlock_user ran, because nothing in this function ever re-reads it from the database. This is a general Python/Django gotcha: calling a function that changes a database row elsewhere does not automatically update the object you already have in memory. If a caller needs the fresh values, it would need to call user.refresh_from_db() afterward, or unlock_user would need to be written to mutate and return the same object it was given rather than working by ID alone. Not something to fix in this file — just something to know as you read the rest of the codebase.

# 6. Missing @transaction.atomic

# Same gap you caught in handle_failed_login: this function performs two separate write operations — the conditional unlock_user(...) call (itself a database write) and user.save(...). If the process crashes between them, you could end up with the account still logically "locked" in the database despite a login that just succeeded, or vice versa depending on what crashed. Per your project's own rule (atomic on all writes), this should be:

# python
# from django.db import transaction

# @transaction.atomic
# def handle_successful_login(*, user):
#     if user.failed_login_attempts > 0 or user.locked_until:
#         unlock_user(user_id=user.id)
#     user.last_login = timezone.now()
#     user.save(update_fields=["last_login"])
# 7. Why the corrected approach is better

# Wrapping both writes atomically guarantees they commit together — "unlock" and "record this login" either both happen or neither does, closing the same narrow-but-real gap you identified in handle_failed_login. This is a good sign you're starting to catch this specific drift yourself, pattern-matching it across files without me pointing it out line-by-line each time.

# 8. Connections
# Direct counterpart to handle_failed_login — together they form the complete lockout lifecycle: fail → increment → maybe lock; succeed → maybe unlock → record.
# Caller: almost certainly sits right after authenticate_credentials succeeds in a login mutation/resolver — handle_failed_login runs in the except/failure branch, handle_successful_login runs in the success branch.
# unlock_user is the write-side counterpart you haven't seen yet, but can now predict its shape confidently: probably resets failed_login_attempts = 0 and locked_until = None, saved with update_fields=[...], matching every pattern you've now seen repeated across this codebase.
# 9. What to remember
# or short-circuits on the first truthy value — either condition alone is enough to trigger the block; you don't need both.
# A bare object reference (if user.locked_until:) is truthy for any non-None value, including an already-expired timestamp — useful for triggering cleanup of stale state, not just active state.
# Passing an ID instead of a live object to another function often means that function does its own separate database write — and your original in-memory object won't reflect it afterward unless you explicitly refresh it.
# update_fields protects against overwriting changes made elsewhere, but it doesn't make your local Python object aware of those changes — those are two different problems with two different solutions.
# Once you've spotted a project convention violated in one file (@transaction.atomic missing on multi-write services), actively check for the same gap in every similar file you read next — you're now doing exactly that kind of pattern-matching across this whole login/lockout feature.