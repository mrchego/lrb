def get_current_user(info):
    request = info.context.request
    if not request.user.is_authenticated:
        return None
    return request.user


# 1. Purpose — Why this exists

# What problem is this solving?
# In a GraphQL project (which is what your authorization/accounts apps use via Strawberry), almost every resolver and mutation needs to answer one question: "who is making this request?" You can't check permissions, log an action, or scope a query to "my company's data" without first knowing who "I" am. This function is the single place that answers that question.

# Why not just write the logic directly in every resolver?
# Because every single mutation and query would need to repeat the same three lines: dig into info.context, find the request, check is_authenticated. If Strawberry ever changed where the request lives on the context object, you'd have to update every resolver in your codebase instead of one function.

# When is this used in a real project?
# At the very top of resolvers and mutations, before doing anything else — often immediately followed by passing the result into something like require_permission(actor=..., codename=...).

# What breaks without it?
# Every resolver would need to know GraphQL/Strawberry internals (info.context.request) directly, mixing "how do I get the user" concerns into business logic everywhere. You'd also risk resolvers that forget to check is_authenticated and accidentally treat an anonymous visitor as a logged-in user.

# 2. Imports — explained like you've never programmed

# There are none in this file. That's worth noticing rather than skipping past: this function doesn't need to reach into any other file's code because everything it touches — info, request, .user, .is_authenticated — is either handed to it directly as a parameter, or is a built-in attribute that Django and Strawberry attach automatically to objects you already have. No from, no import, because there's nothing external to fetch here.

# 3. Signature — every symbol explained
# python
# def get_current_user(info):

# def
# "I'm defining a reusable block of instructions" — same as always.

# get_current_user
# The name tells you exactly what comes back: the user making the current request (or nothing, if there isn't one).

# Parentheses ()
# The delivery box — this is where the caller hands in whatever this function needs to do its job.

# info
# A single parameter, no type hint, no default value. This is the plainest possible parameter — just a placeholder name, like Dear _______.

# No *, no keyword-only enforcement
# Notice this is a departure from what you've seen in your service functions (require_permission, count_active_superusers), which force keyword arguments. Why is this one different? Because this isn't one of your custom service functions — it's a GraphQL resolver-style helper. Strawberry (like most GraphQL libraries) calls resolvers with info as a positional argument by convention; you don't get to choose keyword-only here because you're not the one calling it — the framework is.

# No ->  return type hint
# Also worth noticing: no promise about what type comes back. We'll see why in a moment — this function actually returns two different kinds of things depending on the situation, which makes a single clean type hint awkward without importing Optional (in fact, technically this should probably be -> Optional[User], and its absence here is a small inconsistency worth flagging, not a rule you should copy).

# 4. Classes

# No class here, and for the same reason as count_active_superusers: this function has no state to carry between calls. Every time it's invoked, it does one thing (look at this specific request) and either hands back a user or None. There's nothing to instantiate.

# 5. Body — line by line
# Line 1
# python
# request = info.context.request

# Right side, read as a journey:

# info — the parameter you were handed
# .context — GraphQL frameworks bundle up everything relevant to the current request into a "context" object, attached to info. Think of info as an envelope, and .context as what's inside it.
# .request — inside that context, Strawberry stores the original Django HTTP request object — the same kind of request object you'd see in an ordinary Django view.

# Left side:
# We're storing it in a variable called request because we're about to use it twice on the next two lines, and re-typing info.context.request three times would be repetitive and harder to read.

# Whole line, plain English:
# "Dig into the GraphQL info object to pull out the underlying Django HTTP request."

# Line 2–3
# python
# if not request.user.is_authenticated:
#     return None

# Read the condition inside if first, right to left in meaning:

# request.user — Django automatically attaches a user object to every request (this is standard Django middleware behavior, nothing custom here). If nobody is logged in, this is Django's special AnonymousUser object — not None, an actual object that just represents "nobody."
# .is_authenticated — a property that's True for a real logged-in user and False for AnonymousUser. This is Django's built-in way of asking "is this a real, logged-in person?"
# not ... — flips it: this condition is True when the visitor is not authenticated.

# The verb return None:
# Immediately stop the function and hand back None — Python's explicit way of representing "nothing," "no value," "not applicable."

# Whole thing, plain English:
# "If whoever made this request isn't logged in, stop here and say there's no current user."

# Line 4
# python
# return request.user

# Right side: request.user — the same attribute we already checked on the line above, now actually being handed back.

# Verb: return — stop the function, hand this value to the caller.

# Whole line: "Otherwise, give back the actual logged-in user object."

# 6. Beginner questions, answered proactively

