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

# 1. Purpose — Why this exists

# What problem is this solving?
# Every mutation needs to hand back a consistent, predictable shape on completion — not just the raw result (or nothing, on failure), but a structured answer: did it work, here's the object if so, here's what went wrong if not. payloads.py is where those response shapes get declared, mirroring inputs.py's role but for the outgoing half of a mutation.

# Why not just have mutations return UserType directly on success, and let Strawberry's own error mechanism handle failures?
# This is precisely the "payload shape trade-offs" question the framework flags as worth raising. Returning a bare UserType is simpler, but it means a failure has to be represented some other way (an exception bubbling up to GraphQL's generic top-level errors array, which is far less structured — no error codes, no field-level attribution). A payload wrapper ({success, user, errors}) keeps success and failure represented uniformly, in the schema itself, letting a frontend branch on success without needing to inspect a separate, less-typed error channel.

# When is this used?
# Every mutation resolver in mutations.py returns one of these two payload types — UserMutationPayload for single-user actions, BulkUserActionPayload for batch actions.

# What breaks without it?
# Mutations would either return bare types with no structured way to signal failure, or each mutation would invent its own one-off payload shape, losing the consistency a shared vocabulary provides.

# Which side of the network boundary is this on?
# Shape — specifically the outgoing half, the mirror of inputs.py. Every class here describes what a client receives back after a mutation runs, never what it sends.

# 2. Imports — explained like you've never programmed
# python
# from __future__ import annotations
# import strawberry
# from typing import Optional, List
# from lrb.accounts.graphql.types import UserType
# from lrb.core.graphql.errors import MutationError
# from lrb.core.graphql.payloads import BulkActionPayload

# Everything mechanically familiar by now — strawberry, Optional, List. Two imports worth reading carefully for what their paths tell you, applying the same "check where it's really coming from" habit from earlier files:

# from lrb.accounts.graphql.types import UserType — from the accounts app specifically, the exact file you fully walked through two turns ago. This is domain-specific — UserType only makes sense in the context of users.

# from lrb.core.graphql.errors import MutationError and from lrb.core.graphql.payloads import BulkActionPayload — both from core, not accounts. This path tells you something architecturally important before you've even read either class's definition: these are meant to be generic, reusable across every domain in the project, not user-specific. MutationError presumably represents a structured error (likely something like a message and a code field, mirroring your ApplicationError/ErrorCode system) usable by any mutation in the whole schema — orders, roles, companies, not just users. BulkActionPayload likewise is presumably a generic wrapper shaped to carry whatever BulkActionResult produces, usable by any bulk operation across the project, not just the user-related ones you've built.

# 3. Signature — every symbol explained
# python
# @strawberry.type
# class UserMutationPayload:
#     success: bool
#     user: Optional[UserType] = None
#     errors: Optional[List[MutationError]] = None

# @strawberry.type, not @strawberry.input — correctly matching what you learned last turn: this is data going out, so it must use the output-type decorator, not the input one. Mixing these up would be rejected by Strawberry's schema validation, exactly as flagged.

# success: bool — no default value, meaning every payload instance must explicitly state whether the mutation succeeded — there's no ambiguous "unset" state for this field, which is the right call for something this central to how a client should interpret the response.

# user: Optional[UserType] = None — defaults to None, meaning a failed mutation can construct this payload without needing a real user object at all: UserMutationPayload(success=False, user=None, errors=[...]).

# errors: Optional[List[MutationError]] = None — worth pausing on the type of the default here versus what you might expect. Compare this against BulkActionResult's own list fields several turns ago:

# python
# succeeded: list[str] = field(default_factory=list)

# BulkActionResult needed field(default_factory=list) specifically to avoid every instance silently sharing one mutable list. Here, errors: Optional[List[MutationError]] = None sidesteps that exact problem differently — by defaulting to None instead of an empty list. Since None is immutable and can't be "shared and mutated" the way an empty list object could be, this avoids the shared-default trap entirely, without needing field(default_factory=...) at all. This is worth recognizing as a second, equally valid solution to the same underlying problem you learned about with BulkActionResult — rather than forcing an always-present-but-empty list, this design lets "no errors" be represented as None itself.

# 4. Classes

# Is this describing data going OUT or coming IN? Out — the mirror of every class in inputs.py.

# Why is UserMutationPayload one single generic class, rather than a separate LockUserPayload, DemoteOwnerPayload, DeactivateUserPayload, etc., one per mutation — the exact opposite design choice inputs.py made for its single-user inputs?

