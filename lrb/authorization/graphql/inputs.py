from typing import List, Optional

import strawberry


@strawberry.input
class CreateRoleInput:
    name: str
    permission_codenames: List[str] = strawberry.field(default_factory=list)
    is_default: bool = False

@strawberry.input
class UpdateRoleInput:
    role_id: strawberry.ID
    name: Optional[str] = None
    permission_codenames: Optional[List[str]] = None
    is_default: Optional[bool] = False

@strawberry.input
class DeleteRoleInput:
    role_id: strawberry.ID

@strawberry.input
class AssignRoleInput:
    user_id: strawberry.ID
    role_id: strawberry.ID

@strawberry.input
class RemoveRoleInput:
    user_id: strawberry.ID
    role_id: strawberry.ID

@strawberry.input
class SetPermissionOverrideInput:
    user_id: strawberry.ID
    permission_codename: str
    is_granted: bool

@strawberry.input
class ClearPermissionOverrideInput:
    user_id: strawberry.ID
    permission_codename: str

@strawberry.input
class CloneRoleInput:
    role_id: strawberry.ID
    new_name: str

@strawberry.input
class BulkAssignRoleInput:
    user_ids: List[strawberry.ID]
    role_id: strawberry.ID

@strawberry.input
class BulkRemoveRoleInput:
    user_ids: List[strawberry.ID]
    role_id: strawberry.ID


# Teaching: GraphQL Input Types

# This file introduces @strawberry.input — a new decorator for a new kind of GraphQL type (inputs, not outputs), plus a strawberry.field(default_factory=...) pattern you haven't seen. It's also the perfect place to apply everything you've learned about the is not None sentinel pattern from update_role — because this file contains a real, concrete bug that directly connects to that exact lesson.

# 1. What is it?

# Ten small classes, each describing the shape of data a GraphQL mutation expects as input — literally the input types (CreateRoleInput, UpdateProfileInput, etc.) you've seen referenced as parameters throughout every mutation resolver in this whole conversation, finally shown to you directly.

# New pieces:

# @strawberry.input — a decorator
# strawberry.field(default_factory=list) — a special default-value helper
# strawberry.ID (you saw this briefly in the last file)
# List[strawberry.ID] — a list of GraphQL IDs
# Class bodies with only annotations, no methods — a new shape entirely
# 2. How is it written?

# @strawberry.input
# A sibling to @strawberry.type and @strawberry_django.type — but specifically for input types: data flowing into a mutation from the client, rather than data flowing out as a response. GraphQL genuinely distinguishes these as two different kinds of types on the wire (type for outputs, input for inputs) — you can't use an output type as a mutation argument, or vice versa; this decorator is what tells Strawberry which category a given class belongs to.

# Class bodies with just name: type lines, no def, no self
# This is a new shape you haven't encountered directly yet, though you've been using the results of it all along (every input.first_name, input.user_id access throughout every mutation file was reaching into a class exactly like these). Under the hood, @strawberry.input (like @strawberry_django.type) turns these plain annotated attributes into something similar to a dataclass — Strawberry automatically generates the __init__ method for you behind the scenes, based on each line. Writing:

# python
# @strawberry.input
# class CreateRoleInput:
#     name: str
#     permission_codenames: List[str] = strawberry.field(default_factory=list)
#     is_default: bool = False

# is roughly equivalent, in plain Python, to:

# python
# class CreateRoleInput:
#     def __init__(self, name, permission_codenames=None, is_default=False):
#         self.name = name
#         self.permission_codenames = permission_codenames if permission_codenames is not None else []
#         self.is_default = is_default

# — except you never write that __init__ yourself; the decorator generates it from the annotations.

# permission_codenames: List[str] = strawberry.field(default_factory=list)
# This is the one genuinely new mechanic. You might expect = [] directly as the default, matching the simple = False/= None defaults elsewhere in this file — but that would actually be a classic, dangerous Python bug if this were a plain function/dataclass default. Here's why: in Python, a mutable default value (like a list [], dict {}, or set set()) written directly in a default position is created once, when the class/function is defined — not fresh, each time a new instance is created. If multiple CreateRoleInput instances shared that same single list object as their default, appending to one instance's list could silently affect every other instance that never got an explicit value. default_factory=list avoids this entirely: instead of a shared, pre-built empty list, you pass list — the function itself, not a call to it (no ()) — and Strawberry calls list() fresh, producing a brand-new empty list, every single time a new instance needs a default value. This is the same underlying concept Python's own dataclasses module solves with field(default_factory=list) — Strawberry's strawberry.field(default_factory=list) mirrors that exact pattern deliberately.

