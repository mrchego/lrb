from lrb.accounts.services.lock_user import lock_user
from lrb.core.constants import LOCKOUT_DURATION_MINUTES, MAX_FAILED_ATTEMPTS


def handle_failed_login(*, user):
    if not user:
        return

    user.failed_login_attempts += 1
    user.save(update_fields=["failed_login_attempts"])

    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        lock_user(user_id=user.id, duration_minutes=LOCKOUT_DURATION_MINUTES)



# 1. Purpose

# This is a service function that handles what happens right after a login attempt fails. It increments a counter, and if that counter crosses a threshold, locks the account. This is the piece that actually uses the failed_login_attempts and locked_until fields you saw reset in the last file's _set_new_password — now you're seeing the other side of that same feature: brute-force protection.

# 2. Imports — explained from scratch
# python
# from lrb.accounts.services.lock_user import lock_user
# Another your-own-code import, following the pattern you've seen throughout: lrb.<app>.services.<file> — a service function pulled in from a different app (accounts) than wherever this file lives.
# This tells you something architectural: lock_user is a separate, reusable service — not something this file implements inline. That means "locking a user" is a concept important enough to exist on its own (other code, e.g. an admin action or a suspicious-activity check, can probably call lock_user too, not just this failed-login path).
# python
# from lrb.core.constants import LOCKOUT_DURATION_MINUTES, MAX_FAILED_ATTEMPTS
# lrb.core.constants — a shared module holding project-wide fixed values. MAX_FAILED_ATTEMPTS and LOCKOUT_DURATION_MINUTES are almost certainly plain integers (e.g. MAX_FAILED_ATTEMPTS = 5).
# Why pull these from a shared constants module instead of typing 5 and 30 directly in this file? Two reasons: (1) if a config value like "5 failed attempts" is scattered as a raw number across multiple files, changing the policy means hunting down every occurrence — one shared constant means one place to edit; (2) a bare 5 in code is a magic number — meaningless without context. MAX_FAILED_ATTEMPTS is self-explanatory the moment you read it, no comment needed.
# 3. Signature
# python
# def handle_failed_login(*, user):
# Same pattern as every service function you've shown me: * forces user to be passed as a keyword — handle_failed_login(user=some_user), never positionally.
# user has no type hint here (unlike email: str in earlier files). This is a minor inconsistency again — you'd expect something like user: "accounts.User". Worth noting as you build your eye for auditing consistency, but not a bug.
# No -> None return hint either. This function never returns a meaningful value (it always falls off the end, which in Python implicitly returns None) — adding -> None would be accurate and match the "type hints everywhere" convention, but its absence doesn't break anything.
# 4. Body — step by step
# python
#     if not user:
#         return
# Guards against being called with user=None. not user — same falsy-check pattern you saw in authenticate_credentials.
# Bare return (no value) — exits the function immediately, doing nothing. This makes the function safe to call defensively — e.g., a caller might do handle_failed_login(user=authenticate_result) right after a failed login attempt where authenticate_result could itself be None (remember: django_authenticate returns None on failure). Rather than making every caller check if user: handle_failed_login(...), the function absorbs that check itself.
# python
#     user.failed_login_attempts += 1
# += is Python's augmented assignment operator — shorthand for user.failed_login_attempts = user.failed_login_attempts + 1. It reads the current value, adds one, and writes it back to the same attribute.
# This only changes the value in memory, on this Python object — nothing is saved to the database yet.
# python
#     user.save(update_fields=["failed_login_attempts"])
# .save() is a Django Model method that writes the object's current in-memory state to the database.
# update_fields=[...] — same pattern you saw in _set_new_password: tells Django to generate an UPDATE statement touching only the failed_login_attempts column, not every field on the model. This matters here specifically: without it, a full save could overwrite other fields on user that might have been changed elsewhere in the same request but not yet persisted — restricting to update_fields makes this function's effect precise and safe to call without worrying about side effects on unrelated columns.
# python
#     if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
#         lock_user(user_id=user.id, duration_minutes=LOCKOUT_DURATION_MINUTES)
# >= — "greater than or equal to." Using >= rather than == is a deliberate defensive choice: if attempts somehow jump past the threshold in one step (e.g., a race condition — two failed logins processed close together), == could miss the exact number and never trigger the lock. >= guarantees the lockout fires at or beyond the threshold, no matter what.
# If the condition is true, calls the imported lock_user service, passing user.id (not the whole user object — notice lock_user only needs the primary key, a slightly different, more decoupled interface than functions that take the full object) and the configured duration.
# 5. Why this approach
# Delegating the actual locking to a separate lock_user service keeps this function focused on one job — "count this failure, decide if it's time to lock" — while the mechanics of locking (setting locked_until, maybe sending a notification email, maybe logging a security event) live in one place other callers can reuse.
# update_fields on the counter save avoids a subtle real-world bug class: if this function runs concurrently with some other part of the request that's also modifying user but hasn't saved yet, an unrestricted .save() here could silently overwrite those other in-memory changes when they eventually get written — restricting the fields saved narrows the blast radius.
# The early if not user: return guard means this function can safely sit right after any authentication attempt without extra if checks cluttering the caller's code.
# 6. Connections
# Input: a User object (or None) — the natural next step after authenticate_credentials returns None/raises. A typical GraphQL login mutation would do something like:
# python
#   user = django_authenticate(email=email, password=password)
#   if not user:
#       failed_user = User.objects.filter(email=email).first()
#       handle_failed_login(user=failed_user)
#       raise ApplicationError(...)

