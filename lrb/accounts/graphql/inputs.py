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


# 1. Purpose — Why this exists, plus the new question

# What problem is this solving?
# Every mutation you've built in the service layer — update_user, lock_user, demote_owner, bulk_lock_users — takes keyword arguments. GraphQL doesn't let a client send "keyword arguments" directly; it needs a named, typed shape describing exactly what fields a mutation accepts. inputs.py is where each of those shapes gets declared, one per mutation (or shared across a small family of near-identical mutations).

# Why not just let each mutation resolver accept raw scalar arguments directly (def lock_user(self, user_id: str, duration_minutes: int)), skipping Input classes entirely? Strawberry does actually support this for simple cases — but a dedicated Input class becomes valuable the moment a mutation takes several related fields together, since it gives the client (and the schema itself) one named, reusable, self-documenting object instead of a growing list of loose arguments — exactly why UpdateProfileInput bundles four fields instead of the mutation taking four separate parameters.

# When is this used?
# Every mutation resolver in mutations.py declares its argument using one of these Input types as its parameter type.

# What breaks without it?
# Either mutations end up with unwieldy loose-argument signatures, or — worse — different mutations doing conceptually similar things end up with inconsistently-shaped, one-off argument sets instead of a shared, predictable vocabulary.

# Which side of the network boundary is this on?
# Entirely shape, and specifically the incoming half of shape — the mirror image of types.py. Every class here describes what a client sends in, never what comes back out.

# 2. Imports — explained like you've never programmed
# python
# import strawberry
# from typing import List, Optional
# from strawberry.file_uploads import Upload

# strawberry, List, Optional — all familiar. from strawberry.file_uploads import Upload is new — this is Strawberry's special type specifically for accepting a file upload as a GraphQL argument (used here for avatar). It's worth recognizing as its own small "family" within the GraphQL import vocabulary from the new framework's table — not a shape-describing tool, not a resolver tool, but a scalar type representing "a file, sent over the network as part of a multipart request," which GraphQL's plain type system (strings, ints, IDs) has no native way to express on its own.

# 3. Signature — the new symbol, @strawberry.input
# python
# @strawberry.input
# class UpdateProfileInput:
#     first_name: Optional[str] = None
#     ...

# What does this class look like without the decorator? A plain container of optional fields with defaults — structurally identical in shape to a dataclass, similar to BulkActionResult from several turns ago, just without the methods.

# What does the decorator add? It registers this class specifically as an input type in the schema — distinct from @strawberry.type, which registers an output shape. This distinction genuinely matters to GraphQL itself, not just to your own code organization: a GraphQL schema enforces that types used as mutation arguments must be declared as inputs, and types used as return values must be declared as regular types — you cannot use one where the other is expected, even if the fields look identical. This is a real, enforced rule of the GraphQL type system, not a convention you're choosing to follow.

# 4. Classes — the new GraphQL-specific questions, applied to nine classes at once

# Is each class describing data going OUT or coming IN? Every single class in this file is data coming in — the direct mirror of the previous file, which was entirely data going out. This is worth confirming as a genuinely useful sanity check whenever you open a new GraphQL file: one glance at whether it's @strawberry.type or @strawberry.input throughout tells you immediately which direction across the network boundary you're reading.

# Why so many small, near-identical input classes (UserIdInput, PromoteToOwnerInput, DemoteOwnerInput are all literally the same single field) instead of one shared UserIdInput reused everywhere a mutation only needs a user ID?

# This is worth sitting with as a genuine design question, not assuming it's simply redundant. Two real considerations cut in opposite directions here:

# In favor of reusing UserIdInput everywhere: less duplication, one shape to maintain.
# In favor of separate, mutation-specific input types (as this file does): each mutation gets its own named, independently-evolvable shape. If promoteToOwner later needs an extra field (say, a reason/audit note) but demoteOwner doesn't, having them as separate classes means you extend PromoteToOwnerInput without touching DemoteOwnerInput at all — reusing one shared UserIdInput for both would force an awkward choice between adding an unused field to demoteOwner's input or breaking the "one shared shape" convenience the moment the two mutations' needs diverge even slightly.

# This file has chosen the second approach consistently — worth recognizing as a deliberate trade-off (a little more boilerplate now, in exchange for each mutation's input being free to evolve independently later), not an oversight.

# 5. Body — nothing to read line-by-line, and that's the point

