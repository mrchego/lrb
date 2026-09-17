from django.contrib.auth import authenticate as django_authenticate

from lrb.core.exceptions import ApplicationError, ErrorCode


def authenticate_credentials(*, email: str, password: str):
    user = django_authenticate(email=email, password=password)
    if not user:
        raise ApplicationError(
            message="Invalid email or password.", code=ErrorCode.INVALID_CREDENTIALS
        )
    return user


# 1. Purpose

# This is a service function — the write/action side of your service/selector split (even though it doesn't write to the database, it performs an action: verifying credentials). Its job: take an email and password, check them against Django's authentication system, and either return a valid User object or raise a clear, structured error the rest of the app can catch and handle (e.g., to show "Invalid email or password" in a GraphQL response).

# This is the piece that sits underneath a "log in" mutation — the mutation itself should be a thin wrapper that just calls this.

# 2. Imports — explained from scratch
# python
# from django.contrib.auth import authenticate as django_authenticate
# django.contrib.auth is Django's built-in authentication app — it ships with Django and handles password hashing, user lookup, and login/logout machinery so you don't write that security-critical code yourself.
# authenticate is a function Django provides: give it credentials, it checks them against your User model (hashing the password and comparing safely), and returns the matching User object — or None if nothing matches.
# as django_authenticate — this is an import alias. import X as Y means "bring in X, but let me refer to it as Y in this file." Why rename it here? Because this file is defining its own function called authenticate_credentials, and having a local function accidentally shadow (hide) Django's authenticate would be confusing — you might later write authenticate(...) inside this file expecting your version, but accidentally call Django's, or vice versa. Renaming the import removes that ambiguity entirely; anyone reading this file instantly knows django_authenticate means "the framework's version," not something local.
# python
# from lrb.core.exceptions import ApplicationError, ErrorCode
# Again, your own project code (lrb.core), not a third-party library.
# ApplicationError — a custom exception class, presumably a subclass of Python's built-in Exception, built specifically for this project so that all "expected" business-logic failures (bad password, permission denied, etc.) share one common shape the GraphQL layer knows how to catch and turn into a clean error response — instead of leaking raw Python stack traces to the frontend.
# ErrorCode — almost certainly another TextChoices-style enum (like Purpose in your VerificationCode model), giving you a fixed, typo-proof set of error codes (ErrorCode.INVALID_CREDENTIALS, etc.) that the frontend can match against to decide what message or behavior to show.
# 3. Signature — piece by piece
# python
# def authenticate_credentials(*, email: str, password: str):
# def authenticate_credentials(...) — same pattern as before: defines a function named authenticate_credentials.
# * — forces everything after it to be keyword-only, matching your project's standing rule. You must call this as authenticate_credentials(email=..., password=...), never positionally.
# email: str and password: str — two required parameters, each type-hinted as str. The comma between them separates two independent parameters — each parameter after * still needs its own type hint and is still keyword-only, the * applies to all of them at once, not just the first.
# No -> ReturnType here — unlike the two functions you showed me earlier, this signature has no return type hint at all. That's a small inconsistency worth noticing as you read more of this codebase: it's missing something like -> User (or -> "accounts.User" as a string hint, since User may live in another app). Not a bug — Python runs fine without it — but it's a gap in documentation. If your project convention is "type hints on all service functions," this line falls short of it, and you'd add -> "accounts.User" to match.
# Final : — starts the function body.
# 4. Body — step by step
# python
#     user = django_authenticate(email=email, password=password)
# Calls Django's real authentication function, passing along the email and password this function received.
# What happens inside django_authenticate (you don't need to write this, but understanding it matters): Django looks up a user by the given identifier (here, email — meaning your project has configured Django to authenticate by email rather than the default username), takes the stored hashed password for that user, hashes the submitted password the same way, and compares the two hashes using a timing-safe comparison. It never compares plain-text passwords directly, and it never exposes why a match failed (wrong email vs wrong password) — both cases just return None. This is a deliberate security property: telling an attacker "that email doesn't exist" vs "wrong password" would leak information about which emails are registered.
# user — this variable will hold either a real User object (success) or None (failure).
# python
#     if not user:
# if — starts a conditional branch: only run the indented block below if the condition is true.
# not user — not is Python's boolean-negation operator. Since user is either a User object (which Python treats as "truthy" — meaning bool(user) is True) or None (which is "falsy"), not user reads naturally as "if there is no user" / "if authentication failed."
# Why not user instead of user is None? Both would work correctly here since django_authenticate only ever returns a User or None. not user is the more common, idiomatic Python phrasing for "this value is empty/missing/falsy" — but user is None is more precise (it can't accidentally match other falsy values like 0 or ""). Since user here can genuinely only be User or None, both are safe; is None is the marginally more defensive choice you'll sometimes see project style guides prefer for exactly this reason.
# python
#         raise ApplicationError(
#             message="Invalid email or password.", code=ErrorCode.INVALID_CREDENTIALS
#         )
# raise — a keyword that immediately stops normal execution and throws an exception up the call stack, to be caught by whatever calling code is watching for it (likely somewhere in your GraphQL mutation layer, which turns this into a user-facing error payload via your SimpleMutationPayload).
# ApplicationError(message=..., code=...) — constructs an instance of your custom exception class, passing in a human-readable message and a machine-readable code as keyword arguments.
# Deliberate vagueness in the message: notice it says "Invalid email or password" — not "No user with that email" or "Wrong password". This mirrors Django's own refusal to distinguish the two cases inside authenticate() — the service layer preserves that security property all the way up to the user-facing message, rather than accidentally leaking it back out.
# python
#     return user
# If we reach this line, user must be a real User object (the if block above would have already exited the function via raise otherwise). Return it to the caller.
# 5. Why this approach
# Wrapping Django's authenticate, instead of calling it directly everywhere: if you ever need to add something to the login check — e.g., checking user.is_active, logging failed attempts, rate-limiting — you add it once, here, and every caller (GraphQL mutation, admin login, management command) benefits without changes elsewhere.
# Raising a custom ApplicationError instead of returning None or a plain string: this keeps error handling consistent project-wide. Every place that can fail raises the same kind of exception, so your GraphQL layer can have one piece of code that catches ApplicationError and formats it into a response, instead of every resolver needing custom if result is None: ... checks.
# Not applying @transaction.atomic: your project convention is atomic transactions on write services. This function doesn't write anything to the database (Django's authenticate only reads and compares) — so it correctly has no @transaction.atomic, which is a good example of your project rule being applied selectively, not blindly on every service function.
# 6. Connections
# Input: raw email and password strings, most likely straight from a GraphQL mutation's input arguments (e.g., a LoginInput type).
# Calls into: Django's built-in auth system (django_authenticate) — this is the boundary between your app's code and Django's framework code.
# Output: either a real User object handed back to the caller (who would then typically call Django's login(request, user) to establish the session — matching your project's session/cookie-based auth), or an ApplicationError exception that propagates up to be caught and turned into a SimpleMutationPayload error.
# Sibling code: this function is a great candidate to sit right next to something like create_verification_code and reset_password in an accounts service module, since they're all part of the same auth flow.
# 7. Advanced concepts

