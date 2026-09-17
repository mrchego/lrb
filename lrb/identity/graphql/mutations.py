import strawberry
from django.contrib.auth import login as django_login, logout as django_logout
from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.core.exceptions import ApplicationError
from lrb.core.graphql.errors import format_application_error
from lrb.core.graphql.payloads import SimpleMutationPayload
from lrb.identity.graphql.inputs import (
    ChangePasswordInput,
    ForgotPasswordInput,
    LoginInput,
    RequestEmailVerificationInput,
    ResetPasswordInput,
    VerifyEmailCodeInput,
)
from lrb.identity.graphql.payloads import AuthMutationPayload
from lrb.identity.services.login import login as login_action
from lrb.identity.services.logout import logout as logout_action
from lrb.identity.services.request_email_verification import (
    request_email_verification as request_email_verification_action,
)
from lrb.identity.services.verify_email import verify_email as verify_email_action
from lrb.identity.services.forgot_password import (
    forgot_password as forgot_password_action,
)
from lrb.identity.services.reset_password import reset_password as reset_password_action
from lrb.identity.services.change_password import (
    change_password as change_password_action,
)


@strawberry.type
class AuthMutation:
    @strawberry.mutation
    def login(self, info: strawberry.Info, input: LoginInput) -> AuthMutationPayload:
        try:
            user = login_action(email=input.email, password=input.password)
            django_login(info.context.request, user)
            return AuthMutationPayload(success=True, user=user)
        except ApplicationError as e:
            return AuthMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def logout(self, info: strawberry.Info) -> SimpleMutationPayload:
        try:
            logout_action()
            django_logout(info.context.request)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def request_email_verification(
        self, info: strawberry.Info, input: RequestEmailVerificationInput
    ) -> SimpleMutationPayload:
        try:
            request_email_verification_action(email=input.email)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def verify_email_code(
        self, info: strawberry.Info, input: VerifyEmailCodeInput
    ) -> SimpleMutationPayload:
        try:
            verify_email_action(email=input.email, code=input.code)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def forgot_password(
        self, info: strawberry.Info, input: ForgotPasswordInput
    ) -> SimpleMutationPayload:
        try:
            forgot_password_action(email=input.email)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def reset_password(
        self, info: strawberry.Info, input: ResetPasswordInput
    ) -> SimpleMutationPayload:
        try:
            reset_password_action(
                email=input.email, code=input.code, new_password=input.new_password
            )
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    def change_password(
        self, info: strawberry.Info, input: ChangePasswordInput
    ) -> SimpleMutationPayload:
        try:
            user = get_current_user_or_raise(info, message="Authentication required.")
            change_password_action(
                user=user,
                current_password=input.current_password,
                new_password=input.new_password,
            )
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )


# 1. Purpose

# This is the resolver layer — the file you've been predicting the shape of since the very first file today. AuthMutation is a @strawberry.type class (a container, like SessionQuery was, but for writes instead of reads) holding seven @strawberry.mutation methods — one per feature you've fully audited: login, logout, email verification, password reset, and password change. Each method is the missing translation step: it calls a service, catches whatever exception that service raises, and repackages the result into a payload — exactly what you predicted while reading AuthMutationPayload.

# This file is long, but you already understand almost everything in it. I'll explain the two genuinely new pieces once, then focus most of my attention on real issues — because there are several worth catching.

# 2. Imports — mostly familiar, one pattern reinforced twice
# python
# from django.contrib.auth import login as django_login, logout as django_logout

# The exact same aliasing technique from authenticate as django_authenticate — and now you can see why it's a recurring habit in this codebase: this class defines its own methods named login and logout. Without the alias, from django.contrib.auth import login would collide directly with the method you're about to define below it. One import line handles two potential name collisions at once (login/logout).

# python
# from lrb.identity.services.login import login as login_action
# from lrb.identity.services.logout import logout as logout_action
# from lrb.identity.services.request_email_verification import (
#     request_email_verification as request_email_verification_action,
# )
# ...