# This is worth naming directly as a real, interesting tension against what you just learned. inputs.py chose separate, mutation-specific classes (PromoteToOwnerInput, DemoteOwnerInput) specifically so each input's shape could evolve independently. This file chooses the opposite — one shared UserMutationPayload, reused across every single-user mutation.

# Why does that asymmetry make sense, rather than being an inconsistency? Look at what actually varies between mutations on each side. Inputs genuinely differ in what fields they need — LockUserInput needs a duration, DemoteOwnerInput doesn't, UpdateProfileInput needs several editable fields — real, substantive shape differences. Outputs, by contrast, are remarkably uniform across almost every single-user service function you've built: create_user, update_user, lock_user, demote_owner, activate_user — every single one either returns a real User on success or raises an exception on failure. The response shape needed to represent "did this succeed, here's the user if so, here's what went wrong if not" is identical regardless of which specific action was performed. Sharing one payload class here isn't laziness — it's recognizing that the actual variation lives entirely in the input and the service call, not in the shape of a successful or failed response.

# 5. Body

# No methods, no resolvers — same as inputs.py, this file is pure field declarations except for one line worth its own full treatment.

# python
# BulkUserActionPayload = BulkActionPayload

# This is not a class definition — read it exactly as what it is: a plain variable assignment, using the "assignment means read the right side first" rule you've had since the very beginning of this whole series. The right side, BulkActionPayload, is a class — imported at the top of this file, from lrb.core.graphql.payloads. The left side, BulkUserActionPayload, is simply a new name bound to that exact same class — not a new, separate class, not a subclass, not a copy. After this line runs, BulkUserActionPayload and BulkActionPayload are two different names pointing at the literal same class object in memory — the same relationship as two variables both pointing at the same list, except here the "object" happens to be a class rather than a list or a user.

# Why do this at all, instead of just importing BulkActionPayload directly and using that name everywhere in mutations.py? This is a deliberate aliasing pattern, and it serves a real readability purpose: within this accounts-domain file, BulkUserActionPayload is a self-documenting, domain-specific name — anyone reading mutations.py and seeing -> BulkUserActionPayload immediately understands "this returns the standard bulk-action payload, in the context of user actions" without needing to know or care that the underlying implementation is a shared, generic core class. If some other domain (say, orders) later reused the same generic BulkActionPayload for its own bulk mutations, it could alias it as BulkOrderActionPayload — same underlying class, different domain-appropriate name at each call site.

# 6. Beginner questions, answered proactively

# Why does success: bool have no default, while user and errors both default to None?
# Because there's no sensible universal default for "did this succeed" — every payload instance genuinely needs to state it explicitly, one way or the other. user/errors, by contrast, each have an obviously sensible "nothing here" state (None) that applies naturally to one branch (a failure has no user; a success typically has no errors).

# If errors defaults to None, but the mutation recipe you were shown earlier says return Payload(user=None, success=False, errors=[str(e)]) — passing a list — is there a mismatch?
# Worth flagging as a genuine detail to get right when you build mutations.py: the earlier generic recipe used errors=[str(e)] — a list of plain strings. This actual file's field is typed Optional[List[MutationError]] — a list of MutationError objects, not strings. That means when you actually build a mutation resolver against this real payload, you cannot simply do errors=[str(e)] as the earlier generic recipe sketch suggested — you'll need to construct real MutationError instances, presumably something like errors=[MutationError(message=str(e), code=e.code)], matching whatever fields MutationError (defined in lrb.core.graphql.errors, not shown here) actually declares. This is worth confirming against that file directly before writing your first real mutation — the generic recipe was a simplified sketch; this file's actual, stricter typing is what your resolvers need to honor.

# Why is BulkUserActionPayload an alias rather than its own real class with its own fields?
# Because BulkActionResult (and presumably the generic BulkActionPayload it maps to) is already a completely generic, domain-agnostic shape — succeeded/failed lists of IDs and reasons, nothing user-specific baked in. There's nothing about bulk operations on users specifically that needs different fields than bulk operations on any other kind of thing — so there's no reason to duplicate the class, only to give it a more legible name in this file's context.

# 7. Design discussion

# Payload shape trade-offs, applied concretely to UserMutationPayload: the chosen shape (success, user, errors) is straightforward for a frontend to consume — check success first, then either read user or iterate errors. The cost, as you've now identified yourself, is that it requires every mutation resolver to correctly translate a caught ApplicationError/AppValidationError/whatever into a properly-typed MutationError object — a small but real translation step that has to happen consistently across every mutation resolver, or the schema's own type-checking will reject a resolver that tries to hand back a plain string where a MutationError was declared.

