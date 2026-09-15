from typing import List, Optional

import strawberry

from lrb.authorization.graphql.types import RoleType
from lrb.core.graphql.errors import MutationError


@strawberry.type
class RoleMutationPayload:
    success: bool
    role: Optional[RoleType] = None
    errors: Optional[List[MutationError]] = None

@strawberry.type
class AssignmentMutationPayload:
    success: bool
    errors: Optional[List[MutationError]] = None

# Teaching: GraphQL Payload Types

# This file is short and, structurally, very close to the input types you just read — @strawberry.type instead of @strawberry.input, same "just annotations, no methods" shape. Since you already understand the mechanics (auto-generated constructor, Optional[...] fields), I'll spend most of this teaching on the design of these two payload shapes and what they reveal about how your whole project's error-handling actually works end to end — tying together nearly everything you've read this entire conversation.

# 1. What is it?

# Two GraphQL output types — the standardized "envelope" shape every mutation resolver in your project returns, wrapping either a real result or a list of structured errors, plus a flat success flag.

# Nothing syntactically new here beyond what you already know: @strawberry.type (output, not input), Optional[X] = None (optional field, default None), List[MutationError] (a list of another custom type you haven't seen the definition of, but can infer the shape of from usage).

# 2. How is it written?

# @strawberry.type (not @strawberry.input)
# Confirms these are response shapes — data flowing out of a mutation, back to the client — the mirror image of the input types you just read. This is the exact same decorator you first saw all the way back in UserMutation.

# success: bool
# No default value here — this field is required, meaning every payload instance must explicitly state whether the operation succeeded. Compare this to role/errors below, which both have = None defaults — required fields come first, ones with defaults come after (a plain Python rule: parameters/fields with defaults must follow ones without, in any single class/function definition).

# role: Optional[RoleType] = None
# On success, this carries the actual Role (wrapped in its GraphQL type) that was created/updated/fetched. On failure, it stays None — there's no role to return.

# errors: Optional[List[MutationError]] = None
# On failure, a list of structured error objects (imported from lrb.core.graphql.errors — this is almost certainly what format_application_error(e), which you first saw all the way back in UserMutation, actually builds and returns). On success, None — no errors to report.

# AssignmentMutationPayload — the same shape as RoleMutationPayload, minus the role field entirely. Just success and errors.

# 3 & 4. Signature/body — nothing new mechanically

# Both classes are the exact same shape you learned in the input-types file: plain annotated attributes, Strawberry auto-generates the constructor. No methods, no logic. The entire "body" of teaching here is really about why this specific shape, which is section 5.

# 5. Why? — tying together the whole error-handling story

# Why does every field except success have a default of None, rather than being required?
# Because a single payload instance is only ever "half full" — either the success path fills in role (and leaves errors as None), or the failure path fills in errors (and leaves role as None). Making both optional lets one shared class represent both outcomes cleanly, without needing two separate return types. This is the exact structure you've been watching get built throughout this whole conversation, every single time you saw:

# python
# return RoleMutationPayload(success=True, role=role)
# # or, on the other path:
# return RoleMutationPayload(success=False, errors=[format_application_error(e)])

# Now you're finally seeing the class definition that shape was always instantiating.

# Why success: bool as a required, separate field — rather than just checking if payload.role is not None?
# Because relying on "is the data field None?" as an implicit success signal is fragile and unclear — what if a future field naturally can be None even on success (imagine a nullable field on Role itself)? An explicit, dedicated success boolean removes all ambiguity: the client checks exactly one flag to know which branch of the response to read, regardless of what any individual data field happens to contain. This is a deliberate, explicit design choice for API clarity — never make the client infer success/failure from the shape of the data when you can just say so directly.

# Why AssignmentMutationPayload doesn't have a role field at all, rather than reusing RoleMutationPayload for assign/remove mutations too?
# Trace this back to what you already know: assign_role and remove_role both return a plain bool (True) on success — there's no meaningful object to hand back (you're not creating or modifying a Role, just a join record). A payload type should only carry fields that make sense for what the operation actually produces — including a role: Optional[RoleType] = None field that would always be None for these operations would be misleading to anyone reading the GraphQL schema, since it would suggest a role might sometimes come back, when it never actually does. This is the same "the type signature should tell the truth about what can happen" principle you've applied throughout this conversation to spotting missing/wrong type hints — just now applied to designing a type, not just annotating one.

