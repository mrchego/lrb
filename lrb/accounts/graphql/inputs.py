import strawberry
from typing import List, Optional
from strawberry.file_uploads import Upload

@strawberry.input
class UpdateProfileInput:
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[Upload] = None

@strawberry.input
class AdminUpdateUserInput:
    user_id: strawberry.ID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[Upload] = None

@strawberry.input
class UserIdInput:
    user_id: strawberry.ID

@strawberry.input
class LockUserInput:
    user_id: strawberry.ID
    duration_minutes: int = 15

@strawberry.input
class BulkUserIdsInput:
    user_ids: List[strawberry.ID]

@strawberry.input
class BulkLockUserInput:
    user_ids: List[strawberry.ID]
    duration_minutes: int = 15

@strawberry.input
class PromoteToOwnerInput:
    user_id: strawberry.ID

@strawberry.input
class DemoteOwnerInput:
    user_id: strawberry.ID

# New concept: @strawberry.type vs @strawberry.input

# In the last file, everything was @strawberry.type — those describe data going OUT of your server, to the client (what a User looks like when GraphQL sends it back).

# @strawberry.input describes data coming IN, from the client to your server — the arguments a client must send when calling a mutation (an action that changes something, like "update this profile" or "lock this user"). GraphQL requires these to be separate, named types (not just loose function arguments) — this makes the API self-documenting: a client tool can look at UpdateProfileInput and know exactly what fields are allowed, what's optional, and what type each one is.

# UpdateProfileInput — the full pattern
# python
# @strawberry.input
# class UpdateProfileInput:
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     phone: Optional[str] = None
#     avatar: Optional[Upload] = None

# What is it / How is it written?

# @strawberry.input — decorator that registers this class as a GraphQL input type.
# Each line has the shape: field_name: Optional[TYPE] = None. Let's break that into three parts:
# field_name: Optional[TYPE] — the type hint. Optional[str] means "a string, or nothing at all."
# = None — a default value. This is Python syntax for "if the caller doesn't provide this, use None instead." Without a default, Python (and Strawberry) would require the caller to always supply that field.
# Together, Optional[X] = None is a very common combo pattern: it means "this field is truly optional — the client can leave it out entirely, and it'll be treated as None."

# Why is every field optional here?
# Think about what "update profile" means: a user might want to change only their phone number, and leave their name alone. If first_name were required, every update request would be forced to resend the name even when it's not changing. Making every field Optional[str] = None lets the resolver logic say "if this field was sent, update it; if it's None, leave that column untouched" — a very common partial update pattern.

# Advanced concept: Optional[Upload] for a file field
# Even the avatar upload is optional and defaults to None — the user isn't forced to re-upload a photo just to change their phone number. This is consistent with the "partial update" idea above: every field in this input answers the question "did the client want to change this?" rather than "what is the complete new state?"

# AdminUpdateUserInput — same pattern, one addition
# python
# @strawberry.input
# class AdminUpdateUserInput:
#     user_id: strawberry.ID
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     phone: Optional[str] = None
#     avatar: Optional[Upload] = None

# Identical to UpdateProfileInput, but with one new required field at the top: user_id: strawberry.ID — no Optional, no default. This makes sense: when you update your own profile, the server already knows who you are (from your session/login) — there's no user_id needed. But when an admin updates someone else's profile, the server has no way to know which user is being edited unless the admin tells it. That's exactly why this is a separate input type instead of reusing UpdateProfileInput — the two mutations have genuinely different required data, driven by who is doing the action.

# Notice this connects directly to your RBAC conventions: this input type is almost certainly paired with a mutation that calls require_permission("some_codename") before doing anything, since normal users shouldn't be able to send an AdminUpdateUserInput.

# UserIdInput — the minimal "target one user" shape
# python
# @strawberry.input
# class UserIdInput:
#     user_id: strawberry.ID

