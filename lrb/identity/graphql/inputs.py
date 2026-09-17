import strawberry


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class RequestEmailVerificationInput:
    email: str


@strawberry.input
class VerifyEmailCodeInput:
    email: str
    code: str


@strawberry.input
class ForgotPasswordInput:
    email: str


@strawberry.input
class ResetPasswordInput:
    email: str
    code: str
    new_password: str


@strawberry.input
class ChangePasswordInput:
    current_password: str
    new_password: str


# 1. Purpose

# This file defines six @strawberry.input classes — the request-side counterpart to the @strawberry.type you just read. Where SessionType described data flowing out of the API to a client, these classes describe data flowing in — the exact shape of arguments a client must send when calling a GraphQL mutation. Each one maps directly onto a function you've already fully audited today. This is a great capstone file: you get to see the whole feature set from the very top, one layer above everything else.

# 2. The one new concept: @strawberry.input vs @strawberry.type
# python
# @strawberry.input
# class LoginInput:
#     email: str
#     password: str

# Structurally, this is identical syntax to SessionType — plain class, no parent, name: type annotations, no __init__ written by hand. The only difference is the decorator: @strawberry.input instead of @strawberry.type.

# @strawberry.type → generates an output shape (what the API sends back).
# @strawberry.input → generates an input shape (what a client must send in). In actual GraphQL schema terms, this becomes an input LoginInput { email: String!, password: String! } block — GraphQL's spec genuinely separates these into two different kinds of type, and Strawberry mirrors that with two different decorators. You can't use a type where an input is expected, or vice versa — GraphQL enforces this distinction at the schema level, the same way it enforces field existence, which you learned about in the last file.
# Every field here has no = default, meaning every field on every one of these classes is required — a client must supply all of them to call the corresponding mutation. None of these classes use Optional[...], unlike SessionType.created_at — that makes sense: there's no reasonable "optional" version of an email or password when logging in.

# Since the syntax pattern repeats six times identically, I won't re-explain the mechanics for each — just what each one represents and how it connects.

# 3. Each input, mapped to the function you already know
# python
# @strawberry.input
# class LoginInput:
#     email: str
#     password: str

# → Feeds login(*, email, password). Notice the field names (email, password) match the service function's parameter names exactly — this isn't a coincidence; it means the resolver can likely do something almost as simple as login(email=input.email, password=input.password), with no translation needed between the API-facing shape and the service-facing call.

# python
# @strawberry.input
# class RequestEmailVerificationInput:
#     email: str

# → Feeds request_email_verification(*, email) — the correctly-symmetric one, from the file you compared earlier.

# python
# @strawberry.input
# class VerifyEmailCodeInput:
#     email: str
#     code: str

# → Feeds verify_email(*, email, code).

# python
# @strawberry.input
# class ForgotPasswordInput:
#     email: str

# → Feeds forgot_password(*, email) — the one where you found and fixed the enumeration bug.

# python
# @strawberry.input
# class ResetPasswordInput:
#     email: str
#     code: str
#     new_password: str

# → Feeds reset_password(*, email, code, new_password) — the one where you found and fixed the exception-type enumeration bug.

# python
# @strawberry.input
# class ChangePasswordInput:
#     current_password: str
#     new_password: str

# → Feeds change_password(*, user, current_password, new_password) — and here's a detail worth noticing precisely because it's different from the others: there's no email or user field on this input at all. Every other input above supplies email, because those flows happen before a user is authenticated (that's the whole point — you're logging in, or you've forgotten your password, so the system doesn't yet know who you are except by the email you type). change_password, by contrast, requires you to already be logged in — the user argument that function expects doesn't come from this input at all; it comes from the authenticated request itself (e.g., request.user, populated by your session/cookie auth). This is a meaningful, correct design signal: the shape of an input type tells you something real about when and how that mutation is meant to be called.

# 4. Why this approach
# One input class per mutation, matching field names to service parameter names 1:1, minimizes the "translation layer" between the GraphQL boundary and your service layer — resolvers stay thin, exactly matching your project's stated principle that mutations are "thin orchestration layers that call services."
# Separate Input classes instead of one shared "credentials" blob reused everywhere — even though LoginInput and part of ResetPasswordInput both involve an email and a password-like field, keeping them as distinct types means each mutation's schema is precise: a client calling resetPassword is told, by the schema itself, that it needs code and new_password, not just "some password field" — self-documenting API design, enforced by the type system rather than left to a doc comment.
# No Optional fields anywhere in this file — a deliberate contrast with SessionType.created_at. Inputs are commands the client is issuing; there's rarely a sensible "partially specified" login attempt or password reset. Requiring every field up front means GraphQL itself rejects malformed requests before your resolver code ever runs — a validation layer you get for free, before your own service-level validation (like validate_password_strength) even executes.
# 5. Connections — the full map, now complete

# You can now draw the entire feature, top to bottom, for the first time:

# LoginInput ──────────────────────► login()
#                                      ├─ authenticate_credentials()
#                                      ├─ handle_failed_login() → lock_user()
#                                      └─ handle_successful_login() → unlock_user()

# ForgotPasswordInput ─────────────► forgot_password()
#                                      └─ send_password_reset_code()
#                                           └─ generate_verification_code() → VerificationCode

# ResetPasswordInput ──────────────► reset_password()
#                                      ├─ verify_code()
#                                      └─ set_password_unchecked() → _set_new_password()

# RequestEmailVerificationInput ───► request_email_verification()
#                                      └─ send_email_verification_code()
#                                           └─ generate_verification_code() → VerificationCode

# VerifyEmailCodeInput ────────────► verify_email()
#                                      ├─ verify_code()
#                                      └─ sets is_email_verified=True

# ChangePasswordInput (+ auth'd user) ► change_password()
#                                      ├─ user.check_password()
#                                      └─ _set_new_password()

# Every box in this diagram is a file you've read, understood, and in several cases, debugged yourself today.

# 6. What to remember
# @strawberry.type = data going out, @strawberry.input = data coming in — same Python syntax, genuinely different GraphQL schema concept, enforced by the spec itself.
# When an input type is missing a field you'd expect (like email or user on ChangePasswordInput), ask what that absence implies — here, it correctly signals "this mutation requires an authenticated session, not a fresh identity claim."
# Matching input field names to service parameter names 1:1 is what keeps resolvers thin — friction between an API shape and a service signature usually shows up as awkward renaming code in the resolver; its absence here is a sign of a well-aligned design.
# Required-by-default fields on inputs push validation as early as possible — GraphQL itself rejects incomplete requests before any of your Python runs.
# You've now read this entire authentication feature in full, top to bottom — GraphQL input contracts, orchestration functions, services, selectors, and the model underneath — and you did it by asking the same handful of questions at every layer: what can go wrong, what's every path return, and does this match what I've already verified elsewhere. That question-asking habit is the actual, durable skill — worth applying to the next file in this codebase, or any codebase, without needing this same walkthrough structure to hold your hand through it.