# There are no resolvers, no methods, no logic anywhere in this file — every class is pure field declarations. This is worth stating explicitly as its own lesson from the new framework: Step 0 for resolver bodies ("what triggered this running") doesn't apply here at all, because nothing in this file runs in the sense a resolver does. These classes exist purely to be matched against — Strawberry uses them to validate and parse whatever JSON payload a client sends, mapping it onto these fields before a mutation resolver ever sees it.

# 6. Beginner questions — checking each input against the service function it feeds

# This is the most valuable check to run on a file like this, and it's worth doing systematically rather than glancing — cross-reference each Input class against the actual service function signature you already fully understand.

# LockUserInput vs. lock_user(*, user_id: str, duration_minutes: int = 15):

# python
# @strawberry.input
# class LockUserInput:
#     user_id: strawberry.ID
#     duration_minutes: int = 15

# Matches exactly — same field, same default value (15), consistent with the service function it feeds. This is exactly what you'd want to see: the input's default mirrors the service's default, so a client omitting duration_minutes gets the same behavior whether the omission happens at the GraphQL layer or the Python layer.

# BulkLockUserInput vs. bulk_lock_users(*, user_ids: Iterable[str], company_id: str, current_user_id: str, duration_minutes: int = 15):

# python
# @strawberry.input
# class BulkLockUserInput:
#     user_ids: List[strawberry.ID]
#     duration_minutes: int = 15

# Notice company_id and current_user_id are correctly absent from this input — and this is worth confirming as intentional, not a missing-field bug, by applying exactly what you learned two turns ago about where current_user_id actually comes from: it's derived server-side, from get_current_user(info) in the resolver, never something a client should be trusted to supply directly (a client claiming to be a different user than they actually are would be a serious security hole). Same reasoning for company_id — that almost certainly comes from actor.company_id in the resolver, not from client input, for the same trust reason. A client should never be allowed to directly assert "which company" or "which user" they are — those facts come from authentication, not from a request body.

# AdminUpdateUserInput vs. update_user(*, user_id, first_name=None, last_name=None, phone=None, avatar=None, company=None, email=None):

# python
# @strawberry.input
# class AdminUpdateUserInput:
#     user_id: strawberry.ID
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     phone: Optional[str] = None
#     avatar: Optional[Upload] = None

# Worth flagging as a real, open question rather than a confirmed bug: update_user's own signature accepts company and email as updatable fields, but neither appears here. Is that deliberate (perhaps changing a user's company or email requires a different, more specific mutation, with its own dedicated safeguards — email changes in particular often warrant re-verification) or an oversight where this input simply hasn't caught up with everything update_user supports? This is exactly the kind of mismatch worth confirming with whoever owns the mutation layer — the framework's own recipe says "one field per keyword argument the service function needs," and right now this input has fewer fields than the service function accepts.

# UpdateProfileInput — the self-service counterpart, missing email too:
# Here, the omission reads as far more clearly intentional — a self-service profile update deliberately excluding email makes real sense (email changes often need verification flows, shouldn't be a silent one-field update), and this input also correctly has no user_id field at all, unlike AdminUpdateUserInput — because a self-service mutation should always act on "whoever is currently authenticated," never on an arbitrary ID a client could substitute to edit someone else's profile. This is worth naming as the single most important structural difference between these two nearly-identical-looking inputs: AdminUpdateUserInput includes user_id because a staff member needs to specify whose profile they're editing; UpdateProfileInput omits it because a regular user should only ever be able to edit their own, with "their own" resolved server-side via get_current_user(info), exactly like current_user_id was.

# BulkUserIdsInput — generic, presumably shared across several bulk mutations (bulkUnlockUsers, bulkRestoreUsers, bulkForcePasswordReset — all the bulk functions that need only a list of IDs and get their company_id/current_user_id from context): a single field, reused wherever a bulk mutation needs nothing more than a batch of target IDs. This is exactly the "shared reusable input" approach the earlier design question considered — and it makes sense specifically because these particular mutations genuinely have identical input needs, unlike the single-user mutations discussed above, where the needs diverge just enough to justify separate classes.

# Why is this argument inside an Input class instead of just a raw parameter, for something as simple as UserIdInput's single field?
# Even a one-field input earns its place for schema consistency — GraphQL conventions typically prefer every mutation take a single named input argument (mutation { lockUser(input: LockUserInput!) { ... } }) rather than mixing bare scalar arguments and object arguments across different mutations in the same schema — predictability for API consumers matters more here than saving a few lines of boilerplate for the smallest cases.

# 7. Design discussion

