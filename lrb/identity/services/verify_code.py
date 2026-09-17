import hmac

from django.db import transaction
from django.utils import timezone

from lrb.core.exceptions import AppValidationError
from lrb.identity.models import VerificationCode


@transaction.atomic
def verify_code(*, user, code, purpose):
    verification_code = (
        VerificationCode.objects.select_for_update().filter(
            user=user, purpose=purpose, used_at__isnull=True
        )
        .order_by("-created_at")
        .first()
    )
    if not verification_code:
        raise AppValidationError(
            message="No active verification code found. Request a new one.",
            field="code",
        )

    if verification_code.is_expired:
        raise AppValidationError(
            message="This code has expired. Request a new one.", field="code"
        )

    if not hmac.compare_digest(verification_code.code, code):
        raise AppValidationError(message="Incorrect verification code.", field="code")

    verification_code.used_at = timezone.now()
    verification_code.save(update_fields=["used_at"])
    return True


# Spotting a missing brute-force safeguard on code attempts.
# 1. Purpose
# This is the function you predicted two files ago: verify_code — the other half of the OTP system. Given a user, a submitted code, and a purpose, it checks whether that code is currently valid, and if so, marks it as used. This is what a "confirm my email" or "submit reset code" mutation calls, right before letting the user set a new password or marking their email verified.

# No crashing bugs. The logic is sound. This is a good file to read for its security reasoning, since it's the most security-sensitive function you've seen yet — it's the one actually checking a secret against user input.

# 2. Imports — one you haven't seen before
# python
# import hmac
# hmac is a Python standard library module (not Django) for cryptographic comparison and message authentication. You already saw it referenced in your own project notes (hmac.compare_digest), and here's where it's actually used.
# 3. Signature
# python
# @transaction.atomic
# def verify_code(*, user, code, purpose):
# Familiar shape: @transaction.atomic since this function both reads and writes; * forcing all three parameters to be keyword-only. No type hints — same recurring gap you've now flagged consistently across this codebase.

# 4. Body — step by step
# python
#     verification_code = (
#         VerificationCode.objects.filter(
#             user=user, purpose=purpose, used_at__isnull=True
#         )
#         .order_by("-created_at")
#         .first()
#     )
# Same used_at__isnull=True filter pattern from generate_verification_code — "find currently-active codes for this user+purpose." This is the exact query your composite index (user, purpose, used_at) was built to speed up.
# .order_by("-created_at") — since generate_verification_code invalidates old codes before creating a new one, there should only ever be one active code at a time. But recall the race condition you learned about earlier — two near-simultaneous generation requests could momentarily leave two active codes. .order_by("-created_at") defensively picks the newest one in that edge case, which is the correct choice — always trust the most recently issued code.
# .first() — Django queryset method: run the query, return the first matching row as an object, or None if there are no matches. This is different from indexing ([0]), which would raise an error on an empty result — .first() handles "no rows" gracefully by returning None instead of crashing.
# The whole expression is wrapped in (...) across multiple lines — parentheses here aren't a function call, they're just letting Python continue an expression across multiple lines for readability, chaining .filter() → .order_by() → .first() one per line instead of one long line.
# python
#     if not verification_code:
#         raise AppValidationError(
#             message="No active verification code found. Request a new one.",
#             field="code",
#         )
# Standard falsy-check-then-raise pattern you've now seen many times — verification_code is None if the query found nothing.

# python
#     if verification_code.is_expired:
#         raise AppValidationError(
#             message="This code has expired. Request a new one.", field="code"
#         )
# Uses the @property you read in the very first file of this conversation — is_expired computes timezone.now() >= self.expires_at fresh, every time it's accessed. This is the payoff of that design choice: no risk of a stale "is expired" flag, since it's always calculated live.

# python
#     if not hmac.compare_digest(verification_code.code, code):
#         raise AppValidationError(message="Incorrect verification code.", field="code")
# This is the most important line in the whole file, and it's written correctly. Let's unpack why it's not just verification_code.code != code:

