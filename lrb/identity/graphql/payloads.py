from typing import List, Optional

import strawberry

from lrb.accounts.graphql.types import UserType
from lrb.core.graphql.errors import MutationError


@strawberry.type
class AuthMutationPayload:
    success: bool
    user: Optional[UserType] = None
    errors: Optional[List[MutationError]] = None


# 1. Purpose

# This is AuthMutationPayload — a @strawberry.type (output shape, as you learned last file) that defines what every auth mutation returns, not just one specific action. Where LoginInput told the API what a login request needs to contain, this tells the API what a login (or signup, or password change, etc.) response looks like. Your project notes call this pattern SimpleMutationPayload — a single, reusable "did it work, here's the result, here's what went wrong" envelope every mutation wraps its answer in, so the frontend always knows exactly what shape to expect no matter which mutation it just called.

# 2. Imports — two you haven't seen yet
# python
# from typing import List, Optional
# Optional — familiar. List is typing's way of type-hinting a Python list, with the kind of thing inside it specified in brackets: List[MutationError] means "a list where every item is a MutationError." Plain list (lowercase, no brackets) would just mean "some list, containing who-knows-what" — List[X] is far more informative, both to you reading it and to any tool checking it.
# python
# from lrb.accounts.graphql.types import UserType
# from lrb.core.graphql.errors import MutationError
# Both your own project code. UserType lives in accounts (not identity, where you've spent most of today) — this makes sense, since "a user" is a concept the whole project needs, not something specific to auth flows. MutationError lives in core — a shared, reusable error shape, matching the same "define it once, reuse everywhere" instinct you saw with ApplicationError/AppValidationError in the service layer, now mirrored at the GraphQL layer.
# 3. Signature — the class itself
# python
# @strawberry.type
# class AuthMutationPayload:
#     success: bool
#     user: Optional[UserType] = None
#     errors: Optional[List[MutationError]] = None

# Same annotation-only class shape you now recognize instantly. Let's go through each field and what it's doing, since the combination of these three fields is the actual interesting design here.

# 4. Body — field by field
# python
#     success: bool
# Required (no default), always a plain True/False. The one field every caller can check first, before looking at anything else.
# python
#     user: Optional[UserType] = None
# Nullable, defaulting to None. On a successful login or verify_email, this would hold the actual UserType — matching what you learned in verify_email, which deliberately returned the full user object rather than a bare True, specifically because the caller needs it. On a failed login, or on something like forgot_password (which never returns a user at all, remember — always just True), this stays None.
# python
#     errors: Optional[List[MutationError]] = None
# Nullable, defaulting to None, and when populated, a list of errors rather than a single one. This is a meaningful design choice: a list means a mutation could report multiple problems from a single attempt (e.g., a signup form failing both "email already taken" and "password too weak" at once) — as opposed to your service layer's raise ApplicationError(...), which can only ever raise one exception at a time and stop execution immediately.
# 5. The interesting part: this shape is designed to never raise to the client

# This is the biggest conceptual jump in this file, worth slowing down for. Every service function you've read all day raises on failure — raise ApplicationError(...), raise AppValidationError(...) — Python's normal way of saying "something went wrong, stop right here." But AuthMutationPayload isn't built to represent "an exception happened." It's built to represent a completed response that might describe failure, using plain data (success: False, errors: [...]) instead of Python's exception machinery.

# That means somewhere between your service layer and this payload, there must be a translation step — a resolver (the actual function decorated with something like @strawberry.mutation) that does roughly:

# python
# @strawberry.mutation
# def login(self, input: LoginInput) -> AuthMutationPayload:
#     try:
#         user = login_service(email=input.email, password=input.password)
#         return AuthMutationPayload(success=True, user=UserType.from_user(user))
#     except ApplicationError as e:
#         return AuthMutationPayload(
#             success=False,
#             errors=[MutationError(message=e.message, code=e.code)],
#         )

