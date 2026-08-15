from typing import Iterable
from django.db.models import QuerySet
from lrb.accounts.models import User

def get_users_by_ids(*, user_ids: Iterable[str], company_id: str | None) -> QuerySet[User]:
    qs = User.objects.filter(pk__in=user_ids)
    if company_id:
        qs = qs.filter(company_id=company_id)
    return qs


# 1. Purpose — Why this exists

# What problem is this solving?
# Sometimes you don't need one user — you need several at once, by a batch of IDs. Think: a GraphQL query that resolves a list field (assignedUsers: [User] on some object), or a mutation that operates on multiple targets at once (bulk role assignment, bulk deactivation). This function is the "many at once" counterpart to get_user.

# Why not just write the query directly wherever it's needed?
# Same reasoning as every lookup function you've shown me: consistency. Every caller that needs "give me these users" should get the same filtering behavior — including the company-scoping safety net we'll see in a moment — rather than each writing its own slightly-different query.

# When is this used in a real project?
# Anywhere you have a list of user IDs and need the actual objects — batch operations, resolving a GraphQL list field, validating that a set of submitted IDs actually correspond to real users before acting on them.

# What breaks without it?
# Duplicated batch-lookup logic scattered around, and — this is the important one — a real risk that some of those duplicated queries forget to scope by company, silently letting one company's staff pull up another company's users just by guessing IDs.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional
# from lrb.accounts.models import User

# Same two imports as get_user and get_user_by_email — Optional (built into Python, describes "this type, or None") and User (your own custom model, reached through the lrb.accounts.models path). Nothing new here mechanically. But notice what's missing compared to count_active_superusers, which took a collection of IDs: there's no from typing import Iterable. Hold that thought — it's the first clue toward the bug.

# 3. Signature — every symbol explained
# python
# def get_users_by_ids(*, user_ids: str, company_id: Optional[str] = None):

# def get_users_by_ids — named for what it returns: multiple users, found by a batch of IDs.

# (*, ...) — your familiar keyword-only enforcement. Good, consistent with every function we've seen.

# user_ids: str — here's the bug. Read literally, this type hint claims: "pass me a single string." But the function's own name is get_users_by_ids (plural!), and — as we'll see in Section 5 — the body uses pk__in=user_ids, Django's "is this value inside this collection?" lookup, which is meant to receive a list of IDs, not one string.

# Compare this to count_active_superusers, which you already looked at:

# python
# exclude_ids: Optional[Iterable[str]] = None

# That one correctly hints "a collection of strings." This one should almost certainly read:

# python
# user_ids: Iterable[str]

# As written, if you (or your editor's type checker) trusted the hint literally, you might call this with user_ids="abc-123" — a single string — and it would technically run without crashing, but silently do something you didn't intend (more on that in Section 6).

# company_id: Optional[str] = None — a familiar shape by now: optional, defaults to None if the caller doesn't provide it, type-hinted correctly this time as a single string (which makes sense — you'd only ever scope to one company).

# No -> return type hint at all.
# This is the second thing worth flagging. Every other lookup function you've shown me had one (-> Optional[User], -> int). Here, there's nothing — but the function actually returns a Django QuerySet[User], not a User, not a list, not an Optional of anything. Leaving this off means a reader has to go read the body to discover that this returns a lazy queryset rather than an already-fetched list of users — a meaningfully different thing to work with (more in Section 6).

# 4. Classes

# No class — same reasoning as every function in this file: one self-contained operation, no state to remember between calls.

# 5. Body — line by line
# Line 1
# python
# qs = User.objects.filter(pk__in=user_ids)

# Right side, as a journey:

# User — your model
# .objects — Django's automatic query entry point
# .filter(pk__in=user_ids) — the verb. pk you already know from get_user — "whatever the primary key field is called." The new piece is __in — Django's lookup for "is this value inside this collection?" So pk__in=user_ids means: "find every row whose primary key appears in this collection of IDs." This is the plural sibling of the pk=user_id exact-match you saw in get_user.

# Left side: qs — same naming convention as count_active_superusers, short for "queryset." We store it because we might narrow it further on the next line.

# Whole line: "Find every User whose primary key is one of the given IDs."

# Line 2–3
# python
# if company_id:
#     qs = qs.filter(company_id=company_id)

# Condition: if company_id: — true only if a company ID was actually provided (not None, not an empty string).

# Right side of the reassignment: qs.filter(company_id=company_id) — narrow the existing query further, keeping only rows where the company_id field matches. Note this is .filter() again, not .exclude() — we're keeping matches, not removing them, which is the opposite operation from what you saw in count_active_superusers.

# Left side: reassign qs to the narrower version — same pattern, same reason as before: querysets are immutable, so skipping the reassignment would silently discard this scoping.

# Whole thing: "If a company was specified, further restrict the results to just that company's users."

# Line 4
# python
# return qs

# The important thing to notice: this returns qs directly — the queryset itself, not qs.count() (like count_active_superusers), not qs.first() (like get_user). It hasn't been executed against the database yet. The actual SQL query only runs the moment something iterates over qs (a for loop, converting to a list(), etc.) — Django calls this "lazy evaluation."

# Whole line: "Hand back the (possibly company-scoped) queryset, unexecuted, for the caller to use however they need."

# 6. Beginner questions, answered proactively

# Why does pk__in=user_ids "work" even if you pass a single string like "abc-123" instead of a list?
# This is the dangerous part of the bug. Strings are themselves iterable — each character counts as an element. So pk__in="abc-123" doesn't error — Django happily interprets it as "find rows whose primary key is 'a', or 'b', or 'c'..." one character at a time. It won't crash; it'll just silently return nothing (since no real ID is a single character), and you'd have no idea why your query came back empty. This is exactly why Iterable[str] matters as a hint here, not just as decoration — it's actively steering people away from a subtle, silent failure mode.