# (Notice: since django_authenticate returns None on failure, you can't get the specific user from it directly — the caller has to look the user up separately by email to know whose counter to increment. This function's if not user: return guard exists precisely because that lookup might also come back empty, e.g., if the email doesn't exist at all.)

# Output: none returned; its effect is entirely through database writes (user.save(...)) and the side-effect call to lock_user.
# Downstream: lock_user presumably sets user.locked_until to some future timestamp — the exact field you saw _set_new_password reset to None on a successful password change, confirming these two files are part of the same account-security feature.
# 7. Is it correct?

# Functionally, yes — no crashing bugs like the last two files. But there's one thing worth flagging against your project's own convention:

# Missing @transaction.atomic. This function performs two separate write operations: user.save(...) and (conditionally) lock_user(...), which itself very likely does its own .save() or .update(). Your stated rule is @transaction.atomic on all write services. Right now, if the process crashes or the database connection drops between the counter save and the lock_user call, you could end up with failed_login_attempts incremented past the threshold but the account never actually locked — a real (if narrow) security gap. Wrapping the whole function:

# python
# @transaction.atomic
# def handle_failed_login(*, user):
#     ...

# would guarantee both writes commit together or neither does, matching how you handled the corrected change_password/set_password_unchecked functions.

# 8. Small example
# python
# @transaction.atomic
# def record_strike(*, player):
#     if not player:
#         return
#     player.strikes += 1
#     player.save(update_fields=["strikes"])
#     if player.strikes >= MAX_STRIKES:
#         eject_player(player_id=player.id)

# Same shape: guard clause, increment, targeted save, threshold check, delegate the consequence to another function — now wrapped atomically.

# 9. What to remember
# += reads-then-writes the same attribute — it only changes an in-memory object until .save() (or the DB equivalent) actually persists it.
# Prefer >= over == when checking a counter against a threshold — protects against skipped or concurrent increments.
# A guard clause (if not X: return) at the top of a function is a common way to make a function safe to call unconditionally, pushing null-checks into one place instead of every call site.
# update_fields isn't just an optimization — it's a safety boundary that limits what a .save() call can accidentally overwrite.
# When auditing real code, check for missing project conventions, not just outright bugs — this function doesn't crash, but it silently skips the @transaction.atomic rule your project applies to every other write service you've shown me, which is exactly the kind of drift you said you want caught.