# List[strawberry.ID]
# Combines two things you've now separately learned: List[X] (a list of some type) and strawberry.ID (the GraphQL identifier scalar type from the last file) — "a list of ID values," used for bulk operations (BulkAssignRoleInput.user_ids).

# 3 & 4. Signatures/bodies — the repeated pattern, and what varies

# Every class here follows the exact same shape: a handful of plain name: type (or name: type = default) lines, no logic at all. Once you recognize this as "auto-generated dataclass-like input," you don't need line-by-line walkthroughs for each — what's worth comparing is which fields are required vs. optional, and why, since that maps directly onto everything you've learned about required vs. optional parameters in the services these inputs eventually feed into.

# CreateRoleInput — name required, permission_codenames optional (empty list default), is_default optional (False default). Matches create_role's signature almost exactly — company isn't here because that comes from the authenticated session (current.company_id), never from client input (a deliberate security boundary you learned about back in update_profile, where current.id was used instead of trusting client-supplied identity).

# UpdateRoleInput — role_id required (which role); everything else optional, defaulting to indicate "don't change this" — matching update_role's partial-update design. Except one field doesn't actually match — see the bug below.

# DeleteRoleInput, AssignRoleInput, RemoveRoleInput, SetPermissionOverrideInput, ClearPermissionOverrideInput, CloneRoleInput — each is just the minimal set of required IDs/values needed to identify what the corresponding service call needs, with no optional fields at all (these services don't do partial updates — they perform one complete, well-defined action).

# BulkAssignRoleInput, BulkRemoveRoleInput — List[strawberry.ID] for user_ids, plus one role_id — directly matching bulk_assign_role/bulk_remove_role's Iterable[str] + role_id signatures you read earlier.

# 5. Why? — and a real bug this comparison reveals

# Why do input types exist as a separate concept from output types at all?
# Because a GraphQL client needs to know, at the schema level, exactly what shape of data it's allowed to send versus what shape it should expect back — these are often genuinely different shapes (an input rarely includes computed fields like RoleType.staff_count, for instance), and GraphQL's type system enforces that distinction strictly, catching mismatches before a request is even sent.

# Why default_factory=list instead of = []?
# Explained above — protects against the shared-mutable-default bug. Worth internalizing as a hard rule: never use a mutable literal ([], {}, set()) as a default value directly — always use a factory pattern (default_factory=list, or in plain Python function defaults, the param=None + param = param or [] pattern you actually saw back in create_role!). That's worth connecting directly: create_role's permission_codenames = permission_codenames or [] inside the function body is solving the exact same underlying problem as default_factory=list solves here — just at a different layer (a service function's parameter default vs. a GraphQL input class's field default). Same danger, two different correct solutions depending on context.

# Now, the bug — compare UpdateRoleInput.is_default against update_role's actual sentinel logic:

# python
# @strawberry.input
# class UpdateRoleInput:
#     role_id: strawberry.ID
#     name: Optional[str] = None
#     permission_codenames: Optional[List[str]] = None
#     is_default: Optional[bool] = False    # <-- look closely

# Every other optional field here defaults to None — correctly signaling "the caller didn't touch this field." But is_default defaults to False, not None — even though it's typed as Optional[bool], suggesting None was the intended "not provided" marker, matching its siblings.

# Now trace what actually happens when this flows into update_role, which you already learned uses:

# python
# if is_default is not None:
#     role.is_default = is_default

# If a client sends an UpdateRoleInput without setting is_default at all (intending only to change the role's name, say), Strawberry will fill in the class's default — which is False, not None. That False then gets passed into update_role(is_default=False, ...). Because False is not None evaluates to True, the service will incorrectly interpret "the client didn't mention this field" as "the client explicitly wants to turn off is_default" — silently overwriting is_default to False on every single update call that doesn't deliberately set it, even when the caller never intended to touch it at all.