# Why filter by company_id instead of always requiring it?
# Looking at the signature, company_id is optional — meaning this function can be called two ways: scoped to one company, or unscoped across all companies. That's a meaningful design choice we'll dig into in Section 7, because it has real security implications.

# Why return the queryset instead of list(qs) or converting it to something concrete?
# Returning the raw queryset lets the caller decide what to do next without paying for work they might not need — order it, slice it for pagination, .count() it, or iterate it. Converting to a list here would force full evaluation immediately, even if the caller only wanted a count or the first page of results.

# Why is there no Optional on the return, unlike get_user?
# Because this function's answer is never really "nothing" in the same sense — an empty queryset (zero matches) is a completely normal, valid QuerySet object, not None. Contrast this with get_user, where "no match" genuinely meant "I have no object to give you," so None was the honest signal. A queryset with zero rows is still a perfectly good queryset.

# 7. Design discussion

# The real design issue here is the optional company_id. Think back to count_active_superusers, where company_id was mandatory — you can't even call that function without specifying a company. Here, it's optional, meaning get_users_by_ids(user_ids=[...]) — with no company at all — is a completely legal call that will search across every company in the system.

# Is that intentional? It might be, for a genuinely cross-company admin/superuser context. But it's also exactly the kind of function where a bug is easy to introduce: imagine a staff member's mutation resolver calls get_users_by_ids(user_ids=submitted_ids) and simply forgets to pass company_id=actor.company_id. Nothing crashes. Nothing warns you. You'd have just built a mutation that lets any staff member fetch (and potentially act on) users belonging to a completely different company — a serious RBAC violation, made possible by an easy-to-forget optional parameter with no enforcement.

# Trade-off worth naming explicitly: making company_id mandatory (like count_active_superusers does) would close this hole, at the cost of losing the ability to do legitimate cross-company lookups from a true platform-admin context. As written, that trade-off is being made silently — there's nothing in the code signaling "hey, caller, you're about to search across every company unless you explicitly opt into scoping." A safer version of this same function might require callers to be explicit either way:

# python
# def get_users_by_ids(*, user_ids: Iterable[str], company_id: str | None) -> QuerySet[User]:

# (no default at all — forcing every caller to consciously write company_id=None if they truly mean "all companies," rather than being able to omit it by accident).

# 8. DIY Recipe — build one like this yourself

# How to build your own "batch lookup, optionally scoped" function:

# Type-hint the collection parameter as Iterable[str] (or list[str]), never str — a batch parameter that's actually singular-typed is a bug waiting to happen, since strings are themselves iterable and will silently "work" the wrong way.
# Use pk__in=<collection> for "give me all rows matching any of these IDs."
# Think hard before making a scoping parameter (like company_id) optional. Ask: "what happens if a caller forgets to pass this?" If the answer is "a security or data-isolation problem," strongly consider making it mandatory instead, the way count_active_superusers does.
# Return the queryset unevaluated if callers might need to further filter, order, paginate, or just count — don't force early evaluation with list() unless you specifically want that.
# Add a return type hint even for querysets — -> QuerySet[User] — so a reader doesn't have to read the body to know they're getting a lazy queryset rather than a materialized list.
# 9. General pattern recognition

# This is a new pattern for you, distinct from the three you've already seen — call it "batch lookup, returned lazy":

# python
# def get_<things>_by_ids(*, <thing>_ids: Iterable[str], <scope>: Optional[str] = None) -> QuerySet[Model]:
#     qs = Model.objects.filter(pk__in=<thing>_ids)
#     if <scope>:
#         qs = qs.filter(<scope_field>=<scope>)
#     return qs

# The defining trait: it returns the queryset itself, not a count (count_active_superusers), not a single object (get_user) — because the caller needs the flexibility to do more with the results before deciding what to actually fetch.

# 10. Real project usage

# This shape is exactly what you'd expect behind a GraphQL list-resolving field, or a bulk-action mutation:

# python
# def resolve_users(self, info, user_ids: list[str]) -> QuerySet[User]:
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.view_users")
#     return get_users_by_ids(user_ids=user_ids, company_id=actor.company_id)

# Notice this hypothetical caller does remember to pass company_id=actor.company_id — which is exactly the discipline the current optional design is silently relying on every single caller to remember, every single time.

# 11. Common beginner mistakes

# ❌ Passing a single string instead of a list — get_users_by_ids(user_ids="abc-123") doesn't crash, it just silently matches nothing (or matches wrong rows), because a string is iterated character-by-character.

# ❌ Forgetting company_id when it should have been scoped — nothing enforces it, so this is easy to miss in code review unless you're specifically looking for it.

# ❌ Treating the return value as already-fetched data — e.g., calling this twice thinking you're reusing results, when each iteration actually re-runs the query against the database, since it's lazy.

# ❌ Not handling the "some IDs didn't match" case — if you pass five IDs and only three exist, this returns three results with no indication of which two were missing; a caller expecting all five back could be silently short-changed.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "I sometimes need multiple users at once by their IDs, not just one — and I might want it scoped to a company."
# What inputs will I need? A batch of IDs (a collection, not a single value!), and optionally a company to restrict the search to.
# What could go wrong? Passing the wrong shape of data for the ID batch; forgetting to scope by company when I should have; assuming the result is already-fetched when it's actually lazy.
# How should I report results? A queryset, not a single value and not None — "zero matches" is just an empty queryset, a completely normal, non-error outcome for a batch lookup.
# What should happen if everything works? Hand back the (possibly scoped) unevaluated queryset, letting the caller decide whether to count it, list it, paginate it, or filter it further — since I don't know yet what they actually need to do with it