# One shared payload vs. one payload per mutation — the trade-off, stated plainly, now that you've seen both extremes in this project: inputs.py's "one input per mutation" approach optimizes for independent evolvability at the cost of more classes to maintain. payloads.py's "one shared payload" approach optimizes for consistency and less duplication, accepting the (currently negligible) cost that if some future single-user mutation ever needed to return something beyond "success, user, errors" — say, a mutation that also needs to return a freshly-generated password reset token — it would either need to extend UserMutationPayload for everyone, or break from the shared pattern for that one case. Neither trade-off is universally correct; each file made the choice that fit what it was actually describing.

# 8. DIY Recipe — building a payloads file like this yourself
# Before creating a payload, ask whether the actual response shape genuinely varies across the mutations that would use it. If every mutation in a family returns "success, the object, or errors," share one payload class — don't create near-duplicate classes for no structural reason.
# Keep truly generic response shapes (bulk results, structured errors) in a core module, importable and reusable by every domain, rather than reimplementing them per app.
# Use Optional[T] = None, not field(default_factory=list), when the "empty" state is naturally representable as None rather than an empty collection — it's a simpler, equally-safe alternative to the BulkActionResult mutable-default pattern.
# Alias a generic core class with a domain-appropriate name when reusing it in a specific app's GraphQL layer, purely for the readability of that file's own resolvers and callers.
# When building mutation resolvers against a payload, always check the payload's actual declared field types (List[MutationError], not List[str]) rather than trusting a generic sketch/recipe verbatim — construct exactly what the schema demands.
# 9. General pattern recognition

# The "uniform success/failure payload" pattern:

# python
# @strawberry.type
# class <Domain>MutationPayload:
#     success: bool
#     <result_object>: Optional[<ResultType>] = None
#     errors: Optional[List[<StructuredErrorType>]] = None

# Plus the "generic core type, domain alias" pattern:

# python
# <DomainSpecificName> = <GenericCoreClass>

# Both are reusable well beyond this project — any GraphQL schema with more than a handful of mutations benefits from recognizing when a shared payload shape is actually sufficient, rather than defaulting to "one payload class per mutation" out of habit.

# 10. Real project usage
# python
# @strawberry.mutation
# def lock_user(self, input: LockUserInput) -> UserMutationPayload:
#     try:
#         user = lock_user(user_id=str(input.user_id), duration_minutes=input.duration_minutes)
#         return UserMutationPayload(success=True, user=user, errors=None)
#     except ApplicationError as e:
#         return UserMutationPayload(
#             success=False,
#             user=None,
#             errors=[MutationError(message=str(e), code=e.code)],
#         )

# @strawberry.mutation
# def bulk_lock_users(self, input: BulkLockUserInput) -> BulkUserActionPayload:
#     actor = get_current_user(self.info)
#     result = bulk_lock_users(
#         user_ids=[str(uid) for uid in input.user_ids],
#         company_id=actor.company_id,
#         current_user_id=str(actor.id),
#         duration_minutes=input.duration_minutes,
#     )
#     return BulkUserActionPayload(succeeded=result.succeeded, failed=result.failed)

# Notice the second example reuses LockUserInput's duration_minutes naming — worth double-checking against the naming inconsistency you caught yourself in bulk_lock_users's service function (duration_time vs. duration_minutes) a few turns back, since the GraphQL layer's naming should track whichever one the service layer settles on.

# 11. Common beginner mistakes

# ❌ Constructing errors=[str(e)] against this payload's actual List[MutationError] type — a type mismatch the schema (or at least a type checker) should catch, but easy to write by habit if you're following the earlier, simplified generic recipe literally instead of checking the real payload's field types.

# ❌ Creating a new payload class per mutation reflexively, without first checking whether an existing shared payload already covers the exact same shape.

# ❌ Forgetting that BulkUserActionPayload is just an alias, and accidentally defining a second, separate class with slightly different fields under a similar name elsewhere — reintroducing exactly the duplication the alias was meant to prevent.

# 12. Think like the original developer
# What problem am I solving? "Give every user-related mutation a consistent, typed way to report success-with-result or failure-with-structured-errors, without inventing a new shape per mutation where the actual response structure never varies."
# What inputs will I receive? Not applicable — this file describes output shape only.
# What could go wrong? A mutation resolver constructing this payload with the wrong error type (plain strings instead of MutationError instances); creating redundant payload classes where one shared shape already suffices.
# How should I report errors? Via the errors field, populated with real, structured MutationError instances — translating whatever ApplicationError/ErrorCode the service layer raised into this GraphQL-facing structured form.
# What should happen if everything's right? success=True, the real result object attached, errors left None — a clean, predictable shape a frontend can branch on without ambiguity.