# Just one required field. This is the simplest possible input: "which user are we acting on?" No optional fields, because there's nothing to configure — the mutation using this either does one fixed thing (like "deactivate this user") or doesn't.

# LockUserInput — a required-style field with a default
# python
# @strawberry.input
# class LockUserInput:
#     user_id: strawberry.ID
#     duration_minutes: int = 15

# New pattern: duration_minutes: int = 15. This is not Optional — the type is plain int, not Optional[int]. But it still has = 15. The difference from Optional[str] = None matters:

# Optional[str] = None → "this field can be missing, and if so, means nothing."
# int = 15 → "this field can be missing, and if so, means exactly 15 (a real, meaningful number), not the absence of a number."

# This is a default parameter, not an optional-value pattern. It's used when there's a sensible "normal" value (lock someone out for 15 minutes) that the caller usually doesn't need to think about, but can override if they want a different duration.

# BulkUserIdsInput and BulkLockUserInput — operating on many users at once
# python
# @strawberry.input
# class BulkUserIdsInput:
#     user_ids: List[strawberry.ID]

# @strawberry.input
# class BulkLockUserInput:
#     user_ids: List[strawberry.ID]
#     duration_minutes: int = 15

# New pattern: List[strawberry.ID] — instead of one ID, a list of IDs. This is the plural version of UserIdInput/LockUserInput — used for admin actions that apply to many users at once (e.g., "lock these 5 accounts"). BulkLockUserInput is literally BulkUserIdsInput + the same duration_minutes default seen in LockUserInput — the developer combined two smaller patterns you've already learned.

# PromoteToOwnerInput and DemoteOwnerInput — same shape, different meaning
# python
# @strawberry.input
# class PromoteToOwnerInput:
#     user_id: strawberry.ID

# @strawberry.input
# class DemoteOwnerInput:
#     user_id: strawberry.ID

# These are structurally identical to UserIdInput — one required user_id. Why not just reuse UserIdInput for these too?

# This is a real design choice, worth sitting with: Strawberry/Python would happily let you reuse UserIdInput everywhere. But the developer chose to make separate, specifically-named input types. Reasons this is often the right call:

# Clarity in the GraphQL schema — a client browsing your API sees a mutation called promoteToOwner(input: PromoteToOwnerInput!), which is self-explanatory, versus promoteToOwner(input: UserIdInput!), which is vague and reused everywhere.
# Room to grow independently. If tomorrow "promote to owner" needs an extra field (like a confirmation reason), you only change PromoteToOwnerInput — you don't risk breaking every other mutation that happened to share UserIdInput.
# Given this is require_owner()-gated territory (owner promotion/demotion is about as sensitive as actions get in an RBAC system), keeping each action's input isolated also makes it easier to reason about security per-mutation, rather than worrying about shared-type side effects.
# Connections

# Each input type here pairs with exactly one mutation resolver elsewhere in your schema (e.g., lockUser(input: LockUserInput!) -> SimpleMutationPayload). Following your project's service/selector separation, the resolver itself should stay thin: unpack the input's fields and hand them as keyword arguments to a service function (e.g., lock_user(user_id=input.user_id, duration_minutes=input.duration_minutes)), which then does the real work inside @transaction.atomic.

# What I should remember
# @strawberry.type = data going out, @strawberry.input = data coming in. They look similar but serve opposite directions of the request.
# Optional[X] = None means "truly absent/no change"; X = default_value (like int = 15) means "no override, use this sensible default." Same syntax shape, different meaning — read the type carefully.
# List[Type] is the plural version of a single field — a fast way to spot "this input supports bulk actions."
# A required field has no = something; adding a default (= None or a real value) is what makes a field optional. Field order and defaults directly express what the caller must vs may provide.
# It's fine (and often good design) to create near-duplicate input types for different actions rather than reusing one generic type everywhere — it keeps each mutation's contract clear and lets them evolve independently, especially for sensitive, permission-gated actions.