from typing import List, Optional

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.graphql.types import (
    EffectivePermissionType,
    PermissionType,
    RoleType,
    UserPermissionOverrideType,
)
from lrb.authorization.selectors.get_role import get_role
from lrb.authorization.selectors.get_user_permissions import (
    get_user_permission_codenames,
)
from lrb.authorization.selectors.list_permissions import list_permissions
from lrb.authorization.selectors.list_roles import list_roles
from lrb.authorization.selectors.list_user_overrides import list_user_overrides
from lrb.authorization.selectors.user_has_permission import user_has_permission
from lrb.core.exceptions import AppPermissionDeniedError


@strawberry.type
class RoleQuery:
    @strawberry.field
    def permissions(self, info: strawberry.Info) -> List[PermissionType]:
        return list(list_permissions())

    @strawberry.field
    def roles(self, info: strawberry.Info) -> List[RoleType]:
        current = get_current_user_or_raise(info)
        return list(list_roles(company_id=str(current.company_id)))

    @strawberry.field
    def role(self, info: strawberry.Info, role_id: strawberry.ID) -> Optional[RoleType]:
        current = get_current_user_or_raise(info)
        return get_role(role_id=role_id, company_id=str(current.company_id))

    @strawberry.field
    def effective_permissions(
        self, info: strawberry.Info, user_id: strawberry.ID
    ) -> EffectivePermissionType:
        current = get_current_user_or_raise(info, message="Authentication required.")
        if not current.is_superuser and str(current.id) != str(user_id):
            raise AppPermissionDeniedError(
                message="You can only view your own permissions."
            )
        user = get_user(user_id=user_id)
        codenames = get_user_permission_codenames(user=user) if user else set()
        return EffectivePermissionType(user_id=user_id, codenames=sorted(codenames))

    @strawberry.field
    def my_permissions(self, info: strawberry.Info) -> EffectivePermissionType:
        current = get_current_user_or_raise(info, message="Authentication required.")
        codenames = get_user_permission_codenames(user=current)
        return EffectivePermissionType(user_id=current.id, codenames=sorted(codenames))

    @strawberry.field
    def user_permission_overrides(
        self, info: strawberry.Info, user_id: strawberry.ID
    ) -> List[UserPermissionOverrideType]:
        current = get_current_user_or_raise(info, message="Authentication required.")
        if not current.is_superuser and str(current.id) != str(user_id):
            raise AppPermissionDeniedError(
                "You can only view your own permission overrides."
            )
        return list(list_user_overrides(user_id=user_id))

    @strawberry.field
    def has_permission(self, info: strawberry.Info, codename: str) -> bool:
        current = get_current_user_or_raise(info, message="Authentication required")
        return user_has_permission(user=current, codename=codename)


# Teaching: RoleQuery

# This file is the read-side counterpart to UserMutation — same @strawberry.type + @strawberry.field shape, but every method here fetches data instead of changing it. Structurally, there's very little new syntax; the real value is in tracing a serious bug back to something you already caught in an earlier file, plus a couple of smaller inconsistencies worth flagging. Let's go through it.

# 1. What is it?

# A GraphQL query class exposing read operations for roles, permissions, and effective-permission lookups — the "GET" side of everything you've built up across services like list_roles, get_role, list_permissions, etc.

# Nothing syntactically new: @strawberry.type, @strawberry.field, strawberry.Info, Optional[X], List[X] — all familiar. What's new is the authorization pattern: several resolvers here check "is this the current user's own data, or are they a superuser?" — a self-service-vs-admin access rule you haven't seen phrased this way before.

# 2. How is it written? (new pattern)

# if not current.is_superuser and str(current.id) != str(user_id):
# Read this right-to-left in two parts joined by and:

# str(current.id) != str(user_id) — "the person asking is not the same person whose data is being requested" (same str(...) normalization trick from assign_role, comparing an ID that might arrive as different types).
# not current.is_superuser — "and they're not a superuser either."