# This is a genuinely serious bug, and it's a perfect, concrete illustration of exactly the lesson from update_role: the whole point of using is not None instead of a truthiness check was to correctly distinguish "not provided" from "explicitly set to False." That distinction only works end-to-end if the input type actually uses None as its "not provided" sentinel too — this input type breaks that chain at the very first step, before the service logic ever gets a chance to reason about it correctly. The fix is a one-character-conceptual change:

# python
# is_default: Optional[bool] = None    # matches its own type hint, matches update_role's expectation

# Why is this the kind of bug that's easy to miss? Because in isolation, is_default: Optional[bool] = False reads as plausible — "if not specified, default to False" sounds like completely reasonable, ordinary code, the same shape as CreateRoleInput.is_default: bool = False just above it (which is correct, for a create operation, where there's no "existing value to leave alone" — a genuine default makes sense there). It's only wrong here because you already know, from reading update_role directly, what "unset" is specifically supposed to mean for this exact operation — this is a bug that's essentially invisible unless you compare the input type against the service function it feeds, exactly the skill you've been building all conversation.

# 6. Connections

# What comes in: these classes ARE the "what comes in" for every mutation you've read throughout this entire conversation — input.name, input.user_id, input.permission_codenames, all trace back to exactly these field declarations.
# What goes out: nothing — inputs are consumed, not returned.
# Direct connections: CreateRoleInput → create_role's parameters; UpdateRoleInput → update_role's parameters (with the bug just found); BulkAssignRoleInput/BulkRemoveRoleInput → bulk_assign_role/bulk_remove_role's user_ids/role_id. Every resolver in a RoleMutation class (the sibling to UserMutation you read first) would take one of these as its input: parameter and unpack it into the matching service call — the exact same shape as update_profile(self, info, input: UpdateProfileInput) from your very first mutations file.

# 7. Advanced concepts

# A) The mutable-default-argument trap, in two different forms
# You've now seen this exact bug-prevention pattern twice, in two different syntaxes, solving the identical underlying problem:

# Plain Python function parameter: def f(x=None): x = x or [] (seen in create_role)
# Strawberry/dataclass field: x: List[str] = strawberry.field(default_factory=list) (seen here)
# Both exist because def f(x=[]): or x: List[str] = [] directly would create one shared list object, reused across every call/instance that doesn't override it — a famous, classic Python gotcha worth permanently remembering: never put a mutable literal directly as a default value; always use None + fallback, or a factory function.

# B) Sentinel consistency has to hold across every layer, not just one
# This is the deeper lesson from the bug you just found: update_role's is not None logic is only correct if every layer feeding it — the input type's default, the resolver, the service — agrees on what "not provided" looks like. A correct implementation at the service layer can still produce a real, silent bug if an earlier layer (the input type, in this case) hands it the wrong sentinel. When reviewing any system with an "unset means don't touch it" convention, check the entire path the value travels, not just the function that ultimately branches on it.

# 8. Small example (demonstrating the bug concretely)
# python
# def update_thing(*, is_default=None):
#     if is_default is not None:
#         print(f"Explicitly setting is_default to {is_default}")
#     else:
#         print("Leaving is_default untouched")

# # Correct input type (default=None):
# def build_input_correct(is_default=None):
#     return is_default

# # Buggy input type (default=False):
# def build_input_buggy(is_default=False):
#     return is_default

# update_thing(is_default=build_input_correct())   # "Leaving is_default untouched" — correct!
# update_thing(is_default=build_input_buggy())      # "Explicitly setting is_default to False" — BUG!
# 9. What you should remember
# @strawberry.input classes are auto-generated, dataclass-like shapes — plain name: type annotations become constructor parameters and attributes automatically, no __init__ needed.
# Never use a mutable literal ([], {}, set()) as a direct default value — use strawberry.field(default_factory=list) in Strawberry inputs, or the param=None + param = param or [] pattern inside plain functions; both solve the identical shared-mutable-default bug.
# An "unset means don't touch it" sentinel must be None consistently at every layer the value passes through — a service correctly written with is not None checks can still be silently broken if the input type upstream defaults to a real value (False) instead of None.
# Compare an input type's field defaults directly against the service function it feeds, not just against its own type hint — Optional[bool] = False looks internally plausible but is wrong the moment you check it against update_role's actual branching logic.
# A default that's "reasonable-looking in isolation" can still be a real, serious bug — this is the same reading discipline you've applied throughout this whole conversation: trust the comparison between related pieces of code more than how any single line reads on its own.