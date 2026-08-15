from typing import Optional
from lrb.accounts.models import User

def get_user(*, user_id: str) -> Optional[User]:
    return User.objects.filter(pk=user_id).first()




# 1. Purpose — Why this exists

# What problem is this solving?
# You constantly have a user's ID (from a session, a URL, a GraphQL mutation argument like target_user_id) and need the actual User row it points to. This is arguably the single most-called lookup in the whole project — nearly every service that acts "on a user" (deactivate, promote, assign a role) needs to go from "an ID string" to "a real object with real fields" first.

# Why not just write User.objects.get(pk=...) inline everywhere?
# Same reasoning as get_user_by_email: centralizing means every caller gets consistent "not found" behavior, and if the lookup logic ever needs to change (e.g., later excluding soft-deleted users), you fix it in one place.

# When is this used?
# Practically everywhere a service or resolver receives an ID and needs the object — this is likely one of the most frequently imported functions in your entire accounts app.

# What breaks without it?
# Every service would either duplicate User.objects.filter(pk=...).first() or, worse, some might use .get() and others .filter().first(), giving inconsistent crash-vs-None behavior across the codebase for the exact same kind of lookup.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional
# from lrb.accounts.models import User

# Identical imports to get_user_by_email, for identical reasons: Optional (built into Python, describes "this or None") and User (your own custom model, reached via the lrb.accounts.models path through your project's folders). Nothing new to explain here — the presence of exactly these two imports is itself a signal, once you recognize the pattern, that you're about to see another "safe single-record lookup."

# 3. Signature — every symbol explained
# python
# def get_user(*, user_id: str) -> Optional[User]:

# def get_user — defined, named for exactly what it returns.

# (*, user_id: str) — the lone * again enforces keyword-only calling: get_user(user_id="abc-123") is required, get_user("abc-123") is forbidden. user_id: str — a mandatory placeholder (no default value), type-hinted as a string.

# One thing worth pausing on that's easy to skim past: the parameter is named user_id, but as you'll see in the body, it's compared against pk. This is a deliberate naming choice — user_id is what the caller thinks in terms of (which user am I identifying?), while pk is what Django's ORM thinks in terms of (primary key, whatever that field is actually called on the model). The function's job includes translating between how the outside world names things and how the database layer names things.

# -> Optional[User] — same honest promise as before: you get a User back, or you get None. Never anything else.

# 4. Classes

# No class, same reasoning as every function we've walked through: single self-contained operation, nothing to remember between calls, a function is the correct minimal tool.

# 5. Body — line by line
# python
# return User.objects.filter(pk=user_id).first()

# Step 1 — User — start at your User model.

# Step 2 — .objects — Django's automatic query entry point for this model.

# Step 3 — .filter(pk=user_id) — the first verb: find rows matching a condition. Here's the interesting part: pk is Django's universal shorthand for "whatever this model's primary key field is" — it works identically whether the actual underlying column is named id, uuid, or something custom. This is why the function can accept a generic user_id: str without needing to know or care what your User model's primary key column is actually called internally. .filter() builds (but doesn't yet run) a query.

# Step 4 — .first() — run the query, return the first match or None if there's no match — never raising an exception. Same behavior, same reasoning as get_user_by_email.

# Whole line, plain English: "Look up a user whose primary key matches the given ID; return them if found, or None if not."

# 6. Beginner questions, answered proactively

# Why pk instead of id?
# pk always works regardless of what the primary key field is actually named on the model, while id would break if your User model ever used a different primary key field name (some projects use uuid as the primary key, for instance). pk is Django's way of future-proofing this kind of code against that detail.

# Why .first() instead of .get() — again?
# Same answer as get_user_by_email: a None result here is often a completely normal outcome, not a bug. Think about a GraphQL mutation like deactivate_user(target_user_id: str) — if a staff member submits a stale/deleted ID (maybe someone else just deleted that user seconds earlier), you want to gracefully report "user not found," not crash the whole request with an unhandled User.DoesNotExist.

# Isn't looking someone up by ID supposed to be guaranteed to exist, unlike email?
# Not necessarily — IDs get stale too (deleted records, IDs from another company being passed in by mistake, front-end bugs sending the wrong value). Treating "not found by ID" as just as normal a case as "not found by email" is the safer default, and it's exactly why this function mirrors get_user_by_email's design rather than assuming IDs are somehow more trustworthy.

