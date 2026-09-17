from lrb.accounts.selectors.get_user_by_email import get_user_by_email
from lrb.identity.services.send_password_reset_code import send_password_reset_code


def forgot_password(*, email:str):
    user = get_user_by_email(email=email)
    if user:
        send_password_reset_code(user=user)
        return True

# 1. Purpose

# This is the top-level orchestration function — the "forgot password" flow. Given an email address, it looks up the matching user (if any) and kicks off sending a reset code. This is almost certainly the function a GraphQL forgotPassword mutation calls directly, sitting one layer above everything you've reviewed so far: forgot_password → send_password_reset_code → generate_verification_code → VerificationCode model. You've now traced this feature from the very top all the way down to the database table.

# There's a genuine security bug here, and it's a subtle one — not a crash, but a logic flaw. I'll walk through the whole file, then explain it in detail.

# 2. Imports — explained from scratch
# python
# from lrb.accounts.selectors.get_user_by_email import get_user_by_email
# Note the folder: selectors, not services. This matches your project's read/write split — get_user_by_email is a selector (a pure lookup, no side effects, no writes), as opposed to everything else you've reviewed today, which lives under services/ (functions that do something — send emails, create rows, change state).
# This is the counterpart to the get_active_session stub you reviewed earlier — same category of function (a keyword-only lookup returning Optional[...]), just presumably a real implementation this time.
# python
# from lrb.identity.services.send_password_reset_code import send_password_reset_code
# The function from the previous file — directly imported and called here.
# 3. Signature
# python
# def forgot_password(*, email:str):
# * — forces email to be passed as a keyword, matching every other function in this codebase.
# email:str — a type hint, missing the conventional space after the colon (email: str is the standard formatting; most linters/formatters like black would auto-correct this). Purely cosmetic — Python doesn't care about the missing space, but it's a small tell that this file might not have been run through your project's auto-formatter.
# No -> Optional[bool] (or similar) return type hint — same recurring gap you've now spotted in almost every service function in this codebase.
# 4. Body — step by step
# python
#     user = get_user_by_email(email=email)
# Calls the selector, storing the result. Based on the naming pattern (Optional[dict] you saw earlier on a similar stub), this almost certainly returns either a User object or None.
# python
#     if user:
#         send_password_reset_code(user=user)
#         return True
# if user: — the truthy-check pattern you've now seen repeatedly: True/an object if found, None/falsy if not.
# If a user was found: call the send function (queues the email, as you reviewed), then return True.
# If no user was found: this if block is simply skipped, and there is no further code. The function falls off the end, which in Python means it implicitly returns None.
# 5. The bug: inconsistent return value leaks whether an email is registered

# Walk through both possible outcomes of calling this function:

# Situation	What's returned
# Email belongs to a real user	True
# Email doesn't belong to any user	None

# Now think about what the caller (a GraphQL mutation) does with that return value. If the mutation's response reflects this difference in any way — even something as small as success: true vs success: false/null, or a different HTTP status, or a slightly different response shape — an attacker can send a "forgot password" request for any email address and learn, from the response alone, whether that email exists in your system, without ever needing the actual password reset code. This is a well-known category of vulnerability called user enumeration.

# Compare this to send_password_reset_code from the previous file, which you now understand deliberately return True unconditionally — specifically so no information about the code itself leaks back through the return value. forgot_password should follow that exact same philosophy one level up: the response should look identical whether or not the email is registered.

# Why this matters in the real world: attackers use enumeration to build lists of valid accounts to target with credential-stuffing or phishing. It's on the OWASP list of common authentication weaknesses for exactly this reason — the fix is almost always "make the failure case and the success case indistinguishable from the outside."

# The fix
# python
# def forgot_password(*, email: str) -> bool:
#     user = get_user_by_email(email=email)
#     if user:
#         send_password_reset_code(user=user)
#     return True

# Moving return True outside and after the if block means it always runs, regardless of whether a user was found. From the caller's perspective, forgot_password now always looks identical — "we processed your request" — whether or not anything actually happened behind the scenes. The if user: check still correctly ensures you never try to email a nonexistent user; it just no longer changes what the function itself reports back.

# 6. Why the corrected approach is better
# Symmetric responses are the whole security property here — it's not enough to avoid saying "no account found" in an error message; you also have to avoid saying it implicitly, through a different return value, timing, or response shape. This is a good general lesson: security-sensitive logic needs to be audited not just for what it says, but for every observable difference between its "yes" and "no" paths.
# The fix costs nothing functionally — the real work (sending the email) still only happens when a user genuinely exists; you're only changing what gets reported back afterward.
# 7. Connections
# Direct caller: a forgotPassword GraphQL mutation, which should itself also return the same generic success message/payload no matter what forgot_password internally discovered — the fix needs to hold all the way up the chain, not just at this one function.
# This function is the top of the whole feature you've now fully traced: forgot_password → send_password_reset_code → generate_verification_code → writes to VerificationCode → (eventually) some verify_code function you haven't seen yet, checking the submitted code against the stored one.
# 8. Small example
# python
# # Wrong — leaks whether the username exists
# def request_account_recovery(*, username):
#     account = find_account(username=username)
#     if account:
#         send_recovery_link(account=account)
#         return True
#     # implicitly returns None here — different from the True above!

# # Correct — always the same response
# def request_account_recovery(*, username) -> bool:
#     account = find_account(username=username)
#     if account:
#         send_recovery_link(account=account)
#     return True
# 9. What to remember
# When a function's job is "trigger a side effect if X exists," make sure its return value doesn't leak whether X existed — this is a distinct concern from the side effect itself.
# An if block that only sometimes reaches a return is a common source of accidental None — always ask "what happens when this condition is false?" as deliberately as you ask "what happens when it's true?"
# Security-relevant symmetry has to be checked end-to-end — fixing this one function only matters if every layer above it (the mutation, the API response) also stays symmetric.
# Selectors (get_user_by_email) vs services (send_password_reset_code) — folder naming itself documents intent in this codebase: "am I about to read data, or cause an effect?" is answerable just by which folder a function lives in.
# This closes the loop on the whole feature — you've now read every layer of "forgot password," from the top-level orchestration down to the database row and back — a good moment to try writing the mirror-image reset_password(*, email, code, new_password) function yourself as practice, using everything you've seen.