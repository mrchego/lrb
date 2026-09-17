from lrb.accounts.selectors.get_user_by_email import get_user_by_email
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.identity.services.authenticate import authenticate_credentials
from lrb.identity.services.failed_login import handle_failed_login
from lrb.identity.services.successful_login import handle_successful_login


def login(*, email: str, password: str):
    user = get_user_by_email(email=email)

    try:
        authenticated_user = authenticate_credentials(email=email, password=password)
    except ApplicationError as e:
        handle_failed_login(user=user)
        raise e

    if authenticated_user.is_locked:
        raise ApplicationError(
            message=f"Account locked until {authenticated_user.locked_until.strftime('%Y-%m-%d %H:%M:%S')}.",
            code=ErrorCode.ACCOUNT_DISABLED,
        )
    if not authenticated_user.can_login:
        raise ApplicationError(
            message="Account disabled.", code=ErrorCode.ACCOUNT_DISABLED
        )
    if not authenticated_user.is_active:
        raise ApplicationError(
            message="Account inactive", code=ErrorCode.ACCOUNT_INACTIVE
        )

    handle_successful_login(user=authenticated_user)
    return authenticated_user


# 1. Purpose

# This is the top-level login orchestration function — the final piece of the puzzle. It ties together everything you've reviewed today: look up the user, run pre-authentication account-status checks, verify the password, then delegate to the success/failure handlers you already understand deeply. This is what a login GraphQL mutation would call directly.

# There are two real bugs here — one will crash, one is a security design flaw — plus a smaller consistency issue. Let's find them.

# 2. The crash: handle_successful_login(user)
# python
#     handle_successful_login(user)

# Go back and check how you defined that function two files ago:

# python
# def handle_successful_login(*, user):

# The * makes user keyword-only. This line calls it positionally — handle_successful_login(user) instead of handle_successful_login(user=user). Python will raise:

# TypeError: handle_successful_login() takes 0 positional arguments but 1 was given

# This means every single successful login crashes. This is the same category of mistake as set_password(new_password=new_password) earlier — but inverted: there, keyword args were used against a function that only accepts positional; here, a positional arg is used against a function that only accepts keyword. Same underlying lesson from a different angle: you have to match the actual signature of the function you're calling, not just guess based on what "feels" consistent.

# Fix:

# python
#     handle_successful_login(user=user)
# 3. The likely-crash: positional message in ApplicationError
# python
# raise ApplicationError(
#     f"Account locked until {user.locked_until.strftime('%Y-%m-%d %H:%M:%S')}.",
#     code=ErrorCode.ACCOUNT_DISABLED,
# )

# Every other ApplicationError(...) call you've reviewed today — in authenticate_credentials, in _set_new_password, in change_password — passes message= explicitly as a keyword. This is the only place in the whole codebase where the message is passed positionally. Given this project's blanket rule of keyword-only arguments on its own functions, ApplicationError.__init__ almost certainly enforces the same thing — meaning this line likely raises:

# TypeError: __init__() takes 1 positional argument but 2 were given

# Fix — match every other call site:

# python
# raise ApplicationError(
#     message=f"Account locked until {user.locked_until.strftime('%Y-%m-%d %H:%M:%S')}.",
#     code=ErrorCode.ACCOUNT_DISABLED,
# )

# A small syntax note on the line itself, since it's new today: f"...{user.locked_until.strftime('%Y-%m-%d %H:%M:%S')}." — the f prefix makes this an f-string (as you saw before); .strftime(...) is a datetime method that formats a date/time object into a specific string layout. %Y-%m-%d %H:%M:%S are format codes: 4-digit year, month, day, hour, minute, second. It's just string formatting — no bug there.

# 4. The real design flaw: account-status checks run before password verification
# python
# def login(*, email: str, password: str):
#     user = get_user_by_email(email=email)
#     if user:
#         if user.is_locked:
#             raise ApplicationError(...)   # <- runs BEFORE password check
#         if not user.can_login:
#             raise ApplicationError(...)
#         if not user.is_active:
#             raise ApplicationError(...)

#     try:
#         user = authenticate_credentials(email=email, password=password)
#     ...

# Trace through this carefully: get_user_by_email finds the user by email alone — no password needed yet. If that user happens to be locked, disabled, or inactive, the function raises a specific error immediately, before authenticate_credentials (the actual password check) ever runs.