# Same reasoning, applied to every single service import in this file — each one is aliased with an _action suffix, because each resolver method below shares its exact name with the service function it calls (def login(...) calling login_action(...), def forgot_password(...) calling forgot_password_action(...)). This is a project-wide convention now, not a one-off trick: when a resolver method and its underlying service function share a name, alias one of them on import.

# python
# from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
# from lrb.core.graphql.errors import format_application_error
# from lrb.core.graphql.payloads import SimpleMutationPayload
# get_current_user_or_raise — a variant of get_current_user you already saw in SessionQuery, but this one raises instead of returning None — sensible for a mutation like change_password where "no user logged in" genuinely is an error, not a valid state to quietly return None for (unlike the session query, where "logged out" was a legitimate, answerable question).
# format_application_error — a helper that takes a raised ApplicationError and converts it into a MutationError (the list-item type you predicted in the AuthMutationPayload file). You now get to see it actually used.
# SimpleMutationPayload — the shared, generic payload (no user field) you can now recognize as the right choice for every mutation that only needs to report success/failure, without returning a user object — matching AuthMutationPayload's more specific shape (with user) being reserved just for login.
# 3. Signature — the shared shape, explained once
# python
# @strawberry.mutation
# def login(self, info: strawberry.Info, input: LoginInput) -> AuthMutationPayload:
# @strawberry.mutation — the write-side sibling of @strawberry.field from SessionQuery. Same idea (marks a method as something Strawberry calls live to compute a result), but registers it specifically as a mutation in the schema — GraphQL keeps queries and mutations as two separate top-level operation types, and this decorator is what tells Strawberry which bucket this method belongs in.
# self, info: strawberry.Info — identical to what you already understand from SessionQuery.session — framework-supplied, positional, not keyword-only, by necessity.
# input: LoginInput — a new parameter, but you already fully understand LoginInput (you read it two files ago). This is where the input class you learned actually gets used: Strawberry parses the client's submitted arguments into a real LoginInput instance, and hands it to this method as input. input here is a parameter name that shadows Python's own built-in input() function (the one that reads from a keyboard in a script) — that's completely fine inside this method's body, since you're not using the built-in here, but it's worth knowing that name is "taken" by Python normally, and this convention only works because nothing in this method needs the real built-in.
# -> AuthMutationPayload (or -> SimpleMutationPayload on the others) — same as SessionQuery: not just documentation, this is what Strawberry reads to know what shape this mutation returns in the schema.

# Every other mutation in this file follows this exact signature shape, just swapping which Input class it accepts and which payload type it returns. I won't re-explain the syntax seven times — I'll focus on what each body does differently, since that's where the real content (and the bugs) live.

# 4. Body — walking through each mutation, focusing on what's new or wrong
# login — correct, plus one design point worth understanding
# python
#     def login(self, info: strawberry.Info, input: LoginInput) -> AuthMutationPayload:
#         try:
#             user = login_action(email=input.email, password=input.password)
#             django_login(info.context.request, user)
#             return AuthMutationPayload(success=True, user=user)
#         except ApplicationError as e:
#             return AuthMutationPayload(
#                 success=False, errors=[format_application_error(e)]
#             )
# Correct order: verify credentials (login_action, which you audited in full — including the enumeration-ordering fix), then establish the real Django session (django_login) only after that succeeds.
# info.context.request — reaching through info (which you learned carries request-level context) to get the actual Django HttpRequest object, which django_login needs to attach the session cookie to.
# AuthMutationPayload(success=True, user=user) — worth pausing on. user here is a raw Django User model instance — not a UserType instance. You never see UserType(id=..., email=...) constructed explicitly anywhere in this file. Is that a bug? No — and understanding why is a genuinely useful intermediate GraphQL concept. Strawberry types generated with @strawberry.type are just Python dataclasses underneath — when Strawberry serializes the user field for the response, it doesn't check isinstance(user, UserType); it simply reads whatever attributes UserType declares (id, email, etc.) directly off whatever object was stored there, using ordinary attribute access. As long as the Django User model has matching attribute names for every field UserType declares, this works via duck typing — "if it has the attributes I need, I don't care what class it actually is."
# Contrast this with SessionType from earlier, where you had to manually write SessionType(user_id=data["user_id"], ...). Why the difference? Because get_active_session returns a plain dict, and data["user_id"] reads a dict key — dicts don't support .user_id attribute access at all, so Strawberry couldn't duck-type its way through a raw dict the same way it can through a model instance with real attributes. This is the actual rule worth remembering: Strawberry can serialize any object whose attributes match a type's fields — model instances often work directly; dicts almost always need to be manually unpacked into the real type first.
# logout — one thing worth verifying, not asserting as broken
# python
#     def logout(self, info: strawberry.Info) -> SimpleMutationPayload:
#         try:
#             logout_action()
#             django_logout(info.context.request)
#             return SimpleMutationPayload(success=True)
#         except ApplicationError as e:
#             ...