# Why check is_authenticated instead of just if request.user:?
# Because request.user is never None in Django — even an anonymous visitor gets a real AnonymousUser object, which would be truthy in a boolean check (if request.user: would pass even for anonymous visitors, which is exactly the bug you're trying to avoid). is_authenticated is the only reliable way to distinguish a real user from a stand-in for "nobody."

# Why return None instead of raising an exception here?
# This function is answering "who is this, if anyone" — a question that legitimately has "nobody" as a valid answer (public/anonymous GraphQL queries are often allowed to run). Raising an exception would be appropriate for a function like require_permission, whose entire job is to enforce that someone is present. This function's job is only to report, not to enforce — enforcement is left to whatever calls it next.

# Why not just call request.user directly wherever it's needed, skipping this function?
# You could — but then every single caller has to remember the is_authenticated check themselves, and remember it needs .None instead of trusting AnonymousUser's truthiness. Centralizing it means that check is written once, correctly, and never forgotten.

# Why does line 1 fetch request into a variable instead of writing info.context.request.user.is_authenticated inline?
# Purely readability — request is reused twice below. Writing the full chain three times would work identically but be harder to scan.

# 7. Design discussion

# Why return Optional[User] (a user or None) instead of always raising if nobody's logged in?
# This mirrors a real design decision: some parts of your schema (public product listings, maybe) should work for anonymous visitors, while others (staff mutations) should require a user. If get_current_user always raised on None, you'd lose the ability to have any public-facing queries at all. By returning None and letting the caller decide whether that's acceptable, this function stays reusable across both authenticated-only and public parts of your schema.

# Trade-off: this pushes responsibility onto every caller to remember to check for None before using the result. An alternative design would be two functions — get_current_user() (nullable) and require_current_user() (raises if None) — giving each caller an explicit choice instead of one function that quietly hands back None and hopes it's checked.

# 8. DIY Recipe — build one like this yourself

# How to build your own "identify the current actor" helper:

# Find where your framework stores the request/session for the current call. In Django+GraphQL, that's info.context.request; in a plain Django view, request is just handed to you directly as a parameter.
# Check authentication using the framework's built-in signal, not a truthiness check on the user object itself — look for something like is_authenticated, never assume "no user" means None.
# Decide: should "nobody's logged in" be an error, or a valid None result? If some callers need to allow anonymous access, return None. If this helper should only ever be used where a user is mandatory, raise instead.
# Keep the function to one job: identify the actor. Don't fold in permission checks here — that belongs in a separate function (like your require_permission), called after this one.
# 9. General pattern recognition

# This is the "context extraction with a fallback" pattern:

# python
# def get_current_<thing>(info):
#     value = info.context.<path to raw value>
#     if not <condition proving it's usable>:
#         return None
#     return value

# You'll see this same shape anywhere you need to pull something out of a framework-provided bag of request data, with a guard clause for the "not actually available" case. It generalizes beyond auth — e.g., a hypothetical get_current_company(info) that reads a company from a subdomain header, returning None if none was set.

# 10. Real project usage

# This is almost certainly the very first line inside most of your GraphQL mutations and protected queries:

# python
# def resolve_deactivate_user(self, info, target_user_id: str) -> SimpleMutationPayload:
#     actor = get_current_user(info)
#     if actor is None:
#         raise PermissionError("Authentication required.")
#     require_permission(actor=actor, codename="staff.manage_users")
#     ...

# Notice the pattern from the design discussion playing out here: get_current_user stays neutral (returns None), and it's the resolver that decides None isn't acceptable in this particular case.

# 11. Common beginner mistakes

# ❌ Checking if request.user: instead of request.user.is_authenticated — silently treats anonymous visitors as "present" because AnonymousUser is truthy.

# ❌ Assuming get_current_user(info) always returns a real user — forgetting the None check downstream, then crashing later with an AttributeError when code tries to call .company_id or similar on None.

# ❌ Putting permission logic inside this function — mixing "who is this" with "are they allowed to do this" makes the function harder to reuse in public, unauthenticated parts of the schema.

# ❌ Re-fetching info.context.request repeatedly across a resolver instead of calling this one shared helper — reintroduces the exact duplication this function exists to prevent.

# 12. Think like the original developer

# If you had to invent this yourself with no reference:

# What problem am I solving? "Every resolver needs to know who's asking — I don't want to repeat that lookup everywhere."
# What inputs will I need? Whatever object the framework gives every resolver — for Strawberry, that's info.
# What could go wrong? Someone assumes request.user is None when unauthenticated (it isn't — it's AnonymousUser), and ships a check that silently misbehaves.
# How should I report "nobody's logged in"? Since some parts of the app should tolerate anonymous access, don't force an exception here — hand back None and let each caller decide what that means for them.
# What should happen if everything works? Return the real user object, unmodified — no extra wrapping, so callers can immediately use it (e.g., pass straight into require_permission(actor=...)).