# Both must be true to trigger the raise — meaning: you may view this data if you ARE the owner, OR if you're a superuser. This is a different shape of access rule from anything you've read before — earlier files checked "does this belong to my company" (tenant isolation); this checks "is this MY OWN data, or am I an admin" (self-service isolation). Same underlying philosophy (don't let user A read/touch user B's private data) applied at a different boundary.

# current.is_superuser
# A plain boolean attribute read directly off the User model — not a permission codename lookup (user_has_permission(...)), not a role check. This is Django's own built-in superuser flag (every Django User model ships with is_superuser by default), used here as an "escape hatch" for platform-level admins to see any user's data, bypassing the normal self-only restriction.

# Everything else in this file is direct reuse of things you already fully understand: get_current_user_or_raise(info, message=...), get_role(...), list_roles(...), list_permissions(), sorted(...) on a set, list(...) forcing a queryset to materialize.

# 3. Signature — one representative example
# python
# def effective_permissions(
#     self, info: strawberry.Info, user_id: strawberry.ID
# ) -> EffectivePermissionType:
# Piece	Meaning
# self	required for any method on a @strawberry.type class
# info: strawberry.Info	request context, same as always
# user_id: strawberry.ID	which user's permissions to look up — a plain scalar argument, not wrapped in an Input class, since GraphQL queries often take simple arguments directly rather than a whole input object (input types are more common for mutations, which tend to have more fields)
# -> EffectivePermissionType	the custom, non-model-backed output type from your types file
# 4. Body — walking through the two most interesting resolvers

# permissions — the odd one out:

# python
# def permissions(self, info: strawberry.Info) -> List[PermissionType]:
#     return list(list_permissions())

# Notice: no get_current_user_or_raise(info) call at all. Every other resolver in this file authenticates first; this one doesn't. Worth flagging as a genuine question (see section 5) — is it intentional that anyone, even an unauthenticated request, can list every permission that exists in the system?

# effective_permissions — the full self-or-superuser pattern:

# python
# current = get_current_user_or_raise(info, message="Authentication required.")
# if not current.is_superuser and str(current.id) != str(user_id):
#     raise AppPermissionDeniedError(message="You can only view your own permissions.")
# user = get_user(user_id=user_id)
# codenames = get_user_permission_codenames(user=user) if user else set()
# return EffectivePermissionType(user_id=user_id, codenames=sorted(codenames))
# Authenticate — note the custom message="Authentication required." override, using exactly the upgrade you just made to get_current_user_or_raise.
# Authorize — self-or-superuser check.
# user = get_user(user_id=user_id) — fetch the target user (who might be a different person than current).
# codenames = get_user_permission_codenames(user=user) if user else set() — a conditional expression (a compact if/else written on one line, sometimes called a "ternary"): "compute the real codenames if user was found; otherwise, just use an empty set." This guards against user_id pointing at a nonexistent user without needing a separate raise.
# sorted(codenames) — turn the unordered set into a stable, alphabetically sorted list for the response (sets have no defined order; sorting makes the API's output predictable and diffable).

# my_permissions — a near-duplicate:

# python
# current = get_current_user_or_raise(info, message="Authentication required.")
# codenames = get_user_permission_codenames(user=current)
# return EffectivePermissionType(user_id=current.id, codenames=sorted(codenames))

# Same computation as effective_permissions, but hardcoded to "yourself" — no user_id argument needed, no ownership check needed (you always own your own data), and no if user else set() guard needed (since current is guaranteed non-None by get_current_user_or_raise). This is a convenience wrapper for the extremely common case "show me my own permissions," saving the frontend from having to pass its own user ID back to itself.

# has_permission — a redundant check:

# python
# current = get_current_user_or_raise(info)
# if not current:
#     raise AppPermissionDeniedError("Authentication required")
# return user_has_permission(user=current, codename=codename)

