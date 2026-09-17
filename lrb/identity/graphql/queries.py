from typing import Optional

import strawberry

from lrb.accounts.selectors.get_current_user import get_current_user
from lrb.identity.graphql.types import SessionType
from lrb.identity.selectors.get_active_session import get_active_session


@strawberry.type
class SessionQuery:
    @strawberry.field
    def session(self, info: strawberry.Info) -> Optional[SessionType]:
        user = get_current_user(info)
        if not user:
            return None
        data = get_active_session(user_id=str(user.id))
        return SessionType(
            user_id=data["user_id"],
            active=data["active"],
            created_at=data["created_at"],
        )


# 1. Purpose

# This is a GraphQL Query — the read-side counterpart to everything you've built up with mutations today. SessionQuery defines a queryable field, session, that lets a client ask "am I logged in right now, and what does my session look like?" This is the resolver you predicted while reading SessionType two files ago — the piece that actually turns get_active_session's stub dictionary into a real SessionType object the API can return.

# 2. Imports — two new ones
# python
# from lrb.accounts.selectors.get_current_user import get_current_user

# Another selector, following the same folder convention you already know (accounts.selectors, read-only, no side effects). Its name and how it's used below (get_current_user(info)) strongly suggest it pulls the currently-authenticated user out of the request — likely reading it off info.context.request.user, the way Django's session middleware exposes it.

# python
# from lrb.identity.selectors.get_active_session import get_active_session

# This is the exact stub function from the very first file of this whole conversation — get_active_session(*, user_id: str) -> Optional[dict], the one that always returns a hardcoded {"active": True, ...} no matter what. You're now seeing precisely where it gets called from. Keep that in mind as you read the body below — this resolver's logic is correct, but its actual output will currently be wrong for every real user, because the function it depends on hasn't been finished yet.

# 3. Signature — two new decorator layers
# python
# @strawberry.type
# class SessionQuery:

# Same @strawberry.type decorator you already understand — but here, note the name's convention: ...Query, not ...Type. This class isn't describing a piece of data (like SessionType or AuthMutationPayload were) — it's a root query type, a container Strawberry uses to organize "here are the read operations available on the API," the same way you'd expect a matching ...Mutation class somewhere else to hold login, resetPassword, etc. Your project notes mention "Root schema composed in config/schema.py" — that's where several of these ...Query and ...Mutation classes from different apps all get combined into one final API.

# python
#     @strawberry.field
#     def session(self, info: strawberry.Info) -> Optional[SessionType]:

# This is genuinely new syntax — a method inside a class, decorated individually, rather than a bare class of annotations. Let's break every piece apart.

# @strawberry.field — a different decorator from @strawberry.type, and it's doing a different job at a different level: @strawberry.type marks the whole class as a GraphQL type; @strawberry.field marks one method inside it as a queryable field — specifically, one whose value comes from running actual Python code (a "resolver"), rather than being a plain static attribute like SessionType.active: bool was. When a client asks for session { ... }, Strawberry calls this method to compute the answer live, rather than reading a stored value.
# def session(self, info: strawberry.Info) -> Optional[SessionType]: — a normal method definition (def, inside a class), but look closely at the parameters — this is the first function in the whole conversation without a * forcing keyword-only arguments. That's not an inconsistency to flag — it's correct and expected. Your project's keyword-only convention applies to your own service/selector functions, which you control the calling convention for. self and info here are positional parameters Strawberry itself calls this method with — you don't get to choose how Strawberry invokes your resolver, so there's nothing to make keyword-only. This is the same lesson as the set_password/check_password bug from earlier, just correctly applied this time: match the calling convention the framework actually uses, don't impose your own project's style onto code a library calls for you.
# self — same meaning as always: "the specific SessionQuery instance this method is being run on." Since this class holds no actual per-instance data (no fields set in __init__), self here is mostly a formality Python requires for any regular instance method — but it's still what makes this a proper method rather than a standalone function.
# info: strawberry.Info — a special parameter every Strawberry resolver can optionally accept, type-hinted as strawberry.Info. This object carries request-level context — things like the current user, headers, or whatever else your GraphQL view attaches to the request (this connects to "GraphQL served at /graphql/ via csrf_exempt(GraphQLView.as_view(schema=schema))" from your project notes — info is how a resolver reaches back into that underlying Django request). This is how get_current_user(info) below is able to figure out who's asking, without you having to pass a user around manually through every layer.
# -> Optional[SessionType] — the return type hint, and it's meaningfully different from every service function you've read today, which mostly had no return hint at all. Here it matters for a real reason: Strawberry reads this type hint to build the schema itself — it's not just documentation, the same way SessionType's field annotations weren't just documentation. Optional[SessionType] tells the GraphQL schema "querying session might return null" — which is exactly what happens for a logged-out visitor, as you're about to see.
# 4. Body — step by step
# python
#         user = get_current_user(info)

