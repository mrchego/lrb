from django.db import transaction

from lrb.accounts.selectors.get_user_by_email import get_user_by_email
from lrb.core.exceptions import AppValidationError
from lrb.identity.models import VerificationCode
from lrb.identity.services.verify_code import verify_code


@transaction.atomic
def verify_email(*, email:str, code:str):
    user = get_user_by_email(email=email)
    if not user:
        raise AppValidationError(message="Invalid email or code.", field="code")
    verify_code(user=user, code=code, purpose=VerificationCode.Purpose.EMAIL_VERIFICATION)
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    return user


# 1. Purpose

# This is verify_email — the completion function for the email-verification flow, structurally the exact mirror of reset_password: look up the user, verify the OTP code, then apply the actual effect (here, flipping is_email_verified to True instead of changing a password). This is what a verifyEmail GraphQL mutation calls directly, closing out the second full feature you've traced today.

# Good news: this file gets right the exact bug that was in reset_password. Let's confirm that, then look at one genuine design question worth thinking through.

# 2. Signature
# python
# def verify_email(*, email:str, code:str):

# Same shape as always: * forces both parameters keyword-only. Same small formatting slip you already spotted in forgot_password — email:str and code:str are missing the space after the colon that Django/Python style conventions (and tools like black) expect (email: str). Cosmetic, not a bug, but you should now recognize this as a recurring tell across a few files in this codebase that autoformatting isn't being run consistently.

# 3. Body — step by step
# python
#     user = get_user_by_email(email=email)
#     if not user:
#         raise AppValidationError(message="Invalid email or code.", field="code")

# This is the fix you wrote for reset_password, done correctly here from the start. Compare directly:

# 	reset_password (original bug)	verify_email (this file)
# Exception class on "no user"	ApplicationError	AppValidationError
# Exception class on "bad code" (from verify_code)	AppValidationError	AppValidationError
# Match?	❌ different classes	✅ same class

# By raising AppValidationError here — the same class verify_code itself raises for a wrong/expired/missing code — "no such user" and "wrong code" are indistinguishable at the exception-type level, exactly the property reset_password was missing. This is good evidence that you now genuinely understand the bug you found earlier, since you can independently verify it's absent here without me pointing it out first.

# (One very minor nuance: the message text itself — "Invalid email or code." vs. verify_code's "Incorrect verification code." — isn't byte-for-byte identical. This is a much smaller concern than a mismatched exception type, since both messages equally imply "something about the code was wrong" without confirming which. Worth knowing the distinction exists, not worth losing sleep over.)

# python
#     verify_code(user=user, code=code, purpose=VerificationCode.Purpose.EMAIL_VERIFICATION)

# Same call shape you've now seen twice — correct keyword arguments, correct enum member.

# python
#     user.is_email_verified = True
#     user.save(update_fields=["is_email_verified"])
#     return user

# Sets the flag, saves only that column (the update_fields pattern you've now seen in nearly every write in this codebase), and returns the full User object.

# 4. A genuine design question: should this return user?

# Every other "action" function you've reviewed today (send_password_reset_code, send_email_verification_code, request_email_verification, reset_password) deliberately returns a bare True — you learned why: never leak more than the caller needs, especially anything sensitive. This function breaks that pattern and returns the whole User object.

# Is that a bug? Almost certainly not — it's a legitimate, different requirement. Think about what a resolver needs after this succeeds: verifying your email is often the moment an app wants to automatically log you in, or at least return your updated profile (is_email_verified: true) to the frontend so the UI updates immediately without a second query. reset_password doesn't have that need — after resetting a password, the sensible UX is "now log in with your new password," not "you're automatically logged in." verify_email plausibly does need to hand the caller a real User object to build a session from.

# This is worth internalizing as a general principle, not just a one-off note: "return the minimum necessary" doesn't mean "always return True" — it means think about what the very next step actually requires, and return exactly that, no more. Here, the User object is likely genuinely necessary; in reset_password, the OTP code was not.

# 5. Connections
# request_email_verification(email)
#   → send_email_verification_code(user)
#     → generate_verification_code(user, EMAIL_VERIFICATION)

# verify_email(email, code)
#   → get_user_by_email(email)
#   → verify_code(user, code, EMAIL_VERIFICATION)
#   → sets is_email_verified=True
#   → returns user (likely used to establish a session)

# You've now read this feature's complete round trip, matching the password-reset round trip exactly in structure.

# 6. What to remember
# You correctly identified, without help, that this file avoids the exact bug you found in reset_password — that's the real marker that the lesson landed, not just the fix.
# "Minimize what you return" is a judgment call based on what the caller genuinely needs next, not a blanket rule — returning a full object is right when the next step requires it (building a session here), wrong when it isn't (the OTP code in the reset flow).
# Comparing two structurally identical functions side by side remains your best tool for catching subtle divergence — you've now used this technique successfully across forgot_password/request_email_verification and reset_password/verify_email.
# Exception type matching matters as much as message-text matching for security symmetry — and small message wording differences are a much lower-severity concern once the type already matches.
# You've now completed a full, real, end-to-end audit of two parallel authentication features — password reset and email verification — built on the same OTP infrastructure, and independently caught the same class of bug appearing in different shapes across both. That's the actual skill this whole series was training: not memorizing this codebase, but building the instinct to ask "what happens on every path, not just the one that looks intended" — on any code you read next.