# Import aliasing for name-collision avoidance — as django_authenticate isn't just a style choice. In Python, if you defined a local function called authenticate in this same file and had done from django.contrib.auth import authenticate (no alias), your local function would overwrite the import (or vice versa, depending on definition order) — whichever is defined later "wins" in that namespace. Renaming one of them at import time eliminates the entire class of bug where you can't tell, six months later, which authenticate a given line is calling.

# Why authentication functions return None instead of raising directly — Django's authenticate() deliberately returns None rather than raising its own exception on failure. This is a design choice: "did this specific check pass" is expected, routine behavior (users mistype passwords constantly) — not an exceptional, abnormal program state. Your authenticate_credentials function is the layer that decides "now that I know it failed, this is exceptional enough for this application to raise an error that stops the flow." This is a common two-layer pattern: low-level functions return None/falsy on "expected failure," and a higher-level layer converts that into an exception when the caller needs to stop everything.

# 8. Small example
# python
# def get_discount(*, code: str):
#     discounts = {"SAVE10": 10}
#     amount = discounts.get(code)  # None if code not found — "expected" failure
#     if not amount:
#         raise ApplicationError(message="Invalid discount code.", code=ErrorCode.INVALID_CODE)
#     return amount

# Same shape as your file: a lookup that can quietly return nothing, turned into a loud, structured error by the function wrapping it.

# 9. What to remember
# Alias imports (as) when a name you're importing could collide with something you're defining locally — it removes ambiguity for every future reader (including you).
# not value is Python's idiomatic falsy-check — works for None, empty strings, 0, empty lists, etc.; use value is None instead when you specifically only care about None and want to rule out other falsy values.
# Convert "expected failures" (None, empty results) into meaningful exceptions at the boundary that needs to stop execution — don't make every caller re-check if result is None themselves.
# Keep error messages exactly as specific as they should be, not more — vague-on-purpose messages (like "invalid email or password") are often a deliberate security decision, not a shortcut.
# Project conventions (keyword-only args, @transaction.atomic) apply based on what a function actually does, not automatically to every function — a read-only service function correctly skips @transaction.atomic even though write services always have it.

# One more thing worth flagging as you keep reading: this function is missing a return type hint, unlike the other two files you showed me. If you're auditing for consistency, that's a small drift from the "type hints on all service functions" pattern — worth adding -> "accounts.User" when you touch this file next.