# Look closely at the second line. get_current_user_or_raise always either returns a real, non-None user, or raises AppPermissionDeniedError itself — that's the entire contract you learned when you first read this function, and its very name promises it ("...or_raise"). This means if not current: on the next line can never possibly be true — by the time this line runs, current is guaranteed to be a real user. This is dead code: harmless (it will never execute), but it signals either a misunderstanding of what get_current_user_or_raise already guarantees, or leftover code from before that guarantee existed. Worth removing for clarity — the exact same reasoning you'd apply to spotting any other piece of code that can never run.

# 5. Why? — and the serious bug this file exposes

# Why does permissions skip authentication while every other resolver requires it?
# This might be entirely intentional — a list of what permissions exist in the system (their codenames, labels, categories) arguably isn't sensitive information on its own; it doesn't reveal anything about any specific user or company's actual data. But it's exactly the kind of asymmetry worth questioning rather than assuming is correct: does your product actually want anonymous/unauthenticated clients to see the full permission catalog? If not, this is a real gap; if so, it's a deliberate, reasonable design choice. Worth checking against your actual product requirements rather than guessing.

# Why the self-or-superuser pattern, duplicated across two resolvers (effective_permissions, user_permission_overrides)?
# Same "don't leak other people's data" principle you've applied throughout this conversation — but here at the level of individual users' permission data, rather than company-level tenant isolation. The duplication itself (same if not current.is_superuser and str(current.id) != str(user_id): raise ... logic copy-pasted in two places, with two slightly differently worded messages) is a real candidate for extraction into a shared helper — exactly the same kind of "spot the duplication" instinct you applied to create_role/update_role's repeated permission-validation block earlier.

# Now, the important bug — trace user_permission_overrides's return type back through everything you've already learned:

# python
# from lrb.authorization.models.user_role import UserPermissionOverride
# ...
# def user_permission_overrides(
#     self, info: strawberry.Info, user_id: strawberry.ID
# ) -> List[UserPermissionOverride]:

# Look at the import at the top of this file: UserPermissionOverride is imported from lrb.authorization.models.user_role — that's the Django model, not the GraphQL type. Now recall the GraphQL types file you read two files ago, where you personally caught this exact bug:

# python
# @strawberry_django.type(UserPermissionOverride)
# class UserPermissionOverride:   # <- shadows the model import, inside THAT file
#     ...

# That earlier bug means the correct GraphQL type — the one Strawberry actually needs for a field's return annotation — is defined inside lrb.authorization.graphql.types, confusingly also named UserPermissionOverride (because of the naming collision you caught). But this file never imports that GraphQL type at all. It imports only the plain Django model, and uses that model class directly as -> List[UserPermissionOverride].

# Why this actually breaks: Strawberry needs every field's return type to be a real, registered GraphQL type (something decorated with @strawberry.type or @strawberry_django.type) — a plain Django model class, with no Strawberry decoration at all, is not something Strawberry knows how to serialize into a GraphQL response. This resolver would fail — either at schema-build time (Strawberry complaining it doesn't recognize UserPermissionOverride as a valid GraphQL output type) or, if it somehow got past that, at actual query-execution time, when Strawberry tries and fails to convert real UserPermissionOverride model instances into GraphQL response fields.

# The fix:

# python
# from lrb.authorization.graphql.types import (
#     EffectivePermissionType,
#     PermissionType,
#     RoleType,
#     UserPermissionOverrideType,   # <- the corrected, renamed GraphQL type from that earlier fix
# )
# ...
# def user_permission_overrides(
#     self, info: strawberry.Info, user_id: strawberry.ID
# ) -> List["UserPermissionOverrideType"]:

# This is a genuinely satisfying moment in your learning: the shadowing bug you personally caught two files ago wasn't just a style nitpick — it directly causes this real, concrete breakage here, in a completely different file, the moment someone tries to use that type correctly. This is exactly why catching naming collisions early matters: the damage doesn't show up at the point of the mistake, it shows up later, somewhere else, in a way that can be confusing to trace back if you didn't already know the root cause.

