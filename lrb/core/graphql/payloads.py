from typing import List, Optional
import strawberry
from .errors  import MutationError

@strawberry.type
class SimpleMutationPayload:
    success: bool
    errors: Optional[List[MutationError]] = None
    
    
@strawberry.type
class BulkActionFailure:
    user_id: strawberry.ID
    reason: str


@strawberry.type
class BulkActionPayload:
    success: bool
    succeeded_ids: List[strawberry.ID]
    failed: List[BulkActionFailure]
    
def to_bulk_payload(result) -> BulkActionPayload:
    return BulkActionPayload(
        success=len(result.failed) == 0,
        succeeded_ids=result.succeeded,
        failed=[BulkActionFailure(user_id=f["user_id"], reason=f["reason"]) for f in result.failed],
    )
    
    
# 1. Purpose (Why this exists)

# What problem is this solving? Every mutation in your GraphQL schema needs to send back a response shape the frontend can rely on — did it succeed? If not, what went wrong? For bulk operations specifically (recall BulkActionResult from earlier — the internal Python object tracking successes/failures), the frontend needs that same information, but as an actual GraphQL type it can query fields from over the network, not a plain Python object. This file provides two response shapes — one for simple, single-item mutations (SimpleMutationPayload), and one specifically for bulk operations (BulkActionPayload) — plus a function that converts your internal BulkActionResult into the GraphQL-facing BulkActionPayload.

# Why couldn't we just write the logic directly? Same argument as format_application_error — without one shared, consistent payload shape, every mutation resolver would invent its own slightly different response format, and the frontend would have to handle dozens of inconsistent shapes instead of one predictable pattern.

# When is this used in a real project? Every mutation returns one of these payload types (or something similar) as its GraphQL return type — createUser might return SimpleMutationPayload, while bulkDeactivateUsers would return BulkActionPayload.

# What happens if this doesn't exist? Inconsistent, unpredictable mutation response shapes across your schema — a frontend developer would have to learn a slightly different "did it work, what failed" pattern for every single mutation instead of one they can rely on everywhere.

# 2. Imports — explained like you've never programmed
# python
# from typing import List, Optional

# Same built-in typing toolbox as before. List is a type hint meaning "a list containing this specific type of thing" — this is the older-style way of writing what more recent Python lets you write as plain list[...] (both mean the same thing; List from typing is the more traditional/compatible form, still very common, especially in codebases that support slightly older Python versions or that were written before list[...] syntax was added). Optional, as before, means "this or None."

# python
# import strawberry

# Same core Strawberry package.

# python
# from .errors import MutationError

# A relative import again (the . before errors) — "look for errors.py in this same folder," which is where MutationError and format_application_error from the last file live.

# 3 & 4. SimpleMutationPayload
# python
# @strawberry.type
# class SimpleMutationPayload:
#     success: bool
#     errors: Optional[List[MutationError]] = None

# Why a class, and why @strawberry.type again? Same reasoning as MutationError — this needs to actually be part of your GraphQL schema, queryable by the frontend, so it needs Strawberry's own decorator, not @dataclass.

# Field by field:

# success: bool — required, True/False, telling the frontend immediately whether the mutation worked.
# errors: Optional[List[MutationError]] = None — read this type hint from the outside in: Optional[...] = "this whole thing might be None"; List[MutationError] = "or, if it's not None, it's a list of MutationError objects" (the type you built in the last file). Defaults to None, meaning "if the mutation succeeded, there's no reason to even build an empty list — just leave this blank."

# Why one payload type shared across many different mutations, rather than a custom one per mutation? Because most simple mutations only ever need to communicate the same two things: did it work, and if not, why. SimpleMutationPayload is deliberately generic enough to cover createUser, deleteRole, updateCompany, and dozens more, without each needing its own bespoke response type.

# BulkActionFailure
# python
# @strawberry.type
# class BulkActionFailure:
#     user_id: strawberry.ID
#     reason: str