# Thin resolver vs. fat resolver, applied to inputs specifically: the framework's own flagged mistake — "putting validation logic in inputs.py instead of leaving it to the service layer" — and this file passes that check cleanly. There's no validation anywhere here; every field is just a type and an optional default. validate_email, validate_phone_number, validate_password_strength all still live exclusively in your service layer, never duplicated here. That's correct discipline, worth confirming explicitly rather than assuming by omission.

# The AdminUpdateUserInput/update_user field mismatch, revisited as a design cost: if this mismatch is unintentional, it represents exactly the kind of drift the framework warns about — the input's shape silently falling out of sync with what the service function actually supports, discovered only when someone tries to build a mutation that needs to update a user's company through this input and finds it structurally impossible without first extending the input class.

# 8. DIY Recipe — building input classes like this yourself
# Start from the service function's own keyword arguments — but exclude anything that should be derived from authentication/context rather than supplied by the client (company_id, current_user_id, anything establishing "who is asking" or "which company they belong to").
# Match each input field's type and default value exactly to the service function's own type hint and default — a mismatch here (like a missing default, or a wrongly-typed field) creates confusing behavior differences between what the schema promises and what the service actually does.
# Decide deliberately, per mutation, whether to reuse a shared input shape (like BulkUserIdsInput) or give it its own dedicated class — reuse when the needs are identical now and likely to stay that way; separate when you can already imagine the two mutations' needs diverging.
# Never put validation logic here — inputs describe shape, never rules; that discipline is what keeps validation living in exactly one place (the service layer) instead of two places that can drift apart.
# For anything representing "act on myself" vs. "act on someone else," use the presence or absence of an ID field itself as the signal — no ID means "the authenticated caller," an explicit ID means "a staff member specifying a target."
# 9. General pattern recognition

# The "input shape mirrors service keyword arguments, minus context-derived fields" pattern:

# python
# @strawberry.input
# class <Verb><Noun>Input:
#     <required identifying field(s)>          # if targeting someone other than the caller
#     <optional field>: Optional[T] = <matching service default>
#     # never: company_id, current_user_id, or anything else derivable from auth context

# Plus the "self vs. admin" pairing pattern you can now recognize on sight: two inputs targeting conceptually the same action, distinguished by whether a target ID is present.

# 10. Real project usage

# Directly consumed by mutations.py, exactly per the framework's recipe:

# python
# @strawberry.mutation
# def lock_user(self, input: LockUserInput) -> LockUserPayload:
#     try:
#         user = lock_user(user_id=str(input.user_id), duration_minutes=input.duration_minutes)
#         return LockUserPayload(user=user, success=True, errors=[])
#     except ApplicationError as e:
#         return LockUserPayload(user=None, success=False, errors=[str(e)])

# Notice str(input.user_id) — strawberry.ID needs converting to a plain string before it reaches your service layer, which expects user_id: str throughout, exactly matching the type-tracing discipline you've been applying all along.

# 11. Common beginner mistakes

# ❌ Letting a client supply company_id or current_user_id directly in an input — a serious trust boundary violation; those must always be derived server-side from the authenticated request.

# ❌ An input silently falling out of sync with the service function's actual accepted fields — worth checking explicitly, as AdminUpdateUserInput prompted here, any time the two are updated separately.

# ❌ Putting an @strawberry.type where an @strawberry.input was needed, or vice versa — GraphQL's schema will reject this outright, since the two are not interchangeable despite looking structurally identical in code.

# ❌ Adding validation logic into an input class "since it's right there" — creates a second place validation can drift out of sync with the service layer's own rules.

# 12. Think like the original developer
# What problem am I solving? "Give every mutation a named, typed, client-facing shape for its arguments, matching what the underlying service function actually needs — and nothing the client shouldn't be trusted to supply themselves."
# What inputs will I receive? Whatever shape the client's GraphQL request sends — Strawberry validates it against these declared fields before a resolver ever runs.
# What could go wrong? A client attempting to impersonate another user or company via a field that shouldn't exist; an input drifting out of sync with its service function's real capabilities.
# How should I report errors? Not this file's job — malformed input (wrong type, missing required field) is rejected by Strawberry's own schema validation before your code runs at all; business-rule errors are entirely payloads.py's and the mutation resolvers' concern.
# What should happen if everything's right? A cleanly-typed object lands in the mutation resolver, containing exactly the fields the service function needs, with context-derived fields (who's asking, which company) supplied separately and safely by the resolver itself.