# Why go through this translation at all, instead of just letting the exception propagate up through GraphQL naturally? GraphQL can return raw errors in a special top-level errors array on every response, separate from the requested data — and many APIs do exactly that. But this project has chosen a different, deliberate pattern instead: every auth mutation always returns normal, predictable data — {success, user, errors} — never a top-level GraphQL error for something as routine as "wrong password." This has a real, practical payoff on the frontend: TypeScript code calling this mutation can treat "wrong password" and "successful login" as the same kind of response shape to check (if (result.success) ... else showErrors(result.errors)), rather than needing separate exception-handling logic just for the routine, expected failure cases. Genuinely unexpected crashes (a bug, a database outage) would still surface as real GraphQL-level errors — this payload pattern is specifically for the expected, routine failure cases your service layer already models cleanly with ApplicationError/AppValidationError.

# 6. Why this approach, more broadly
# One shared payload type reused across every auth mutation (your project notes literally confirm this: "Adopted a centralized SimpleMutationPayload to avoid Strawberry schema collisions") means the frontend only has to learn this response shape once, and every new mutation you add later — signup, delete account, whatever comes next — slots into the exact same handling code on the client with zero new logic.
# errors as a list, not a single value — future-proofs the shape for mutations that genuinely can have multiple simultaneous problems, even though today's single-raise service functions only ever produce one at a time. The payload's shape is slightly more general than what currently fills it — a reasonable, forward-looking design choice rather than overengineering, since it costs nothing today and avoids a breaking schema change later.
# user: Optional[UserType] rather than a separate payload type per mutation (e.g., a LoginPayload vs a RequestEmailVerificationPayload) — trades a small amount of specificity (every payload technically could return a user, even for mutations like forgot_password that never will) for a much simpler, single, memorable shape across the whole API. This mirrors the "why go through the trouble" question worth asking about any shared abstraction: fewer types to remember beats perfect per-mutation precision, as long as the imprecision (user always None for forgot_password) is harmless — and here, it clearly is.
# 7. Connections
# This is the actual return type of every resolver built on top of the functions you've spent all day reading. login, reset_password, verify_email, forgot_password, request_email_verification, change_password — every one of them is wrapped by a resolver that catches whatever ApplicationError/AppValidationError that service raises and repackages it into this shape.
# Directly connects to MutationError, a file you haven't seen but can now predict the shape of with confidence: almost certainly another small @strawberry.type with message: str and probably field: Optional[str] and/or code: str — matching the message/field/code keyword arguments you've now seen passed into ApplicationError/AppValidationError dozens of times today.
# Completes the full request/response picture: LoginInput (in) → login() service chain (business logic) → AuthMutationPayload (out) — you now have all three layers of a real GraphQL mutation, for six different mutations, fully traced.
# 8. Small example
# python
# @strawberry.type
# class SignupPayload:
#     success: bool
#     user: Optional[UserType] = None
#     errors: Optional[List[MutationError]] = None

# # A resolver would build one of these two shapes, never raise to the client:
# SignupPayload(success=True, user=new_user_type)
# SignupPayload(success=False, errors=[MutationError(message="Email already taken", field="email")])
# 9. What to remember
# A shared response payload type is the output-side mirror of a shared input pattern — just as Input classes standardize what a client must send, one reusable payload standardizes what every mutation sends back.
# List[X] type-hints the contents of a list, not just "it's a list" — always more informative than bare list.
# GraphQL APIs can choose to represent "expected" failures as ordinary data (success: False) rather than as raised/propagated errors — this is a deliberate architectural choice with a real frontend-simplicity payoff, not the only correct way to do it.
# Somewhere between a service's raise and a payload's success: False, there's always a translation step (a resolver) — you haven't seen that file yet, but you can now describe exactly what it must do before ever reading it, because you understand both sides of what it connects.
# You can now predict the shape of code you haven't read (MutationError, the resolver functions) purely from the conventions you've absorbed across everything else today — that's the clearest sign this teaching approach has actually built durable, transferable understanding, not just file-by-file memorization.