# Why is there no variable, again?
# Same reasoning as before — the result of .filter().first() is used exactly once, immediately, in the return statement. No reuse, no benefit to naming it.

# 7. Design discussion

# Why does this function exist separately from get_user_by_email instead of one combined "find user by any identifier" function?
# Because they answer genuinely different questions with different callers and different trust levels. An ID typically comes from your own system (a URL, a GraphQL argument, a foreign key) — something already inside your application's trusted data. An email typically comes from user input on a form — something a person is actively typing, which has different failure modes (typos, case sensitivity, "does this reveal account existence" security concerns). Keeping them separate keeps each function's contract simple and its callers' intent clear at the call site — get_user(user_id=...) versus get_user_by_email(email=...) tells a reader immediately what kind of value is flowing in, without needing a comment.

# Trade-off: this does mean near-duplicate code between the two functions. That's an acceptable, common trade-off in service layers — a small amount of repetition in exchange for each function being trivially simple to read on its own, rather than one clever combined function with conditional logic branching on which identifier was provided.

# 8. DIY Recipe — build one like this yourself

# Same recipe as get_user_by_email, with one addition specific to ID lookups:

# Decide if "not found" is normal or exceptional for this specific lookup — for IDs originating from external/user-controlled sources (URLs, mutation args), treat "not found" as normal.
# Use pk rather than hardcoding a field name like id — it's more resilient to primary key changes on the model.
# Use .filter(pk=...).first() and Optional[Model] when "not found" should degrade gracefully rather than crash.
# Keep it keyword-only, matching your project's convention, even with a single parameter.
# Name the parameter for what the caller conceptually has (user_id), even if internally you translate it to pk — the function's job is to bridge that gap.
# 9. General pattern recognition

# This is the exact same "safe single-record lookup" pattern as get_user_by_email:

# python
# def get_<thing>_by_<identifier>(*, <identifier>: <type>) -> Optional[Model]:
#     return Model.objects.filter(<orm_field>=<identifier>).first()

# Once you can name this pattern, you'll recognize it instantly anywhere in the codebase — get_user, get_user_by_email, and probably eventually get_company, get_role_by_codename, etc. all share this identical shape with only the field and model swapped.

# 10. Real project usage

# This is almost certainly the very first line of most write services that take a target user ID — exactly the pattern we sketched in count_active_superusers's "real project usage" section:

# python
# @transaction.atomic
# def deactivate_user(*, actor, target_user_id: str) -> SimpleMutationPayload:
#     require_permission(actor=actor, codename="staff.manage_users")
#     target = get_user(user_id=target_user_id)
#     if target is None:
#         return SimpleMutationPayload(success=False, errors=["User not found."])
#     remaining = count_active_superusers(company_id=target.company_id, exclude_ids=[target_user_id])
#     if remaining == 0:
#         return SimpleMutationPayload(success=False, errors=["Cannot deactivate the last active superuser."])
#     ...

# Notice how all four functions we've now walked through — require_permission, get_user, count_active_superusers, and (implicitly) something like get_current_user earlier in the resolver — compose together into one real service. This is the payoff of the "general pattern recognition" section: once each small function's job is clear, reading the service that combines them becomes much easier.

# 11. Common beginner mistakes

# ❌ Forgetting the None check before using target — target.company_id crashes with AttributeError if target is None.

# ❌ Confusing user_id (the caller's concept) with pk (the ORM's concept) and writing filter(user_id=user_id) instead of filter(pk=user_id) — User model doesn't have a field literally called user_id, so this would raise a FieldError.

# ❌ Assuming IDs never go stale and skipping the None check "because it's just an ID, it must exist" — a dangerous assumption in any system where records can be deleted or IDs can come from another company's data by mistake.

# ❌ Passing the wrong type — e.g., passing an integer when user_id: str is expected, if your primary keys are UUID strings; Django will often coerce this, but it's a silent type mismatch worth being deliberate about.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "Nearly every service I write receives a user's ID and needs the real object — I want one trustworthy place to do that translation."
# What inputs will I need? Just the ID — nothing else identifies a specific row by primary key.
# What could go wrong? The ID doesn't correspond to any existing row (deleted, stale, wrong company, front-end bug) — and this should be a normal, handleable outcome, not a crash.
# How should I report "not found"? Return None, matching the same contract as get_user_by_email, so every caller across the codebase learns one consistent way to handle "lookup failed."
# What should happen if everything works? Return the real User object, unmodified, ready for the caller to act on immediately — permission checks, field reads, whatever comes next.