# This means: anyone who knows or guesses a valid email address can learn that account's exact status — locked, disabled, or inactive — without ever needing to know the password. This is the same class of bug you just fixed in forgot_password (user enumeration), but worse here: instead of just learning "this email exists," an attacker learns detailed internal account state.

# Why this is a real risk, concretely: an attacker scripting through a list of email addresses (from a breach, a company directory, etc.) can silently map out which accounts are currently locked (useful for timing a brute-force attempt around the lockout) or disabled (useful for social-engineering an admin: "why is my account disabled?"). None of this requires a single correct password guess.

# The fix — verify credentials first, then check account status:

# python
# def login(*, email: str, password: str):
#     user = get_user_by_email(email=email)

#     try:
#         authenticated_user = authenticate_credentials(email=email, password=password)
#     except ApplicationError as e:
#         handle_failed_login(user=user)
#         raise e

#     if authenticated_user.is_locked:
#         raise ApplicationError(
#             message=f"Account locked until {authenticated_user.locked_until.strftime('%Y-%m-%d %H:%M:%S')}.",
#             code=ErrorCode.ACCOUNT_DISABLED,
#         )
#     if not authenticated_user.can_login:
#         raise ApplicationError(message="Account disabled.", code=ErrorCode.ACCOUNT_DISABLED)
#     if not authenticated_user.is_active:
#         raise ApplicationError(message="Account inactive", code=ErrorCode.ACCOUNT_INACTIVE)

#     handle_successful_login(user=authenticated_user)
#     return authenticated_user

# Now, the only way to learn anything about an account's lock/disabled/inactive status is to already have proven you know the correct password — exactly mirroring the principle you applied to forgot_password.

# (One nuance: authenticate_credentials likely already fails for a locked/inactive user in some Django configurations, depending on how your custom User model's is_active interacts with Django's authenticate() — worth checking, since it might affect exactly how much these three checks can even be reached after moving them. But the ordering principle — checks after credential verification, not before — holds regardless.)

# 5. Smaller consistency note: reused error code
# python
# if user.is_locked:
#     raise ApplicationError(..., code=ErrorCode.ACCOUNT_DISABLED)   # locked
# if not user.can_login:
#     raise ApplicationError(..., code=ErrorCode.ACCOUNT_DISABLED)   # disabled

# Both "locked" and "disabled" (two different, distinguishable states) raise the same ErrorCode.ACCOUNT_DISABLED. If your frontend ever needs to show a different message or behavior for "temporarily locked, try again later" vs. "permanently disabled, contact support," it can't — both arrive as identical codes. Worth a dedicated ErrorCode.ACCOUNT_LOCKED if that distinction matters to your product.

# 6. What's actually correct here
# The try/except/handle_failed_login structure is sound — and subtler than it looks. Notice user = authenticate_credentials(...) is inside the try. If authenticate_credentials raises, that assignment never completes — so in the except block, user still holds whatever get_user_by_email found earlier (or None). This is exactly why handle_failed_login's if not user: return guard exists — it correctly handles both "wrong password for a real account" and "email doesn't exist at all."
# raise e inside except ApplicationError as e: correctly re-raises the same exception after logging the failed attempt, rather than swallowing it.
# 7. Connections

# This function is the true top of the entire feature you've built up across this whole conversation:

# login()
#  ├─ get_user_by_email()           (selector)
#  ├─ authenticate_credentials()    (uses django_authenticate)
#  ├─ handle_failed_login()  ──────► lock_user()
#  └─ handle_successful_login() ───► unlock_user()

# And separately, the password-reset side:

# forgot_password() → send_password_reset_code() → generate_verification_code() → VerificationCode model

# Together these form one coherent authentication subsystem — you've now read every layer of it.

# 8. What to remember
# Positional vs. keyword mistakes go both ways — check whether a function you're calling was defined with * (keyword-only) just as carefully as you check whether it was defined with plain positional parameters.
# The order of security checks matters, not just their presence — "check X" and "check X only after proving Y" can look almost identical in code while having completely different real-world consequences.
# A pattern you've already fixed once (enumeration in forgot_password) is worth actively re-checking for elsewhere — the same mistake often repeats across a codebase in slightly different clothing.
# Reusing one error code for two logically different states saves a line of code today and costs you precision later — when a frontend or admin needs to tell two failure modes apart.
# You've now traced a complete real-world auth feature end to end — model → services → orchestration — and caught a crash bug, a fragile-API-assumption bug, and a genuine security-ordering flaw along the way. That's the actual skill this whole exercise has been building: not just reading code, but reading it skeptically.