# Why a brand-new type, when MutationError already exists? Worth noticing this deliberately: MutationError has message, code, field — built for describing "one thing went wrong with one mutation." BulkActionFailure has user_id, reason — built for describing "this specific item, among many, failed, and here's why." These represent genuinely different concepts: one mutation-wide error, versus one failed item inside a list of many attempted items. Reusing MutationError here would be a poor fit — it has no user_id field to say which item failed, and it carries a code/field that don't cleanly apply to "item 42 out of 100 failed."

# strawberry.ID, a new type worth explaining: this is a Strawberry-specific type representing a GraphQL ID — a special scalar type in the GraphQL spec meant specifically for unique identifiers. It's serialized as a string over the wire, but marking it as ID (rather than plain str) tells GraphQL clients/tools "this specific value identifies something uniquely" — useful for client-side caching tools (like Apollo or Relay) that specifically look for ID fields to know how to cache/refetch objects correctly.

# BulkActionPayload
# python
# @strawberry.type
# class BulkActionPayload:
#     success: bool
#     succeeded_ids: List[strawberry.ID]
#     failed: List[BulkActionFailure]

# Mirrors the shape of your internal BulkActionResult, but GraphQL-facing:

# success: bool — a summary flag; true if the whole bulk operation had zero failures.
# succeeded_ids: List[strawberry.ID] — every ID that succeeded, as a plain list of GraphQL IDs.
# failed: List[BulkActionFailure] — every failure, each one carrying its own user_id and reason.
# 5. to_bulk_payload — the body, line by line
# python
# def to_bulk_payload(result) -> BulkActionPayload:

# Signature: one input, result — notice, unlike format_application_error, this parameter has no type hint at all. We'll flag this as a real inconsistency below. -> BulkActionPayload promises the return type.

# python
#     return BulkActionPayload(
#         success=len(result.failed) == 0,

# Right side, then whole line: len(result.failed) — counts how many items are in result.failed (recall result is expected to be a BulkActionResult, whose .failed is a list of dictionaries). == 0 checks "is that count exactly zero?" — producing True if nothing failed, False otherwise. Whole line: "the whole bulk operation counts as successful only if the failure list is completely empty."

# python
#         succeeded_ids=result.succeeded,

# Directly copies result.succeeded (already a plain list of ID strings from BulkActionResult) straight across — no transformation needed, since both sides expect "a list of IDs."

# python
#         failed=[BulkActionFailure(user_id=f["user_id"], reason=f["reason"]) for f in result.failed],
#     )

# This is a list comprehension — a compact way of writing "build a new list by transforming every item in an existing list," worth breaking down piece by piece:

# for f in result.failed — loop over every dictionary in result.failed (recall each one looks like {"user_id": "...", "reason": "..."}), calling each one f as we go.
# BulkActionFailure(user_id=f["user_id"], reason=f["reason"]) — for each dictionary f, build one new BulkActionFailure GraphQL object, pulling the two values out of the dictionary by key and placing them into the object's fields.
# The surrounding [...] collects every one of those newly-built objects into a brand-new list.

# Whole line, in plain English: "for every failure dictionary in result.failed, build a proper BulkActionFailure GraphQL object out of it, and collect all of those into a list."

# 6. Beginner questions, answered

# Why a list comprehension instead of a regular for loop? They do the same thing — a list comprehension is just a shorter way of writing:

# python
# failed_list = []
# for f in result.failed:
#     failed_list.append(BulkActionFailure(user_id=f["user_id"], reason=f["reason"]))

# List comprehensions are common in Python specifically because "build a new list by transforming each item in an existing one" is such a frequent pattern that Python gives it dedicated, more compact syntax.

# Why square brackets around the whole comprehension? Same reason as any list literal — square brackets mean "this is a list."

# Why f["user_id"] instead of f.user_id? Because f here is a plain Python dictionary (recall add_failure built it as {"user_id": ..., "reason": ...}), and dictionaries use square-bracket key lookup (dict["key"]), not dot access. Dot access (f.user_id) is for objects with actual named attributes — a dictionary doesn't have those; it has keys.

# 7. Design Discussion — the missing type hint