# logout_action() is called with zero arguments — every other service function you've read all day required at least a user=... keyword argument, and logging out conceptually needs to know who is being logged out (to clear failed-attempt counters, revoke a specific session, log the event, etc.). This file doesn't show you logout's actual definition, so I can't tell you with certainty this is wrong — it's entirely possible logout_action() is intentionally a no-op or a stub (echoing the get_active_session stub from your very first file), or that it's genuinely designed to take no arguments because all the real cleanup work happens in django_logout(info.context.request) right below it. This is exactly the kind of thing worth checking the actual file for, rather than guessing — a good habit to end on: when a call site looks surprising compared to every sibling call site you've seen, go read the definition before concluding either way.

# request_email_verification, verify_email_code, forgot_password, reset_password — structurally identical, and correct

# All four follow the same shape: call the service (with the exact keyword arguments you already know each one needs), return SimpleMutationPayload(success=True) on success, catch ApplicationError and format it on failure. Nothing new to explain syntax-wise — but one is worth a closer look for what it doesn't do.

# verify_email_code quietly discards a return value that you already established matters:

# python
#     def verify_email_code(self, info, input: VerifyEmailCodeInput) -> SimpleMutationPayload:
#         try:
#             verify_email_action(email=input.email, code=input.code)
#             return SimpleMutationPayload(success=True)
#         ...

# Go back to your own analysis of verify_email a few files ago: you reasoned carefully about why it returns the full user object instead of a bare True — specifically because verifying an email is a plausible moment to auto-log the user in, the same way login does with django_login(info.context.request, user). This resolver calls verify_email_action(...) but never captures or uses its return value at all — and returns the generic SimpleMutationPayload, which has no user field to put it in even if it wanted to. Either the earlier design reasoning about why verify_email returns user was aspirational and never actually wired up at this layer, or the product intentionally requires a separate login after verifying — but as written, verify_email handing back a User object serves no purpose here, since nothing downstream reads it. Worth flagging precisely because you reasoned so carefully about that design choice earlier — it's a good instinct to check whether a deliberate-looking design decision actually gets used where you'd expect.

# change_password — a real bug: the auth check sits outside the safety net
# python
#     def change_password(
#         self, info: strawberry.Info, input: ChangePasswordInput
#     ) -> SimpleMutationPayload:
#         user = get_current_user_or_raise(info, message="Authentication required.")
#         try:
#             change_password_action(
#                 user=user,
#                 current_password=input.current_password,
#                 new_password=input.new_password,
#             )
#             return SimpleMutationPayload(success=True)
#         except ApplicationError as e:
#             return SimpleMutationPayload(
#                 success=False, errors=[format_application_error(e)]
#             )

