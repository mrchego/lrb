from django.db import transaction
from django.utils import timezone

from lrb.core.constants import (
    VERIFICATION_CODE_EXPIRY_MINUTES,
    VERIFICATION_CODE_LENGTH,
)
from lrb.core.utilis.strings import generate_numeric_code
from lrb.identity.models import VerificationCode


@transaction.atomic
def generate_verification_code(*, user, purpose):
    VerificationCode.objects.filter(
        user=user, purpose=purpose, used_at__isnull=True
    ).update(used_at=timezone.now())
    code = generate_numeric_code(length=VERIFICATION_CODE_LENGTH)
    return VerificationCode.objects.create(
        user=user,
        purpose=purpose,
        code=code,
        expires_at=timezone.now()
        + timezone.timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES),
    )


# 1. Purpose

# This service function generates a fresh OTP verification code for a user (for either email verification or password reset — the purpose you defined back in the VerificationCode.Purpose enum). Before creating the new code, it invalidates any old, still-unused codes for that same user+purpose combination, so a user can never have two "active" codes floating around at once — this is exactly the model+behavior pairing your VerificationCode model was built for, right down to using the composite index (user, purpose, used_at) you defined in its Meta class.

# 2. Imports — explained from scratch, plus one to double-check
# python
# from lrb.core.utilis.strings import generate_numeric_code
# Worth a flag: the path is lrb.core.utilis.strings — that middle segment reads like a typo of utils (missing the "l," has an extra "i": u-tilis vs u-tils). This isn't necessarily a bug — if that's genuinely the real folder name elsewhere in your project, this import will work fine. But if the actual folder is named utils and this line has a stray typo, Python will raise ModuleNotFoundError: No module named 'lrb.core.utilis' the moment this file is imported. Worth a 10-second check against your actual folder structure — this is the kind of thing that's easy to miss reading code on a screen, since utilis and utils look nearly identical at a glance.

# The rest of the imports follow patterns you already know: transaction for atomicity, timezone for safe current-time handling, VERIFICATION_CODE_EXPIRY_MINUTES/VERIFICATION_CODE_LENGTH as named constants (same reasoning as MAX_FAILED_ATTEMPTS last time — no magic numbers), and VerificationCode — the model you already fully broke down two files ago.

# 3. Signature
# python
# @transaction.atomic
# def generate_verification_code(*, user, purpose):
# @transaction.atomic sits directly above the function, decorating it. This function performs two separate database operations (a bulk update, then a create) — atomic wrapping guarantees they both succeed or both roll back together. If step two failed after step one succeeded, you could end up invalidating a user's working code without ever creating a replacement — locking them out. Correctly applied here, matching your project's "atomic on all writes" rule (and fixing the exact gap I flagged in the previous handle_failed_login file).
# * — forces user and purpose to be keyword-only, consistent with every other service function you've shown me.
# user and purpose — no type hints, and the function itself has no -> VerificationCode return hint either. Small, recurring drift from the "type hints everywhere" convention — not a bug, but worth noting as a pattern across this codebase: type hints seem to appear more consistently on model methods (is_expired -> bool) than on service functions. Something to raise if you're doing a consistency pass.
# 4. Body — step by step
# python
#     VerificationCode.objects.filter(
#         user=user, purpose=purpose, used_at__isnull=True
#     ).update(used_at=timezone.now())
# VerificationCode.objects — every Django model gets a .objects manager, your entry point for querying that model's table.
# .filter(user=user, purpose=purpose, used_at__isnull=True) — builds a query: "rows where user matches, purpose matches, AND used_at is NULL." used_at__isnull=True is Django's syntax for IS NULL — the double underscore (__) separates the field name (used_at) from a lookup type (isnull). This finds exactly the "currently active, unused" codes — notice this is the exact three columns your composite index was built for, so this query is fast.
# .update(used_at=timezone.now()) — this is a bulk update: it runs a single UPDATE ... WHERE ... SQL statement directly, changing every matching row's used_at to right now, all at once, without loading them into Python objects first.
# Effect: "mark any old, still-active codes as used" — invalidating them, using the same used_at-as-a-flag pattern from the model (is_used becomes True the instant used_at is set).
# Worth knowing: .update() bypasses each row's .save() method and any model signals — it talks straight to the database. That's fine here (there's no custom .save() logic on VerificationCode to skip), but it's a distinction worth remembering: .update() on a queryset is not the same operation as calling .save() on an individual object.
# python
#     code = generate_numeric_code(length=VERIFICATION_CODE_LENGTH)
# Calls your imported helper to produce the actual code string (e.g., a random 6-digit number, per your project notes), storing it in the local variable code.
# python
#     return VerificationCode.objects.create(
#         user=user,
#         purpose=purpose,
#         code=code,
#         expires_at=timezone.now()
#         + timezone.timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES),
#     )
# .objects.create(...) — builds and saves a new row in one step (shorthand for VerificationCode(...) then .save()).
# timezone.now() + timezone.timedelta(minutes=...) — computes "now, plus N minutes" to get the expiry timestamp. + here is Python's operator working on datetime/timedelta objects — adding a duration to a point in time gives you a new, later point in time.
# A subtlety on timezone.timedelta: this works, but it's leaning on an implementation detail. timedelta is not actually part of django.utils.timezone's intended public API — it's accessible as timezone.timedelta only because Django's timezone.py happens to do from datetime import timedelta near its own top, which makes timedelta incidentally reachable as an attribute of the timezone module. It works today, but the more standard, explicit way (and what you'll see in most Django codebases) is:
# python
#   from datetime import timedelta
#   ...
#   expires_at=timezone.now() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)