# Calls the selector, passing info positionally — again, correctly, since this is calling your own selector function. Let's pause on this: is get_current_user itself keyword-only? You haven't seen its definition, but based on this call site passing info with no =, either it's defined without the * convention (an exception, perhaps because it's meant to be called the same way Strawberry calls things), or this is actually a small inconsistency worth checking against the file itself if you come across it later. Worth holding as an open question rather than assuming either way without seeing the source.

# python
#         if not user:
#             return None

# Familiar falsy-check-then-early-return pattern. If nobody's logged in, there's no session to describe — return None immediately, matching the Optional[SessionType] return type: this is the concrete case that return hint exists to permit.

# python
#         data = get_active_session(user_id=str(user.id))
# Calls the stub function from way back, this time correctly keyword-only (user_id=...), matching how it was actually defined.
# str(user.id) — user.id is presumably an integer or UUID (a database primary key); str(...) converts it to text, matching get_active_session's user_id: str type hint. This is a small but genuinely important detail: the selector expects a string ID, and user.id from the database is very likely not a string by default — without this conversion, you'd be silently passing the wrong type. This is worth remembering as a general pattern: primary keys often need explicit conversion when crossing from "database object" to "API boundary expecting a specific primitive type."
# python
#         return SessionType(
#             user_id=data["user_id"],
#             active=data["active"],
#             created_at=data["created_at"],
#         )
# data["user_id"], data["active"], data["created_at"] — dictionary indexing with square brackets: "look up the value stored under this exact key." This is different from .get("key"), which you saw once before (ages.get(name)) — [...] raises a KeyError if the key doesn't exist, while .get(...) returns None safely instead. Using [...] here is a reasonable choice specifically because get_active_session's stub always includes exactly these three keys — if that guarantee ever changes (say, a future real implementation sometimes omits created_at), this line would need to switch to .get(...) or risk crashing.
# Builds and returns a real SessionType instance, translating the plain dict from the selector into the typed GraphQL object the schema promises to return.
# 5. Why this approach
# Splitting get_current_user and get_active_session into two separate calls, rather than one combined function, mirrors the service/selector philosophy you've seen everywhere today: "who is asking" (authentication/identity) and "what does their session look like" (session-specific data) are two independently reusable concerns — get_current_user is almost certainly called from many resolvers across the whole schema, not just this one.
# Returning None early for a logged-out user, rather than raising an error, fits GraphQL norms: asking "what's my session" while logged out isn't an error — it's a perfectly valid question with a perfectly valid answer (null). This is a good contrast worth holding onto against your service layer's raise ApplicationError(...) pattern — that's for mutations attempting an action that genuinely failed; this is a query describing a state that's legitimately absent. Different situations, different mechanisms, both correct in context.
# 6. Connections — the loop closes

# You can now see the complete arc, start to finish, across this entire conversation:

# get_active_session()  [stub — very first file you read]
#         ↑
#         │  called by
#         │
# SessionQuery.session()  [this file]
#         │
#         │  wraps result into
#         ↓
# SessionType  [second-to-last file]

# The very first piece of code you asked me to explain today turns out to be load-bearing infrastructure for one of the very last — that's not a coincidence in how I picked these, it's just what a real, interconnected codebase looks like once you've read enough of it.

# 7. What's still incomplete (not a bug — an honest gap)

# Because get_active_session is still a stub, this resolver is functionally correct in structure but will currently return the same fake active: True for every logged-in user, regardless of whether a real session actually exists or is still valid. This file has no bug in isolation — everything it does with the data it receives is correct — but it inherits the incompleteness of a function three files back. This is a valuable, realistic thing to notice: a file can be perfectly correct and still produce wrong results, because of an unfinished dependency elsewhere. Reading one file in isolation is never quite enough to fully trust its output — you have to trace what it actually calls.

# 8. Small example
# python
# @strawberry.type
# class ProfileQuery:
#     @strawberry.field
#     def profile(self, info: strawberry.Info) -> Optional[ProfileType]:
#         user = get_current_user(info)
#         if not user:
#             return None
#         return ProfileType(name=user.name, bio=user.bio)

# Same shape: guard on identity first, then build and return the typed response.

# 9. What to remember
# @strawberry.field marks one method as a live resolver; @strawberry.type marks the whole class as a schema container — two decorators, two different scopes of effect.
# A resolver's own parameters (self, info) follow the calling framework's convention, not your project's internal style rules — keyword-only applies to functions you call, not to how a library invokes your code.
# Return type hints on resolvers aren't just documentation — Strawberry reads them to build the actual GraphQL schema, same as the field annotations on @strawberry.type classes.
# dict["key"] raises if missing; dict.get("key") returns None instead — pick based on whether you're certain the key exists or need to handle its absence gracefully.
# A file can be completely correct on its own and still return wrong results, because of what it depends on — you now have a real, first-hand example of this, having read both ends of the same dependency chain in one conversation. Tracing a function's callees, not just reading it in isolation, is what closes that gap — and it's exactly the instinct this whole session has been building toward.