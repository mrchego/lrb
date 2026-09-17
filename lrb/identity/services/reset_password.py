from django.db import transaction

from lrb.accounts.selectors.get_user_by_email import get_user_by_email
from lrb.core.exceptions import AppValidationError, ApplicationError, ErrorCode
from lrb.identity.models import VerificationCode
from lrb.identity.services.change_password import set_password_unchecked
from lrb.identity.services.verify_code import verify_code


@transaction.atomic
def reset_password(*, email: str, code: str, new_password: str):
    user = get_user_by_email(email=email)
    if not user:
        raise AppValidationError(
            message="Invalid email or code.", field="code"
        )
    verify_code(user=user, code=code, purpose=VerificationCode.Purpose.PASSWORD_RESET)
    set_password_unchecked(user=user, new_password=new_password)
    return True


# 1. Purpose

# This is the final piece: reset_password — the function that actually completes the password-reset flow. Given an email, a submitted OTP code, and a new password, it verifies the user exists, verifies the code is valid (delegating to verify_code, which you just fully audited), and if both pass, sets the new password (via set_password_unchecked, which you corrected earlier). This is what a resetPassword GraphQL mutation calls directly — the mirror image of forgot_password, completing the round trip you started several files ago.

# There's one real bug here, and it's the enumeration bug again — in a new, subtler shape.

# 2. Imports

# All familiar at this point except one new detail worth naming: set_password_unchecked and verify_code are both imported and both already decorated with @transaction.atomic themselves (you confirmed this in earlier files). This file's own function is also decorated with @transaction.atomic. That's not a mistake — it's worth understanding why it's safe, covered below.

# 3. Signature
# python
# @transaction.atomic
# def reset_password(*, email: str, code: str, new_password: str):

# Standard shape: * forces all three parameters keyword-only. No return type hint (-> bool would match the pattern, and is missing here just like everywhere else in this codebase).

# 4. Body — step by step
# python
#     user = get_user_by_email(email=email)
#     if not user:
#         raise ApplicationError(
#             message="Invalid email or code.", code=ErrorCode.INVALID_TOKEN
#         )

# Looks deliberately vague on the surface — "Invalid email or code" sounds like it's trying to avoid confirming whether the email exists, similar in spirit to authenticate_credentials's "Invalid email or password". But keep reading.

# python
#     verify_code(user=user, code=code, purpose=VerificationCode.Purpose.PASSWORD_RESET)

# If user exists, control reaches here. Recall exactly what verify_code can raise if the code is wrong, missing, or expired:

# python
# raise AppValidationError(message="No active verification code found. Request a new one.", field="code")
# raise AppValidationError(message="This code has expired. Request a new one.", field="code")
# raise AppValidationError(message="Incorrect verification code.", field="code")
# python
#     set_password_unchecked(user=user, new_password=new_password)
#     return True

# Only reached if both checks pass — sets the password (using the fix you already applied to _set_new_password), returns True.

# 5. The bug: two different failure paths are distinguishable

# Line up every possible failure this function can produce:

# Situation	Exception type	Message
# Email doesn't match any user	ApplicationError	"Invalid email or code."
# Email matches, but no active code exists	AppValidationError	"No active verification code found. Request a new one."
# Email matches, but code is expired	AppValidationError	"This code has expired. Request a new one."
# Email matches, but code is wrong	AppValidationError	"Incorrect verification code."

# The "no user found" case is a different exception class with a different message from every "user exists, code problem" case. Even if a GraphQL layer displayed all of these as generic-looking error text to a human, most GraphQL error-formatting code distinguishes exceptions by type (e.g., except ApplicationError vs except AppValidationError mapping to different error codes, HTTP behavior, or logging) — meaning this distinction is very likely to leak through to the response even if no developer intended it to. An attacker submitting reset_password requests with a fixed fake code across many email addresses can now tell, from the shape of the response alone, exactly which emails are registered — the same enumeration flaw you already fixed in forgot_password, resurfacing here through exception type rather than a True/None return value.

