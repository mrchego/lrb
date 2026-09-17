from typing import Literal

from lrb.accounts.selectors.get_user_by_email import get_user_by_email
from lrb.identity.services.send_email_verification_code import (
    send_email_verification_code,
)


def request_email_verification(*, email: str) -> Literal[True]:
    user = get_user_by_email(email=email)
    if user and not user.is_email_verified:
        send_email_verification_code(user=user)
    return True


# This is the request-side counterpart to send_email_verification_code — the function a "resend verification email" or "verify my email" flow would call. Given an email, it finds the user and, only if they're not already verified, sends them a new code. This is the sibling of forgot_password, and a great one to compare directly against it.

# This file is correct — including getting right the exact bug you found in forgot_password. Let's confirm why, since spotting why correct code is correct is just as valuable as catching bugs.

# 2. Signature
# python
# def request_email_verification(*, email: str):

# Same familiar shape: * forces email to be keyword-only. Type hint formatted correctly this time (email: str, with the space — unlike the small formatting slip in forgot_password). No return type hint — same recurring, now-expected gap in this codebase's service layer.

# 3. Body — step by step
# python
#     user = get_user_by_email(email=email)

# Same selector call you've now seen twice — returns a User or None.

# python
#     if user and not user.is_email_verified:
#         send_email_verification_code(user=user)
# and — Python's logical-and operator, and it short-circuits: if user is None (falsy), Python never even evaluates the right side (not user.is_email_verified). This matters concretely: if it did try to evaluate the right side with user = None, you'd get AttributeError: 'NoneType' object has no attribute 'is_email_verified'. The and here isn't just "combine two conditions" — it's also a safety guard, doing double duty: checking existence and preventing a crash on the next check, in one line.
# not user.is_email_verified — only reached if user is truthy. Skips sending a code entirely if the account is already verified — sensible: no reason to re-verify something already confirmed, and it avoids needlessly spending an email/Celery job on a no-op.
# python
#     return True

# This is the key line, and it's the fix you had to write yourself for forgot_password, applied correctly here from the start. Notice its indentation: it's at the same level as user = get_user_by_email(...) — outside the if block, not nested inside it. That means it runs unconditionally, every single time, regardless of whether user was found, and regardless of whether the code was actually sent.

# Walk through all three possible paths:

# Situation	Code sent?	Return value
# No user with that email	No	True
# User exists, already verified	No	True
# User exists, not yet verified	Yes	True

# Every path returns the exact same thing. An attacker probing this function with different email addresses learns nothing about which ones exist or which are already verified — exactly the symmetry property forgot_password was missing.

# 4. Why this matters, side by side with forgot_password
# python
# # forgot_password — the bug
# if user:
#     send_password_reset_code(user=user)
#     return True
# # falls through to implicit None if no user — ASYMMETRIC

# # request_email_verification — correct
# if user and not user.is_email_verified:
#     send_email_verification_code(user=user)
# return True
# # always reaches this line — SYMMETRIC

# The structural difference is small but critical: in the buggy version, return True was inside the if, so it only ran on the success path. Here, return True is a separate statement after the if block, so the if only controls the side effect (sending the email), never the return value. This is the exact fix pattern to reach for any time a function's job is "maybe do a side effect, but always answer the same way."

# 5. Connections
# Sibling to forgot_password — same shape, same "look up by email, maybe send a code" structure, now correctly guarding against enumeration where the other one didn't.
# Downstream: calls send_email_verification_code, which you already fully audited and confirmed correct — including its .label improvement over send_password_reset_code.
# This closes the second full vertical slice of the identity feature — you now have both forgot_password/send_password_reset_code and request_email_verification/send_email_verification_code fully read, one with a bug you fixed, one written correctly to compare it against.
# 6. What to remember
# and/or short-circuit — the left side gets evaluated first, and if it settles the result, the right side never runs. This is often the mechanism protecting the next line from a crash on None, not just a logic combinator.
# A return statement's indentation level is a security-relevant detail, not just a stylistic one — inside vs. after an if block can be the entire difference between symmetric and leaky behavior.
# When two functions do the same kind of job, compare them directly — you just used a working example to precisely explain what was wrong with a broken one; that comparison is often faster and clearer than reasoning about either function alone.
# Guard conditions can combine "does this exist" with "is there a reason to act" in one expression (user and not user.is_email_verified) — read these compound conditions left to right, since that's also the order Python evaluates them.
# You've now seen the same security principle (return-value symmetry) applied once broken and once correct — that contrast is usually what makes a lesson permanently stick, more than seeing either version alone.