# Why is this pattern ("standardized payload with success/data/errors") used consistently across your whole project, rather than each mutation inventing its own response shape?
# This connects directly back to your very first file's project notes: "Adopted a centralized SimpleMutationPayload to avoid Strawberry schema collisions." RoleMutationPayload and AssignmentMutationPayload are two more members of that same family (alongside UserMutationPayload, SimpleMutationPayload, BulkActionPayload from earlier files) — each mutation category gets its own payload shaped around exactly what data it can legitimately return, but they all share the same underlying contract: success: bool, plus whatever specific data or errors apply. A frontend developer only needs to learn this one pattern once, and every mutation in your entire API behaves predictably.

# 6. Connections

# What comes in: nothing — these are pure output shapes, built by resolvers.
# What goes out: exactly what a GraphQL client receives back from calling a role/assignment mutation.
# Direct connections — pulling together everything from this whole conversation:

# create_role, update_role, clone_role (all return a real Role object or raise) → each resolver calling them would build a RoleMutationPayload(success=True, role=role) on success, or RoleMutationPayload(success=False, errors=[...]) on any caught ApplicationError/AppValidationError.
# delete_role, assign_role, remove_role, set_permission_override, clear_permission_override (all return plain True or raise) → each resolver would build an AssignmentMutationPayload(success=True) on success, AssignmentMutationPayload(success=False, errors=[...]) on failure.
# bulk_assign_role/bulk_remove_role → these return a BulkActionResult, converted via to_bulk_payload(...) into a BulkActionPayload (a different payload type, from your very first file, since bulk operations need per-item results, not one flat success/failure).

# You've now traced the entire path, top to bottom, across this whole conversation: input type → resolver → service → selector/model → back up through a payload type → GraphQL response. This file is genuinely the last piece of that full picture.

# 7. Advanced concepts

# A) Discriminated unions vs. "one wide optional shape" — a design choice worth naming
# GraphQL (and Strawberry) actually supports a fancier alternative to this pattern: a true union type, where the schema says "this mutation returns either a RoleSuccess type or a RoleError type," and the client must check which one it got, rather than checking a success boolean and then trusting that the right optional field is filled in. Your project's chosen pattern (one shape, success boolean, several Optional fields) is simpler to implement and works fine for most GraphQL clients, but it does rely on convention rather than the type system to guarantee "if success is True, role will be present" — nothing stops a resolver from accidentally returning success=True, role=None. A union-based design would make that combination impossible to represent at all. Worth knowing this trade-off exists, even though your project has clearly settled on the simpler, wider-optional-shape convention consistently across every payload you've seen.

# B) Field ordering rules for classes with defaults
# A small but important mechanical rule, worth remembering generally (not just for Strawberry): in any Python class or function signature that mixes required and defaulted fields, all required ones must come before any with defaults. success: bool (no default) correctly comes first in both classes here; role/errors (both = None) come after. Getting this order backwards is a real syntax error, not just a style preference.

# 8. Small example
# python
# from typing import Optional, List

# class MutationError:
#     def __init__(self, message): self.message = message

# class RoleMutationPayload:
#     def __init__(self, success: bool, role=None, errors: Optional[List[MutationError]] = None):
#         self.success = success
#         self.role = role
#         self.errors = errors

# def create_role_resolver(name):
#     if len(name) < 2:
#         return RoleMutationPayload(success=False, errors=[MutationError("Name too short")])
#     return RoleMutationPayload(success=True, role={"name": name})

# r1 = create_role_resolver("Manager")
# print(r1.success, r1.role, r1.errors)   # True {'name': 'Manager'} None

# r2 = create_role_resolver("M")
# print(r2.success, r2.role, r2.errors)   # False None [<MutationError>]
# 9. What you should remember
# A payload type's fields should reflect exactly what an operation can legitimately return — don't include a data field (like role) on a payload for an operation (like assign_role) that never actually produces that kind of data; the schema should be honest about what's possible.
# success: bool as an explicit, required flag is safer than inferring success from whether a data field is None — it removes ambiguity for the client and doesn't rely on any single field's absence meaning something specific.
# Required fields must be declared before fields with defaults, in both classes and functions — a basic Python ordering rule that governs every signature you've read this whole conversation, input types and payload types alike.
# A shared "envelope" pattern (success/data/errors) across many different payload types is what lets one convention serve an entire API — recognize this as the same architectural instinct behind SimpleMutationPayload, UserMutationPayload, BulkActionPayload, and now RoleMutationPayload/AssignmentMutationPayload.
# This file is the return-trip counterpart to the input-types file you just read — together, the two files, plus every selector/service/resolver from this whole conversation, form one complete, traceable path from a GraphQL request all the way down to the database and back. Recognizing that a small file like this one is "just" the last piece of a bigger picture — not something to read in isolation — is itself a core code-reading skill.