# This is the deeper lesson: you fixed the return-value version of this bug in forgot_password. This file shows the same underlying mistake wearing different clothes — through exception type and message, not return value. Once you understand the principle ("don't let success and failure paths diverge on anything an attacker could observe"), you should be checking for it in every shape it can take, not just the one you've already seen.

# The fix

# Make the "user not found" case raise the exact same exception type, message, and field as the most generic code-failure case:

# python
# @transaction.atomic
# def reset_password(*, email: str, code: str, new_password: str):
#     user = get_user_by_email(email=email)
#     if not user:
#         raise AppValidationError(
#             message="Incorrect verification code.", field="code"
#         )
#     verify_code(user=user, code=code, purpose=VerificationCode.Purpose.PASSWORD_RESET)
#     set_password_unchecked(user=user, new_password=new_password)
#     return True

# Now "no such email" and "wrong code for a real email" are completely indistinguishable from outside — same exception class, same message, same field. (The "expired code" and "no active code" messages inside verify_code still technically confirm a real user has requested a reset before — a much narrower, lower-value leak than confirming account existence outright. If you wanted to close that too, verify_code would need to collapse all of its failure messages into one generic one as well — a judgment call depending on how much you value debuggability for legitimate users vs. airtight secrecy.)

# 6. Why this happens, and how to catch it yourself next time

# The failure mode here isn't "forgot a check" — it's "wrote each error case in isolation, using whatever message/type felt locally appropriate, without stepping back to compare all the failure paths side by side." That comparison — listing every way a function can fail, in a table, like the one above — is the actual technique for catching this class of bug. It's slower than reading top-to-bottom, but it's the only way this kind of leak becomes visible, because no single line of the function looks wrong in isolation.

# 7. What's correct here
# Nested @transaction.atomic: reset_password is atomic, and it calls two functions (verify_code, set_password_unchecked) that are also independently atomic. Django handles this safely using savepoints — when an already-atomic block starts another atomic block inside it, Django doesn't open a second real transaction; it creates a savepoint (a rollback point within the same transaction). If the inner block fails, Django rolls back just to that savepoint rather than the very start — but since the outer function immediately re-raises on any failure anyway, the practical effect here is the same: any failure anywhere rolls back the entire operation (code verification and password change happen together, or neither happens). This is exactly right: you never want a state where a code got marked "used" but the password change failed, or vice versa.
# Calling verify_code before set_password_unchecked, not after: correct ordering — never change the password before confirming the code is genuinely valid.
# Using set_password_unchecked (not change_password): correct choice — the whole point of this flow is that the user doesn't know their current password (that's why they're resetting it); requiring it here would be a contradiction. Authorization instead comes from proving control of the OTP code.
# 8. Connections

# This function is the true endpoint of the entire password-reset feature you've now read start to finish:

# forgot_password(email)
#   → send_password_reset_code(user)
#     → generate_verification_code(user, PASSWORD_RESET)   [writes VerificationCode]

# reset_password(email, code, new_password)
#   → get_user_by_email(email)
#   → verify_code(user, code, PASSWORD_RESET)               [reads + marks used]
#   → set_password_unchecked(user, new_password)            [writes new password]

# Every function in that chain, you've now personally audited — and found (and fixed) a real bug in nearly every layer.

# 9. What to remember
# The same security bug can reappear in a different disguise — you fixed enumeration-via-return-value in forgot_password; here it was enumeration-via-exception-type. Learn the principle, not just the one fix.
# List every failure path a function has, side by side, before trusting any single one of them — bugs like this are invisible reading top-to-bottom but obvious in a table.
# Two different exception classes are themselves an observable signal, even before you look at the message text — matching exception type matters as much as matching wording.
# Nested @transaction.atomic calls are safe in Django — they use savepoints, and the outermost failure still rolls everything back together.
# You've now completed a full security audit of an entire real-world authentication feature — login with lockout, password reset with OTP, email verification — catching a crash bug, a fragile-signature bug, and three separate instances of the same enumeration flaw across different files. That pattern-matching instinct — recognizing the same class of mistake in unfamiliar code — is the actual milestone this whole exercise was building toward.