# 6. Connections

# What comes in: info (always), plus specific IDs/codenames depending on the query.
# What goes out: PermissionType/RoleType lists, an Optional[RoleType], EffectivePermissionType, a (currently broken) list of permission overrides, or a plain bool.
# Reuses everything: every selector you've read this whole conversation (list_permissions, list_roles, get_role, list_user_overrides, get_user_permission_codenames, user_has_permission) gets its first real "consumer" shown here — this file is where all that selector-layer work actually gets exposed to a frontend.
# Direct proof of the earlier bug's real-world impact: as explained above.

# 7. Advanced concepts

# A) A guaranteed non-None value doesn't need a follow-up None check — trust the contract
# has_permission's if not current: is a good example of not trusting a function's documented contract. When a function's name and prior behavior (_or_raise) guarantee something, re-checking it defensively isn't "extra safety" — it's dead code that suggests the guarantee isn't understood or trusted. A good habit: when you use a function like get_current_user_or_raise, treat its guarantee as load-bearing — don't re-verify what it already promises.

# B) A conditional expression (ternary) for a safe fallback
# get_user_permission_codenames(user=user) if user else set() is the one-line equivalent of:

# python
# if user:
#     codenames = get_user_permission_codenames(user=user)
# else:
#     codenames = set()

# Useful when the "then" and "else" branches are both simple, single expressions — turns a 4-line if/else into one readable line. Not appropriate when either branch needs multiple statements — that's when a real if/else block is clearer.

# C) A schema-level bug that only surfaces at build/run time, not at "read time"
# This is worth naming as its own category, distinct from the Python-level bugs you've caught before (like the missing raise in assign_role). A wrong type hint on a Strawberry field doesn't crash when Python imports the file — the class definitions are syntactically valid Python. It only breaks when Strawberry actually tries to build the GraphQL schema from these type hints, or when a client actually queries this specific field. This is a good reminder that "the file imports without error" is not the same as "the file is correct" — some bugs only reveal themselves at a later stage of the system's lifecycle.

# 8. Small example (demonstrating the type-mismatch bug conceptually)
# python
# import strawberry

# class PlainPythonClass:   # NOT decorated with @strawberry.type
#     def __init__(self, value):
#         self.value = value

# @strawberry.type
# class Query:
#     @strawberry.field
#     def get_thing(self) -> PlainPythonClass:   # Strawberry doesn't know this type!
#         return PlainPythonClass(value=42)

# schema = strawberry.Schema(query=Query)
# # Strawberry raises an error building the schema:
# # it doesn't recognize PlainPythonClass as a valid GraphQL type
# 9. What you should remember
# A resolver's return type hint must point at an actual Strawberry-registered type, never a plain Django model class — Strawberry can't serialize a model directly; check that every -> annotation on a @strawberry.field traces back to something decorated with @strawberry.type/@strawberry_django.type.
# A naming collision you catch in one file can cause silent, confusing breakage in a completely different file later — this is exactly why the earlier fix mattered beyond "just tidiness"; tracing a bug's actual downstream impact is a powerful way to understand why a rule matters, not just that it exists.
# Don't re-check a condition a function's contract already guarantees — has_permission's redundant if not current: after get_current_user_or_raise is dead code; trust the function you already verified does what its name promises.
# "Can view own data, or is a superuser" is a distinct, common authorization pattern from company/tenant scoping — recognize it as its own category, and notice when it's duplicated across resolvers as a signal to extract a shared helper.
# Not every resolver in a file needs to follow the exact same pattern (like requiring authentication) — but every asymmetry (like permissions skipping it) deserves a deliberate "is this actually intended?" check, rather than assuming consistency where none was verified.
# You are out of free messages until 4:00 PM
# Write a message…



