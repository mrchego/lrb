from __future__ import annotations
import strawberry
from typing import Optional, List
from lrb.accounts.graphql.types import UserType
from lrb.core.graphql.errors import MutationError
from lrb.core.graphql.payloads import BulkActionPayload

@strawberry.type
class UserMutationPayload:
    success: bool
    user: Optional[UserType] = None
    errors: Optional[List[MutationError]] = None

BulkUserActionPayload = BulkActionPayload


# from __future__ import annotations
# import strawberry
# from typing import Optional, List
# from lrb.accounts.graphql.types import UserType
# from lrb.core.graphql.errors import MutationError
# from lrb.core.graphql.payloads import BulkActionPayload

# The first three lines you've already seen. The new part is the last three — notice the file paths embedded in the import:

# lrb.accounts.graphql.types — this is exactly the file from your first message! UserType is being pulled back in from there.
# lrb.core.graphql.errors — a different app (core) than accounts, holding a shared MutationError type.
# lrb.core.graphql.payloads — also in core, holding BulkActionPayload.

# Why?
# Python's import path (lrb.accounts.graphql.types) mirrors your actual folder structure: lrb/accounts/graphql/types.py. This tells you something important about your project's organization: core is a shared app — things that many other apps need (generic error types, generic bulk-action response shapes) live there, so accounts, staff, orders, etc. can all import the same MutationError and BulkActionPayload instead of each app reinventing its own. This is exactly why your project notes mention a "centralized SimpleMutationPayload" — this file is applying that same philosophy to more specific payloads too.

# UserMutationPayload
# python
# @strawberry.type
# class UserMutationPayload:
#     success: bool
#     user: Optional[UserType] = None
#     errors: Optional[List[MutationError]] = None

# What is it?
# A @strawberry.type (data going out to the client, as you learned last file) with three fields:

# success: bool — a plain True/False. Required, no default — every mutation response must say whether it worked.
# user: Optional[UserType] = None — the updated user, if the mutation succeeded. Optional[...] = None because on failure, there's no user to return.
# errors: Optional[List[MutationError]] = None — Optional[List[MutationError]] reads as "either nothing, or a list of MutationError objects." On success, this stays None; on failure, it's filled with one or more error details.

# Why is this shape useful?
# This is the "result envelope" pattern, and it's one of the most important ideas in GraphQL mutation design. Here's the problem it solves: a raw UserType return value has no way to say "this failed, and here's why" — GraphQL would just throw a generic exception, which is hard for a frontend to handle gracefully (e.g., showing "phone number already in use" next to the phone field). By wrapping the real data (user) together with success and errors in one object, the resolver can always return successfully at the GraphQL level, and let the frontend decide how to react to success: false — check one boolean, then either use user or loop through errors to show messages.

# Signature-level detail worth noticing
# Every field here is either required-with-no-default (success) or optional-with-None-default (user, errors). There's no in-between — this is deliberate: success must always be stated, but the other two are mutually exclusive in practice (you'll get user OR errors, rarely both) — the type system doesn't enforce that exclusivity (Python won't stop you from filling both), but it's the convention the developer expects resolvers to follow.

# BulkUserActionPayload = BulkActionPayload
# python
# BulkUserActionPayload = BulkActionPayload

# What is it?
# This is not a class definition — there's no @strawberry.type, no class keyword. It's a plain Python assignment statement: name = value. Here, value happens to be another class (BulkActionPayload, imported from core), not a number or string.

# How is it written / why?
# In Python, classes are just objects like anything else — you can assign a class to a new name, the same way you'd write x = 5. This creates an alias: BulkUserActionPayload and BulkActionPayload now point to the exact same class. They are not two separate types — it's one type with two names.

# Why would a developer do this instead of just using BulkActionPayload directly everywhere?
# Two reasons, both about readability rather than behavior:

# Local, descriptive naming. Inside the accounts app's mutations, a resolver signature like def lock_users(...) -> BulkUserActionPayload: immediately tells another developer "this returns info about a bulk user action," which is clearer in context than the generic BulkActionPayload — even though it's really the same shared shape from core.
# No duplication. If BulkActionPayload ever needs a new field (say, a processed_count), it only needs to change in core — every app using it (including accounts, via this alias) gets the update automatically, because there's truly only one class in memory.

# Small example

# python
# Dog = Animal   # Dog and Animal are now literally the same class
# d = Dog()
# isinstance(d, Animal)  # True — because Dog IS Animal, just under a second name
# Connections

# This file ties everything together:

# UserMutationPayload is what a single-user mutation resolver returns — e.g. updateProfile(input: UpdateProfileInput!) -> UserMutationPayload, using the UpdateProfileInput from your last file and the UserType from your first file.
# BulkUserActionPayload is what a bulk mutation resolver returns — e.g. bulkLockUsers(input: BulkLockUserInput!) -> BulkUserActionPayload, using BulkLockUserInput from your last file.

# So across your three files, one full mutation "sentence" now reads: input type (what the client sends) → service function (does the work, enforces permissions) → payload type (what comes back). This file is the "what comes back" piece.

# What I should remember
# A "payload" type wraps real data with success/errors, so failures can be reported gracefully instead of crashing the whole GraphQL response.
# Import paths mirror your folder structure (lrb.core.graphql.errors → lrb/core/graphql/errors.py) — reading an import tells you exactly where to go look for the original definition.
# Shared, generic types belong in a core app; specific apps import and sometimes rename them for local clarity — this avoids duplicating the same shape across every app.
# Name = SomeClass (no class keyword) creates an alias, not a new type. Two names, one underlying class — useful for readability without duplication.
# Required vs optional fields in a payload tell you the resolver's contract: success is always set; user/errors are conditionally filled based on what happened — a pattern you'll see repeated in every mutation payload in this codebase.