# Why does result have no type hint, when every other function we've reviewed carefully type-hints its inputs?

# This is worth flagging as a real, if minor, inconsistency. Given this function is clearly meant to receive a BulkActionResult (from the earlier file), the honest, consistent signature would be:

# python
# from .results import BulkActionResult

# def to_bulk_payload(result: BulkActionResult) -> BulkActionPayload:

# Why does this matter beyond just "being thorough"? Type hints here aren't just documentation — they let your editor/IDE and tools like mypy catch a mistake before running the code. If someone accidentally called to_bulk_payload(some_unrelated_object), a proper type hint gives you a chance for a tool to flag that mismatch ahead of time. Without it, the mistake would only surface at runtime, the moment the function tries result.failed and that attribute doesn't exist — the exact same category of risk we discussed for avatar_upload_path's instance parameter.

# 8. DIY Recipe — How to Build Your Own GraphQL Payload + Converter Pair
# Design the GraphQL-facing type first, thinking only about what the frontend actually needs to display (success flag, relevant IDs, structured failure info) — not what your internal Python object happens to look like.
# Keep bulk/list-shaped results using their own dedicated small type (like BulkActionFailure) rather than reusing a general-purpose error type that doesn't quite fit.
# Write one small converter function, always type-hinted on both sides (internal_type -> GraphQLType), that maps your internal object's fields onto the GraphQL type's fields.
# Use a list comprehension when transforming a list of internal items into a list of GraphQL objects — this is the standard, idiomatic Python shape for that exact situation.
# Compute derived fields (like success) inside the converter, not by asking every caller to compute it themselves — keeping that logic in one centralized place.
# 9. General Pattern Recognition

# This file continues the exact same "translate at the boundary" shape from format_application_error — but applied to a whole response, not just an error:

# Internal result object (BulkActionResult)
#        ↓
# One converter function (to_bulk_payload)
#        ↓
# GraphQL-facing payload type (BulkActionPayload)

# Recognize this pattern anywhere you see "an internal representation" paired with "a small function that only exists to reshape it for an external audience" — it's one of the most common shapes in any layered application, appearing at every boundary between two different "worlds" (Python ↔ GraphQL, database rows ↔ API responses, internal models ↔ external partner APIs).

# 10. Real project usage

# A bulk mutation resolver in your schema would look roughly like:

# python
# def bulk_deactivate_users(self, info, user_ids: List[strawberry.ID]) -> BulkActionPayload:
#     result = deactivate_users_service(user_ids=user_ids)  # returns a BulkActionResult
#     return to_bulk_payload(result)

# — the resolver stays thin (matching your project's established "mutations are thin orchestration layers" convention), delegating the real work to a service, and delegating the response-shaping to this converter.

# 11. Common beginner mistakes
# ❌ Missing type hints on converter function inputs — exactly the inconsistency flagged above, losing early error-catching.
# ❌ Reusing a general-purpose error type (MutationError) for a fundamentally different concept (per-item bulk failures) just because it already exists, instead of building a purpose-fit type like BulkActionFailure.
# ❌ Forgetting Optional[...] on fields (like SimpleMutationPayload.errors) that genuinely might be absent — breaking client expectations.
# ❌ Computing success inconsistently across different mutations (some checking len(failed) == 0, others checking something slightly different) instead of centralizing that logic in one converter function per payload type.
# 12. Think like the original developer
# "Every mutation needs to tell the frontend if it worked, and if not, why — I'll build one generic payload type most simple mutations can share."
# "Bulk operations are different — they need per-item results, not just one overall error, so they need their own dedicated payload shape."
# "For each failed item in a bulk operation, I need to know which item failed and why — a small, purpose-built type capturing exactly those two things is cleaner than forcing my general-purpose error type to awkwardly fit this different situation."
# "I already have an internal Python object (BulkActionResult) tracking success/failure — I just need one small function whose only job is reshaping that into the GraphQL type the frontend will actually receive."
# "Whether the whole operation 'succeeded' isn't something I need to track separately — I can derive it directly from whether the failure list is empty, computed once, centrally, inside the converter."