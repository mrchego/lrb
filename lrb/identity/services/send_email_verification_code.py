from django.template.loader import render_to_string

from lrb.core.constants import VERIFICATION_CODE_EXPIRY_MINUTES
from lrb.core.tasks import send_email_task
from lrb.identity.models import VerificationCode
from lrb.identity.services.generate_verification_code import generate_verification_code


def send_email_verification_code(*, user):
    verification_code = generate_verification_code(
        user=user, purpose=VerificationCode.Purpose.EMAIL_VERIFICATION
    )
    message = render_to_string(
        "identity/verification_code_email.txt",
        {
            "code": verification_code.code,
            "minutes": VERIFICATION_CODE_EXPIRY_MINUTES,
            "purpose_label": VerificationCode.Purpose.EMAIL_VERIFICATION.label,
        },
    )
    send_email_task.delay(
        subject="Your verification code",
        message=message,
        recipient_list=[user.email],
    )
    return True


# 1. Purpose

# This is the email-verification twin of send_password_reset_code — nearly line-for-line identical, just swapped to Purpose.EMAIL_VERIFICATION and a different email subject. You already understand every piece of this file from two files ago. Rather than re-explain syntax you've already mastered, this is the right moment to do two things: (1) confirm it's correct, and (2) look at why near-duplicate files like this are a real design signal worth noticing.

# 2. Is it correct?

# Yes — no bugs. Let's verify the parts that mattered last time:

# generate_verification_code(user=user, purpose=VerificationCode.Purpose.EMAIL_VERIFICATION) — correct keyword usage, correct enum member.
# send_email_task.delay(...) — same background-task pattern, correctly not blocking the request.
# return True — same deliberate security boundary as before: never echoes verification_code.code back to the caller.
# No @transaction.atomic — correct, for the same reason as last time: the only database write already happened and committed inside generate_verification_code; queuing the email afterward avoids the on-commit race you learned about.
# 3. One thing worth noticing: this file actually does something better than its sibling
# python
# "purpose_label": VerificationCode.Purpose.EMAIL_VERIFICATION.label,

# Compare this to send_password_reset_code, which had:

# python
# "purpose_label": "password reset",   # hardcoded string

# This file does exactly what I suggested as an improvement back then: it pulls the human-readable label from the enum itself — .label — rather than retyping it as a raw string. This confirms .label is genuinely available and works as expected on a TextChoices member (EMAIL_VERIFICATION.label → "Email Verification", the second value you defined back in the model file), which is worth remembering as a small but useful fact about Django's TextChoices.

# The takeaway isn't "this file is right and the other is wrong" — it's that you now have direct evidence of an inconsistency between two sibling files that do the same job two different ways. That's exactly the kind of drift-catching your project conventions ask for: go back and update send_password_reset_code to use VerificationCode.Purpose.PASSWORD_RESET.label too, so both files derive the label the same way instead of one hardcoding it.

# 4. Advanced concept: should these two files even both exist?

# Look at what's actually different between send_password_reset_code and send_email_verification_code:

# 	send_password_reset_code	send_email_verification_code
# purpose	PASSWORD_RESET	EMAIL_VERIFICATION
# subject	"Your password reset code"	"Your verification code"
# everything else	identical	identical

# This is a classic case where two functions share ~90% of their body. A common refactor — worth understanding even if you don't apply it yet — is to extract the shared logic into one private helper both public functions call:

# python
# def _send_verification_email(*, user, purpose, subject):
#     verification_code = generate_verification_code(user=user, purpose=purpose)
#     message = render_to_string(
#         "identity/verification_code_email.txt",
#         {
#             "code": verification_code.code,
#             "minutes": VERIFICATION_CODE_EXPIRY_MINUTES,
#             "purpose_label": purpose.label,
#         },
#     )
#     send_email_task.delay(subject=subject, message=message, recipient_list=[user.email])
#     return True


# def send_password_reset_code(*, user):
#     return _send_verification_email(
#         user=user, purpose=VerificationCode.Purpose.PASSWORD_RESET, subject="Your password reset code"
#     )


# def send_email_verification_code(*, user):
#     return _send_verification_email(
#         user=user, purpose=VerificationCode.Purpose.EMAIL_VERIFICATION, subject="Your verification code"
#     )

# This is the exact same _private_helper + public_function shape you already saw in _set_new_password / change_password / set_password_unchecked — the pattern repeats here at a slightly different layer of the codebase. This is worth recognizing as a general instinct when reading real code: whenever two files look almost identical except for 2–3 values, that's usually a sign a shared helper is waiting to be pulled out — and now you also have the concrete fix (.label instead of a hardcoded string) that a shared helper would have given you automatically, for free, instead of needing to notice the drift by comparing files side by side.

# 5. What to remember
# When you find two files that are nearly identical, compare them for divergence — the differences (like .label vs a hardcoded string here) often reveal which version is more correct, or which one drifted.
# Near-duplicate functions are a signal to extract a shared private helper — the same _helper() + thin public wrappers pattern you've now seen in two different features of this codebase.
# TextChoices members carry both .value (what's stored) and .label (human-readable) — prefer deriving display text from the enum over retyping it as a raw string, so it can never drift out of sync.
# Fixing one file doesn't fix its sibling — apply corrections everywhere the same pattern was copied, not just where you first spotted it.
# You've now fully read and audited the entire identity/auth feature — model, both verification-send services, generation, forgot-password, login, and both lockout handlers. That's a complete, real, production-shaped feature read end to end — a genuinely solid foundation for reading the rest of this codebase on your own.