# Not a bug — just fragile style, relying on something that isn't guaranteed to stay true if Django's internals ever change.

# The whole VerificationCode.objects.create(...) expression is directly returned — the function hands back the newly-created VerificationCode object (row) to the caller.
# 5. Why this approach
# Invalidate-then-create, in one atomic block: enforces "only one active code per user+purpose" as an actual guarantee, not just a hopeful convention — because it's wrapped in @transaction.atomic, no other part of the app can ever see a half-finished state (old code invalidated but no new one yet, or vice versa).
# Bulk .update() instead of loading and saving each old code individually: if a user somehow has multiple stale unused codes, one UPDATE statement handles all of them in a single database round-trip — much more efficient than fetching each into Python and calling .save() in a loop.
# Returning the created object: lets the caller (likely a GraphQL mutation) immediately access code.code to email it to the user, or code.expires_at to include in a response — no second database query needed.
# 6. Connections
# Direct callback to the VerificationCode model file: this function is the thing that populates the table you broke down earlier — it's the write-side counterpart to that model's read-side is_expired/is_used properties.
# Downstream verification service: somewhere else in the codebase, a verify_code(*, user, purpose, submitted_code) function likely does the reverse — looks up the most recent unused code and checks it with hmac.compare_digest (per your project notes), checking not code.is_expired and not code.is_used before accepting it.
# Callers: the "resend verification email" and "request password reset" GraphQL mutations both likely call this exact function — same generation logic, different purpose value.
# 7. Advanced concepts

# Race condition worth knowing about (not necessarily fixing): if two requests to generate a code for the same user arrive at the exact same moment, both could run the filter().update() step before either has created its new row — both see "no active codes to invalidate," both proceed to create one. Result: two simultaneously-active codes exist briefly, technically violating the "only one active code" intent. @transaction.atomic protects against partial failure, but doesn't by itself prevent two concurrent transactions from interleaving like this (it would take an additional select_for_update() lock to fully close that gap). This is a genuinely advanced, low-probability edge case — worth knowing exists, not necessarily worth losing sleep over in a learning project.

# Bulk .update() vs individual .save(): this is a common Django performance pattern. When you need to change the same field on many rows to the same value, and don't need any per-object .save() side effects (custom validation, signals), .update() on a queryset is dramatically more efficient — one SQL statement instead of N.

# 8. Small example
# python
# @transaction.atomic
# def issue_ticket(*, event, attendee):
#     Ticket.objects.filter(attendee=attendee, event=event, used_at__isnull=True).update(
#         used_at=timezone.now()
#     )
#     return Ticket.objects.create(
#         attendee=attendee,
#         event=event,
#         expires_at=timezone.now() + timedelta(hours=24),
#     )

# Same shape: invalidate old active rows in bulk, then atomically create the new one, all wrapped together.

# 9. What to remember
# field__lookup=value (double underscore) is Django's syntax for query conditions beyond plain equality — used_at__isnull=True means WHERE used_at IS NULL.
# .update() on a queryset is a direct, bulk SQL UPDATE — faster than looping and calling .save(), but it skips each object's own .save() logic and signals.
# @transaction.atomic matters most exactly when a function does more than one database write — this function is a textbook case: invalidate, then create, both-or-nothing.
# Watch for accidental reliance on "it happens to work" behavior — timezone.timedelta runs today, but from datetime import timedelta is the explicit, intended way to get it; don't lean on a module's internal imports as if they were its real public API.
# A single-letter typo in an import path (utilis vs utils) can be invisible at a glance — when auditing real code, actually check import paths against the real folder structure rather than assuming they're right because the code "looks" plausible.