# Compare this line by line against every other mutation in the file. In all six others, absolutely everything that can fail sits inside the try block. Here, get_current_user_or_raise(info, message="Authentication required.") runs before the try even starts. Its name tells you exactly what it does on failure: it raises. Almost certainly raise ApplicationError(message=..., ...), matching the message= keyword argument passed to it here — but since that call sits outside the try, if it does raise, this mutation crashes uncaught, instead of gracefully returning SimpleMutationPayload(success=False, errors=[...]) the way every sibling mutation does for every other kind of failure.

# This directly undoes the whole architectural point you spent the last two files understanding: AuthMutationPayload/SimpleMutationPayload exist specifically so that expected failures never propagate as raw exceptions to the client. An unauthenticated call to changePassword is about as "expected" a failure as exists — yet it's the one case in this entire file not protected by the pattern the rest of the file establishes.

# The fix — move the call inside the try:

# python
#     def change_password(
#         self, info: strawberry.Info, input: ChangePasswordInput
#     ) -> SimpleMutationPayload:
#         try:
#             user = get_current_user_or_raise(info, message="Authentication required.")
#             change_password_action(
#                 user=user,
#                 current_password=input.current_password,
#                 new_password=input.new_password,
#             )
#             return SimpleMutationPayload(success=True)
#         except ApplicationError as e:
#             return SimpleMutationPayload(
#                 success=False, errors=[format_application_error(e)]
#             )
# 5. One architectural assumption worth naming explicitly

# Every mutation in this file catches except ApplicationError as e: — but you personally traced, several files ago, that verify_code, _set_new_password, and change_password's "current password incorrect" check all raise AppValidationError, a different class. For this file to work correctly, AppValidationError must be a subclass of ApplicationError — Python's except clause catches the named exception class and any of its subclasses, so except ApplicationError would only catch an AppValidationError if it inherits from ApplicationError somewhere in lrb.core.exceptions. Given how uniformly this file relies on that single except clause across every mutation, that inheritance relationship is almost certainly true by design — but it's exactly the kind of load-bearing assumption worth confirming by actually opening lrb/core/exceptions.py, rather than trusting it purely from context. If it turned out not to be true, every validation failure in this whole feature (wrong current password, expired code, weak new password) would crash instead of returning a clean payload — a single missing subclass relationship would undo the safety net for half the mutations in this file.

# 6. Connections — the full picture, complete

# You now have every layer, for real, of a production-shaped authentication feature:

# Client sends: mutation { login(input: {...}) }
#   → LoginInput (parses client arguments)
#   → AuthMutation.login() (this file — resolver)
#     → login_action() = login() (orchestration you fixed)
#       → authenticate_credentials(), handle_failed_login()/handle_successful_login()
#   → AuthMutationPayload (this resolver builds it, catching ApplicationError)
#   → Client receives: { success, user: {...} } or { success: false, errors: [...] }
# 7. What to remember
# Strawberry types resolve fields via attribute access on whatever object you give them — not strict isinstance checks. A Django model instance can satisfy a @strawberry.type directly if its attributes line up; a plain dict almost never can, and needs explicit unpacking instead.
# A shared "never raise to the client" pattern is only as strong as its weakest call site — one exception call made outside a try block (here, get_current_user_or_raise) undoes the guarantee for that one mutation, even while every sibling mutation upholds it correctly.
# When a resolver discards a return value that you know was deliberately designed to carry information, it's worth asking whether that design intent actually made it all the way through the stack, or stalled out at an earlier layer.
# A single-line "this call has no arguments, unlike every sibling call" observation is worth checking against the real definition before concluding anything — surprising code isn't always wrong code, and the fastest way to know the difference is to go read it, not guess.
# You have now read a complete, real authentication feature from the database column all the way to the exact GraphQL resolver a frontend calls — model, selectors, services, orchestration, input types, payload types, and resolvers — and independently caught bugs at nearly every layer along the way. That's the whole arc this format was built to teach: not this codebase specifically, but the standing habit of tracing every path, checking every assumption, and comparing every file against its siblings, on any code you read from here on.