# hmac.compare_digest(a, b) compares two strings (or byte strings) in constant time — meaning it takes the same amount of time to run regardless of how many characters match before the first difference. A normal == comparison in most languages stops checking the moment it finds a mismatched character, which means comparing "123456" to "199999" (fails at position 2) is measurably faster than comparing it to "123450" (fails at position 6, closer to a match).
# Why that tiny timing difference matters: an attacker measuring response times very precisely, guess by guess, could theoretically narrow down the correct code one digit at a time — a real attack class called a timing attack. hmac.compare_digest exists specifically to eliminate that signal by always taking the same time, no matter where (or whether) the strings differ.
# This is the same security instinct you saw in django_authenticate (which does the analogous thing for passwords internally) — now you're seeing the explicit, visible version of that same principle, because this project rolled its own OTP system rather than using a library that hides this detail.
# python
#     verification_code.used_at = timezone.now()
#     verification_code.save(update_fields=["used_at"])
#     return True
# Marks this specific code as used (so it can never be verified again — used_at__isnull=True in future queries will now correctly exclude it) and returns True. Same deliberate "return a plain success signal, not the object" pattern from the send functions — though here, returning the object would be less of a security concern; it's more just consistency with the rest of this codebase's style.

# 5. Two real gaps worth understanding (not crashes — design considerations)
# A. No brute-force protection on the guess itself. Your project notes describe a 6-digit code — that's 1,000,000 possible values. hmac.compare_digest protects against timing attacks, but there's nothing here stopping someone from simply submitting many different 6-digit guesses in a row within the code's expiry window (5 minutes, per your project notes). Compare this to the login flow, which has handle_failed_login explicitly counting failures and locking the account after MAX_FAILED_ATTEMPTS. This function has no equivalent — no attempt counter, no lockout, no rate limit. In a learning project this may be an acceptable simplification, but in a production system, brute-forcing a 6-digit code within a 5-minute window (with no rate limit) is a realistic attack, not just a theoretical one. This would likely need to live one layer up — in whatever mutation calls verify_code — tracking failed verification attempts the same way login tracks failed password attempts.

# B. A subtler concurrency race than the one you saw before. @transaction.atomic guarantees this function's own writes commit together — but it does not, by itself, stop two simultaneous calls to verify_code from both reading the same still-unused verification_code row before either has committed its update. Picture two requests arriving at nearly the same instant, both submitting the correct code: both could run the .filter(...).first() query, both see used_at IS NULL, both pass every check, and both proceed to set used_at and save — meaning the same code gets successfully "used" twice. For a password reset flow, that could mean two different downstream password-reset attempts both believe they're authorized. The fix is the same tool mentioned in an earlier file: adding .select_for_update() to the query would lock that row for the duration of the transaction, forcing the second concurrent request to wait until the first one finishes (and by then, used_at is already set, so the second correctly gets rejected):

# python
# verification_code = (
#     VerificationCode.objects.select_for_update()
#     .filter(user=user, purpose=purpose, used_at__isnull=True)
#     .order_by("-created_at")
#     .first()
# )
# 6. Connections
# Completes the OTP lifecycle: generate_verification_code (create) → send_password_reset_code / send_email_verification_code (deliver) → verify_code (consume). You've now read every stage of this feature's data lifecycle.
# Caller: a resetPassword or verifyEmail GraphQL mutation — likely calling verify_code(...) first, and only on success proceeding to call set_password_unchecked (from the file you corrected earlier) or setting is_email_verified = True.
# 7. What to remember
# hmac.compare_digest is for comparing secrets, not == — reach for it any time you're checking a user-submitted value against something sensitive (codes, tokens, signatures), because == leaks timing information compare_digest doesn't.
# .first() on a queryset returns None on no match instead of raising — safer than indexing ([0]) when a query might legitimately return nothing.
# @transaction.atomic prevents partial writes, but doesn't prevent two concurrent requests from reading the same "before" state — that's what .select_for_update() is for, and the two solve genuinely different problems.
# A security feature applied in one place (login lockout) doesn't automatically protect a different, similarly-sensitive place (OTP guessing) — each entry point that accepts a guessable secret needs its own explicit protection.
# You now have the full picture of a production-realistic authentication system: password auth with lockout, OTP-based reset/verification with constant-time comparison, and the specific concurrency and enumeration pitfalls that show up in each. That's a genuinely strong foundation — the pattern-recognition you're using to spot these issues yourself is exactly the skill this whole exercise was building toward.