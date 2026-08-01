from lrb.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

def clamp_page_size(limit=None):
    """Keeps requested page sizes within DEFAULT_PAGE_SIZE..MAX_PAGE_SIZE,
    so a caller can never request an unbounded slice."""
    if limit is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(limit, MAX_PAGE_SIZE))

def paginate_queryset(queryset, *, limit=None, offset=0):
    """
    Evaluates `.count()` once, then slices — two queries total, never the
    full table. Returns (items, total_count) so GraphQL can expose both
    the page and how many rows exist in total (for a "Page X of Y" UI).
    """
    size = clamp_page_size(limit)
    offset = max(0, offset or  0)
    total_count = queryset.count()
    items = list(queryset[offset : offset + size])
    return items, total_count


# core/pagination.py
# 1. Purpose (why this exists)

# Imagine your orders table has 500,000 rows. If a client asks "give me all the orders," and your code just fetched everything and sent it back, your server would choke (too much memory) and the client's app would freeze trying to display half a million rows. This file's job: always hand back a small, safe slice of data at a time (like "page 1 of results"), never the whole table — and also tell the client how many total rows exist, so a UI can show "Page 3 of 47."

# 2. The import
# python
# from lrb.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
# from ... import ... = "go to this specific file/location, and bring back just these two named things."
# lrb.core.constants = a path to another file in your project — lrb/core/constants.py — whose entire job is to hold plain fixed values (numbers, settings) that many files need to share.
# DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE = two specific values we're grabbing from that file. Think of them as labeled boxes with numbers inside — e.g., maybe DEFAULT_PAGE_SIZE = 20 and MAX_PAGE_SIZE = 100. We don't hardcode 20 or 100 directly in this file — instead we reference the shared box, so if that number ever needs to change project-wide, you only change it in one place (constants.py), not hunt through every file that used the number 20.
# Function 1: clamp_page_size
# The signature
# python
# def clamp_page_size(limit=None):
# def = "I'm defining a function" (a reusable named block of instructions).
# clamp_page_size = the name of this function.
# (limit=None) = this function accepts one input, called limit, inside the function. The =None part means: "if whoever calls this function doesn't give you anything, just assume limit is None" (Python's word for "nothing/no value"). So this input is optional.
# The docstring (the triple-quoted text)
# python
# """Keeps requested page sizes within DEFAULT_PAGE_SIZE..MAX_PAGE_SIZE,
# so a caller can never request an unbounded slice."""

# This isn't code that runs — it's a note, written by the programmer, explaining what the function does, sitting right under the function's name so anyone reading it (including tools/IDEs) can see a plain-English summary without reading the actual logic.

# The body
# python
#     if limit is None:
#         return DEFAULT_PAGE_SIZE
# if limit is None: — "check: did the caller give us nothing at all for limit?"
# return DEFAULT_PAGE_SIZE — if so, stop here and hand back the default page size (e.g., 20). return means "the function is done, here's the answer."
# python
#     return max(1, min(limit, MAX_PAGE_SIZE))

# This only runs if the if above was False — meaning the caller did give us an actual number for limit. This one line is doing two separate checks, from the inside out:

# Step A — min(limit, MAX_PAGE_SIZE): min() looks at two numbers and picks the smaller one. So if someone asked for limit=100000 but MAX_PAGE_SIZE is 100, min(100000, 100) picks 100. This stops a client from requesting an enormous, server-crushing page size.
# Step B — max(1, ...): max() picks the larger of two numbers. This wraps around Step A's result. So if someone asked for limit=-5 (a negative number, which makes no sense as a page size), Step A wouldn't fix that (since -5 is already smaller than 100, min would just return -5 unchanged) — so Step B catches it: max(1, -5) picks 1. This guarantees the final answer is never less than 1.

# Put together: this one line guarantees the returned number is always somewhere between 1 and MAX_PAGE_SIZE — never too big, never zero or negative.

# Function 2: paginate_queryset
# The signature
# python
# def paginate_queryset(queryset, *, limit=None, offset=0):
# queryset — the first input. A "queryset" is Django's way of representing "a set of database rows I might want" — it's like a request for data that hasn't actually been fetched yet.
# *, — this symbol means "everything listed after this must be given by name." So whoever calls this function must type paginate_queryset(my_data, limit=20, offset=0) — they can't just do paginate_queryset(my_data, 20, 0) and rely on position. This exists because limit and offset are both plain numbers — easy to accidentally swap by mistake if you didn't have to label them.
# limit=None — optional input, page size, defaults to nothing given.
# offset=0 — optional input, "how many rows to skip before starting this page" (e.g., offset=20 means "skip the first 20 rows, start from row 21") — defaults to 0 (don't skip anything, start from the very beginning).
# The docstring

# Explains: this function checks the total row count once, then grabs just one page of rows — never the whole table — and hands back both pieces.

# The body, line by line
# python
#     size = clamp_page_size(limit)

# Calls the function we just explained above, handing it whatever limit was given, and saves the safe, clamped result into a new name, size.

# python
#     offset = max(0, offset or  0)

# Two safety checks combined again:

# offset or 0 — if offset happens to be None (nothing given) or 0, this expression becomes 0 either way. (or here means: "use the first thing if it's meaningful/truthy, otherwise fall back to the second thing.")
# max(0, ...) — wraps that result and makes sure it's never negative. If someone passed offset=-10, max(0, -10) gives you 0 instead — you can't "skip negative rows," so this defends against that nonsensical input.
# python
#     total_count = queryset.count()

# Asks the database: "without fetching any actual rows, just tell me — how many rows total match this query?" This runs a very lightweight, fast database command (behind the scenes, it's like asking SELECT COUNT(*) — just a number, no actual data transferred).

# python
#     items = list(queryset[offset : offset + size])

# This is the real "get me one page of data" step, and it has two parts:

# queryset[offset : offset + size] — Python's slicing syntax, [start:end]. This says: "starting at row number offset, give me up to size rows after that." E.g., if offset=20 and size=20, this grabs rows 20 through 40 — the second page.
# list(...) — this is the moment the database actually runs and fetches those rows into real Python data you can use. Before this, the queryset was just a "plan" for data; wrapping it in list() forces it to actually go get the real rows right now.
# python
#     return items, total_count

# Hands back two values at once — the actual page of data (items) and the total row count (total_count) — separated by a comma. Whoever calls this function can do page_items, total = paginate_queryset(...) and get both pieces cleanly.

# One real design question for you

# Notice clamp_page_size(limit) is called without using limit= (it's called positionally: clamp_page_size(limit)), even though inside paginate_queryset's own signature, limit must be passed by name from the outside (*,). Why do you think it's fine to call clamp_page_size positionally here, but not fine to let outside callers pass limit/offset positionally into paginate_queryset? (Hint: think about how many inputs each function actually takes.) ->Why it's safe here: clamp_page_size only takes one input (limit). With only one thing to pass, there's no way to mix up "which value goes in which spot" — there's only one spot. Positional vs. named makes zero difference in safety when there's just one parameter.

# Why paginate_queryset needs the *, protection: it takes two same-type inputs side by side — limit and offset — both plain numbers. If someone called it positionally, like paginate_queryset(qs, 20, 0), meaning "limit 20, offset 0" — it's completely possible another programmer (or future-you, six months from now) calls it as paginate_queryset(qs, 0, 20) thinking "offset 0, limit 20," accidentally reversing them. Python wouldn't complain — both are just numbers — so the bug would be silent. Forcing limit= and offset= to always be written out removes that risk entirely, because now the meaning is stated every time, not just implied by position.

# The general rule to take away: the danger isn't "does this function have optional inputs" — it's "could two of its inputs be silently swapped without Python noticing, because they're the same type?" One input → no danger, positional is fine. Two-or-more same-type inputs → real danger, force keyword-only.

# core/pagination.py
# Level 1 — Big Picture

# Why does this file exist?
# Almost every list-returning query in your GraphQL schema — users, orders, products, roles — faces the same problem: a table can have thousands of rows, and a client should never be able to say "give me everything." Without pagination, Query.orders could return 500,000 rows in one response, saturating memory, network, and the client's ability to render it. This file is the one place that decides how "give me a page of results" is enforced, so every resolver across every app in your project gets consistent, safe behavior instead of each one inventing its own slicing logic.

# What problem does it solve, specifically?
# Two distinct problems, actually — worth separating them because the file separates them into two functions:

# Input safety — a client might request limit=999999 or limit=-5. Something has to defend the server from a malicious or careless client-supplied number. That's clamp_page_size.
# Efficient retrieval + metadata — once you know a safe limit, you still need to actually fetch a slice of rows and tell the client how many total rows exist (for "Page 3 of 47" UIs), without accidentally loading the entire table into memory to count it. That's paginate_queryset.

# Why is this responsibility placed in core, not in each app's selectors?
# Same reasoning as tasks.py — this is domain-agnostic infrastructure. Pagination doesn't know or care whether it's paginating Order objects or User objects; the logic is identical regardless of what queryset it's handed. Placing it in core means products, orders, staff selectors all call the same tested function instead of five slightly-different reimplementations, some of which would inevitably get the off-by-one or the unbounded-limit case wrong.

# What would happen if this file didn't exist?
# Each selector across your apps would hand-roll queryset[offset:offset+limit], and it's easy to imagine at least one of them forgetting to clamp limit, creating an accidental "return the whole table" endpoint — a real, common source of production incidents (an API that's fine until someone passes limit=1000000 and takes down the DB connection pool).

# Which architectural layer does this belong to?
# It sits below the selector layer — selectors call these functions, but this file itself doesn't know about Django models, permissions, or GraphQL types. It only knows about querysets in the abstract (it'll work on any queryset, from any app). That's a strong signal of correctly-scoped infrastructure code: it operates on Django's QuerySet interface, not on your business types.

# How does it communicate with the rest of the app?
# Pure function calls, no side effects, no I/O of its own beyond what queryset.count() and slicing trigger. A selector calls paginate_queryset(qs, limit=..., offset=...) and gets back a plain tuple — nothing here touches GraphQL types directly, keeping it reusable outside GraphQL too (e.g., a management command or REST-ish endpoint could use the same function).

# Before I go further into design thinking and the trade-offs baked into this specific implementation — since you've now been through the pattern once with tasks.py — try this first:

# Question for you: Look closely at paginate_queryset. It calls queryset.count() and then separately slices queryset[offset:offset+size]. That's two separate database queries against what might be the same underlying table state.

# Why not just do len(list(queryset)) once and get both the count and the items from a single query?
# Is there a race condition here — could total_count and the actual number of items returned ever become inconsistent with each other? If so, when, and does it actually matter for this use case?

# Take a shot at both before I explain the actual reasoning — this is exactly the kind of "why this, not that" trade-off Level 8 is built around, and it's worth you reasoning through the DB mechanics yourself first.


# Excellent question. This gets into how Django QuerySets, SQL, and database transactions work.

# The code

# Your pagination function is probably something like this:

# def paginate_queryset(queryset, offset=0, size=20):
#     total_count = queryset.count()
#     items = list(queryset[offset:offset + size])

#     return PaginationResult(
#         total_count=total_count,
#         items=items,
#     )

# This executes two SQL queries:

# SELECT COUNT(*) FROM users WHERE ...

# and later

# SELECT * FROM users
# WHERE ...
# LIMIT 20 OFFSET 40;
# Why not do this instead?
# items = list(queryset)
# total_count = len(items)

# This is only one SQL query, but it's usually a much worse idea.

# Suppose your table has

# 1,000,000 rows

# Your code would execute

# SELECT * FROM users;

# Django now loads

# every row
# every column
# every object

# into Python memory.

# Then

# len(items)

# counts them.

# Finally you only need

# items[40:60]

# Twenty rows.

# You just transferred a million rows over the network to display twenty.

# What .count() does

# Instead,

# queryset.count()

# becomes

# SELECT COUNT(*)
# FROM users;

# The database counts rows internally.

# No model instances are created.

# No rows are transferred.

# This is extremely efficient.

# What slicing does
# queryset[offset:offset+size]

# becomes

# SELECT *
# FROM users
# LIMIT 20 OFFSET 40;

# Only twenty rows travel to Python.

# So although there are two queries, the amount of work is much smaller than fetching everything.

# Could we avoid two queries?

# Sometimes.

# For example PostgreSQL supports window functions:

# SELECT *,
# COUNT(*) OVER() AS total_count
# FROM users
# LIMIT 20 OFFSET 40;

# Now every returned row also contains the total count.

# One query.

# Some ORMs can generate this.

# Django's paginator intentionally keeps things simple and portable across databases.

# Is there a race condition?

# Yes.

# Imagine this timeline.

# Initial table:

# A
# B
# C
# D
# E
# Query 1
# count = queryset.count()

# returns

# 5

# Now another user deletes a row.

# Table becomes

# A
# B
# D
# E

# Then Query 2 runs

# items = queryset[0:5]

# returns

# A
# B
# D
# E

# Only four rows.

# Your response is

# {
#     "total_count": 5,
#     "items": [
#         "A",
#         "B",
#         "D",
#         "E"
#     ]
# }

# The metadata says

# 5 rows

# but only four now exist.

# The opposite can also happen.

# Suppose

# count() -> 100

# Another request inserts five rows.

# Now

# LIMIT 20 OFFSET 80

# may return data based on a table containing 105 rows.

# Now

# total_count = 100

# is already stale.

# Why does this happen?

# Because each SQL statement typically observes the database independently under the default isolation level (commonly READ COMMITTED).

# The database does not guarantee that two separate SELECT statements see exactly the same snapshot unless you explicitly use a stronger transaction isolation level or other mechanisms.

# Does it matter?

# Usually no.

# Pagination is almost always eventually consistent.

# Suppose a user is browsing products.

# Page 1

# Someone creates a new product.

# Now

# Page 2

# looks slightly different.

# Nobody notices.

# Google, GitHub, Reddit, and many other applications all accept this behavior.

# The tiny inconsistency is far cheaper than locking tables or running more expensive transactions.

# When would it matter?

# It matters in systems where consistency is more important than performance, for example:

# Financial ledgers
# Bank balances
# Inventory reservations
# Audit reports
# Compliance exports

# In these cases you often use:

# transactions
# repeatable-read isolation
# snapshot isolation
# explicit locks

# so both queries see the exact same database state.

# In your RBAC project

# For your Strawberry GraphQL API, the current approach is the standard choice:

# total_count = queryset.count()
# items = queryset[offset:offset + size]

# It's efficient because:

# COUNT(*) lets the database compute the total without loading rows into Python.
# LIMIT/OFFSET fetches only the requested page.
# Any brief inconsistency caused by concurrent inserts or deletes is generally acceptable for administrative lists such as users, roles, or permissions.

# This is exactly the trade-off made by Django's own paginator and many production

# The race condition

# Yes, there genuinely is one, and here's exactly when it bites:

# python
# total_count = queryset.count()          # Query 1: "SELECT COUNT(*) ..." → returns, say, 100
# items = list(queryset[offset:offset+size])  # Query 2: "SELECT ... LIMIT/OFFSET ..." runs *milliseconds later*

# Between Query 1 and Query 2, the database is live — other requests are hitting it concurrently. If, in that gap, someone else's request inserts a new row, or deletes one, the table has already changed by the time Query 2 runs. Django doesn't run these two queries inside a shared transaction/snapshot by default — each is its own independent read against whatever the table looks like at that exact moment.

# Concretely: total_count might say 100, but if a row was deleted between the two queries, the actual slice returned by Query 2 reflects a 99-row table. If the client is on the last page, they might get one fewer item than total_count implied, or a "Page 5 of 5" that doesn't quite add up. Conversely, an insert between the two queries can make the reported total slightly stale by the time the client re-requests.

# Does it actually matter here? No — and it's worth being precise about why not, rather than just shrugging:

# This is a read-only, best-effort UI concern ("Page 3 of 47"), not a financial transaction or an inventory count where a stale number causes real harm (like overselling stock). Nobody's money or data integrity is at risk if a page count is off by one for a moment.
# The inconsistency window is measured in milliseconds and self-corrects on the next request — a user hitting refresh or paging forward gets fresh, consistent numbers again.
# Fixing it would cost something real: wrapping both queries in a single transaction with SELECT ... FOR SHARE or a serializable isolation level adds latency and DB lock contention to every single paginated list query across your entire app — a very expensive fix for a cosmetic, self-healing problem.

# General principle to extract: not every inconsistency needs to be engineered away. The right question is always "what's the actual cost of this race condition happening, versus the cost of preventing it?" Here, the cost of the race is a possibly-stale count in a non-critical UI element; the cost of prevention is transactional overhead on every list query in the system. Eventual consistency is the correct, deliberate choice — and recognizing when eventual consistency is fine (vs. when it's a real bug, like double-charging a customer) is a mark of senior judgment, not carelessness.

# Let's move to Level 2 now that the core trade-off is settled.

# Level 2 — Design Thinking (your turn again)

# Look at clamp_page_size:

# python
# def clamp_page_size(limit=None):
#     if limit is None:
#         return DEFAULT_PAGE_SIZE
#     return max(1, min(limit, MAX_PAGE_SIZE))
# Why max(1, min(limit, MAX_PAGE_SIZE)) instead of just min(limit, MAX_PAGE_SIZE)? What specific bad input does the max(1, ...) part defend against, and what would happen without it?
# Why is this a standalone function at all, rather than just inlining this one-liner directly inside paginate_queryset?
# There's no validation that limit is even an integer — what happens right now if a caller (or a malicious GraphQL client) passes limit="abc" or limit=3.7? Is that this function's problem to solve, or someone else's?

# 1. Why max(1, min(limit, MAX_PAGE_SIZE))?

# The function is:

# def clamp_page_size(limit=None):
#     if limit is None:
#         return DEFAULT_PAGE_SIZE
#     return max(1, min(limit, MAX_PAGE_SIZE))

# Think of it as enforcing an invariant:

# The page size must always be between 1 and MAX_PAGE_SIZE.

# The expression works in two steps.

# Step 1
# min(limit, MAX_PAGE_SIZE)

# ensures the value is not too large.

# Example:

# limit = 500
# MAX_PAGE_SIZE = 100

# min(500, 100)

# returns

# 100
# Step 2
# max(1, ...)

# ensures the value is not too small.

# Examples:

# limit = 0

# becomes

# max(1, 0)

# →

# 1
# limit = -10

# becomes

# max(1, -10)

# →

# 1
# What bad inputs does this defend against?

# Without the max():

# min(-50, 100)

# returns

# -50

# Now pagination becomes

# queryset[offset:offset + (-50)]

# or

# queryset[0:-50]

# Django interprets slicing similarly to Python slicing semantics in some cases, and negative values are not meaningful as page sizes. Depending on how the slice is formed, you could get unexpected behavior or errors rather than "return zero rows."

# Similarly,

# limit = 0

# would produce

# queryset[0:0]

# which returns an empty page.

# Is an empty page ever useful?

# Usually no.

# Most APIs define:

# A page size must be positive.

# So max(1, ...) guarantees that.

# Why not allow zero?

# You certainly could.

# Some APIs intentionally allow

# limit=0

# to mean

# "Give me only the metadata."

# Then you'd write

# max(0, ...)

# instead.

# It's a product decision.

# 2. Why make it a standalone function?

# Instead of

# page_size = max(1, min(limit, MAX_PAGE_SIZE))

# inside paginate_queryset, someone extracted

# clamp_page_size(limit)

# This is about separation of concerns.

# paginate_queryset should answer:

# How do I paginate?

# clamp_page_size answers:

# What is a valid page size?

# Those are different responsibilities.

# Benefit 1: Single source of truth

# Imagine six different resolvers:

# paginate_users()
# paginate_products()
# paginate_roles()
# paginate_permissions()
# paginate_orders()
# paginate_logs()

# Without a helper, every function repeats

# max(1, min(limit, MAX_PAGE_SIZE))

# If the rule changes later:

# minimum size should now be 5

# you update

# clamp_page_size()

# once.

# Done.

# Benefit 2: Easier to test

# You can test only this function.

# assert clamp_page_size(None) == 20
# assert clamp_page_size(1000) == 100
# assert clamp_page_size(-4) == 1
# assert clamp_page_size(5) == 5

# No database.

# No queryset.

# Very small unit test.

# Benefit 3: Better readability

# Compare

# page_size = max(1, min(limit, MAX_PAGE_SIZE))

# vs

# page_size = clamp_page_size(limit)

# The second reads almost like English.

# 3. What happens with limit="abc"?

# Current implementation:

# min(limit, MAX_PAGE_SIZE)

# becomes

# min("abc", 100)

# Python raises

# TypeError:
# '<' not supported between instances of 'int' and 'str'

# because Python cannot compare a string and an integer.

# 4. What about limit=3.7?

# That actually works.

# min(3.7, 100)

# returns

# 3.7

# Then

# page_size = 3.7

# Eventually Django sees

# queryset[:3.7]

# which raises something like

# TypeError:
# slice indices must be integers

# because slice boundaries must be integers (or objects implementing __index__).

# 5. Should this function validate types?

# Generally, no.

# This function assumes:

# I receive an int or None.

# That assumption is usually guaranteed by the layer above.

# For example, in Strawberry GraphQL:

# limit: int | None

# If a client sends

# {
#     users(limit: "abc")
# }

# GraphQL validates the input before your resolver is called.

# The resolver never executes.

# The client gets a GraphQL validation error.

# Likewise,

# {
#     users(limit: 3.7)
# }

# is rejected because an Int cannot be a floating-point value.

# So in a properly typed GraphQL API, clamp_page_size() should only ever receive an int or None.

# Should it ever validate types?

# It depends on how broadly you intend to reuse it.

# If it's an internal helper that's only called from strongly typed code (like GraphQL resolvers), relying on the caller's contract is reasonable and keeps the function simple.

# If you expect it to be used from untyped sources (query parameters, CLI arguments, JSON payloads, etc.), you might either:

# perform explicit type checks and raise a clear TypeError or ValueError, or
# convert values (int(limit)) if coercion is part of the intended API.

# The key is that validation should happen at the boundary where untrusted input enters the system. Internal utility functions generally assume they've already been given values of the correct type.

# Design takeaway

# clamp_page_size() has one focused responsibility:

# Normalize a valid integer page size into the allowed range.

# It is not responsible for parsing user input or validating GraphQL values—that responsibility belongs to the input layer (GraphQL schema, REST serializer, form, CLI parser, etc.). This separation keeps each layer simple and predictable.

# Level 15 — Quick Knowledge Check for this file, then we move on

# Debugging scenario: A teammate reports that paginate_users(limit=100000) in production returns fine — no error — but a support ticket says a client requested limit=100000 expecting 100,000 rows and got only 100 back, with no error message telling them why. Is this a bug? What, if anything, should change?

# Architecture scenario: Right now paginate_queryset always executes queryset.count(), even when a resolver only cares about the items and never uses total_count (say, an infinite-scroll UI with no page numbers). Is this wasteful? Would you change the function signature to make the count optional, and what would that cost in terms of the two-tuple return contract every caller currently relies on?

# Take a shot at both, then send the next file whenever you're ready — core/ or wherever you want to go next.

# These are the kinds of questions senior engineers ask because there isn't a single objectively correct answer—it's about API design and trade-offs.

# Scenario 1: limit=100000 returns only 100 rows

# Suppose:

# MAX_PAGE_SIZE = 100

# and

# paginate_users(limit=100000)

# returns exactly 100 items.

# Is this a bug?

# Technically, no.

# The function is doing exactly what it was designed to do.

# page_size = clamp_page_size(limit)

# intentionally prevents excessively large requests.

# This protects the server from requests like

# limit=100000
# limit=1000000
# limit=999999999

# which could:

# consume huge amounts of memory
# create long-running database queries
# slow down the API for everyone
# accidentally DOS your own service

# So clamping is a defensive measure.

# Why did the client think it was a bug?

# Because the API silently changed their request.

# They asked for

# 100000

# The server answered

# 100

# without explaining why.

# From the client's perspective:

# "The API ignored my input."

# That's confusing.

# What are the possible designs?

# There are three common approaches.

# Option 1 — Silent clamp (current)
# Request:
# limit=100000

# Response:
# 100 items

# Pros

# Never fails
# Simple implementation
# Protects the server

# Cons

# Client doesn't know the limit
# Can hide mistakes
# Harder to debug

# Many APIs do this.

# Option 2 — Validation error

# Instead:

# GET /users?limit=100000

# returns

# {
#     "error": "limit must not exceed 100"
# }

# Pros

# Honest
# Predictable
# Client immediately fixes the request

# Cons

# Existing clients may start receiving errors
# Slightly less forgiving

# This is my preferred design when the API contract clearly states a maximum page size.

# Option 3 — Clamp but tell the client

# Return

# {
#     "totalCount": 5000,
#     "pageSize": 100,
#     "requestedPageSize": 100000,
#     "items": [...]
# }

# or

# {
#     "pageSize": 100,
#     "maxPageSize": 100
# }

# Now the client learns

# "The server reduced your request."

# Best of both worlds.

# Which would I choose?

# If this is a public API, I'd generally prefer either:

# reject invalid requests with a clear validation error, or
# clamp and explicitly communicate the effective page size.

# Silently changing client input makes integrations harder to reason about.

# If this is an internal admin dashboard, silent clamping is often perfectly acceptable because the frontend is under your control and already knows the limit.

# Scenario 2: count() is always executed

# Current implementation

# total = queryset.count()
# items = list(queryset[offset:offset+size])

# always performs

# SELECT COUNT(*)

# followed by

# SELECT ...
# LIMIT ...
# Is this wasteful?

# Sometimes.

# Imagine an infinite-scroll UI.

# It only needs

# next 20 users

# It doesn't care whether there are

# 500

# or

# 5,000

# remaining.

# The count query becomes unnecessary work.

# On very large tables, COUNT(*) can be one of the more expensive operations, depending on the database, indexes, and query complexity.

# Should we make counting optional?

# One possible API is

# paginate_queryset(
#     queryset,
#     offset,
#     limit,
#     include_count=True,
# )

# Then

# paginate_queryset(..., include_count=False)

# would only execute

# SELECT ...
# LIMIT ...

# One query instead of two.

# What would this cost?

# The current API is probably something like

# total_count, items = paginate_queryset(...)

# Every caller assumes

# this function always returns two values.

# If you skip the count, what should happen?

# Option A

# Return

# (None, items)

# The contract remains stable.

# total_count, items = paginate_queryset(...)

# still works.

# Callers simply check

# if total_count is not None:
#     ...

# This is usually the least disruptive approach.

# Option B

# Return only items

# items = paginate_queryset(...)

# Now you've broken every caller.

# Every resolver becomes

# if include_count:
#     total, items = paginate_queryset(...)
# else:
#     items = paginate_queryset(...)

# Much messier.

# Option C

# Return an object

# Instead of

# (total, items)

# return

# PaginationResult(
#     items=...,
#     total_count=None,
# )

# Now the shape never changes.

# result.items
# result.total_count

# If the count wasn't requested,

# result.total_count

# is simply

# None

# This is one reason many APIs return a structured object rather than a tuple: it's easier to evolve over time.

# Would I change it?

# It depends on how often callers don't need the count.

# If almost every resolver returns total_count to clients, always performing count() keeps the API simple and the extra query is justified.
# If many resolvers only need the items (for example, infinite scrolling, autocomplete, or background processing), making the count optional can save a database query on those hot paths.

# If I were designing this from scratch, I'd likely expose an option such as:

# paginate_queryset(..., include_count=False)

# and return a result object whose total_count is None when omitted. That preserves a consistent return type while allowing callers to avoid unnecessary work.

# A broader architectural consideration

# There's also an API design question: should pagination always expose total_count?

# Traditional page-number UIs ("Page 3 of 42") genuinely need it.

# Infinite-scroll UIs often don't. They only need to know whether there is another page. In those cases, a common optimization is to fetch limit + 1 rows:

# If you request 21 rows with a page size of 20 and get 21 back, there is another page.
# Return the first 20 rows and set has_next = True.
# If you get 20 or fewer rows, has_next = False.

# That avoids the COUNT(*) query entirely while still giving the frontend the information it needs. This is one reason cursor-based pagination is popular for large datasets—it avoids expensive counts and scales better than offset-based pagination for many workloads.

# Imports, Signatures, and Bodies — core/pagination.py
# Import
# python
# from rbac.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

# This pulls two named constants from a dedicated constants.py module rather than hardcoding numbers (20, 100) directly in this file. This matters for the same reason send_email_task read from_email from settings instead of taking it as a parameter: project-wide policy values belong in one canonical location, not scattered as magic numbers across every file that needs them.

# Concretely, this means:

# If product decides "our default page size should be 25, not 20," you change one line, in constants.py, and every paginated resolver across every app picks it up automatically.
# If DEFAULT_PAGE_SIZE were hardcoded as 20 inline here, and some other file also hardcoded 20 for a different reason, those two 20s are actually unrelated — but they'd look identical in code, inviting someone to "helpfully" change one when they meant to change the other. Named constants prevent that ambiguity.

# Also worth noting: constants.py is pure data — no functions, no logic, just values. That's deliberate; it means this module can be imported from literally anywhere (including migrations, management commands, tests) without dragging in Django ORM setup, GraphQL types, or anything with side effects. A common, low-risk import.

# clamp_page_size
# python
# def clamp_page_size(limit=None):

# Signature note — this one is not keyword-only, and it's worth noticing that consciously rather than skimming past it. Compare this to send_email_task's *, subject, message, recipient_list. Why the difference?

# This is a small, single-purpose utility likely to be called as clamp_page_size(limit) positionally, in tight internal code (like line 2 of paginate_queryset below), where there's no ambiguity about what the one argument means — there's only one parameter, so there's no ordering mistake to protect against. Keyword-only argument enforcement earns its value when a function has multiple parameters where transposing them would be a silent, hard-to-catch bug (subject and message are both strings — swap them by accident, and Python won't complain, but your emails go out wrong). With a single parameter, that risk doesn't exist, so the extra ceremony of forcing limit=... at every call site would be pure friction with no safety benefit.

# General principle to bank: keyword-only enforcement is a tool for a specific failure mode (positional argument transposition), not a blanket style rule to apply everywhere. Apply it where it protects against a realistic mistake; skip it where it doesn't.

# python
#     if limit is None:
#         return DEFAULT_PAGE_SIZE

# Explicit None check, not if not limit. This distinction matters and is worth being precise about: if not limit would also be True for limit=0, silently treating "the client explicitly asked for zero" the same as "the client didn't specify anything." Given your own Q1 answer — that limit=0 is arguably a legitimate product decision, not automatically invalid — using is None here is the correct choice: it distinguishes "not provided" (→ use the default) from "provided as zero" (→ falls through to the max(1, ...) line below, which happens to also floor it to 1 in this implementation, but that's a separate, deliberate policy decision, not an accident of using not limit).

# python
#     return max(1, min(limit, MAX_PAGE_SIZE))

# Already covered thoroughly above — the two-stage clamp, correctly explained in your answer.

# paginate_queryset
# python
# def paginate_queryset(queryset, *, limit=None, offset=0):

# Here, by contrast, keyword-only is used (* before limit/offset) — and now you can articulate exactly why, using the principle above: limit and offset are both integers, both commonly small numbers, and transposing them (paginate_queryset(qs, 0, 20) meaning "offset=0, limit=20" vs. accidentally meaning the reverse) is a completely plausible, silent bug — nothing about the types would catch it. queryset itself stays positional since there's only one queryset argument and no similar-typed sibling to confuse it with.

# python
#     size = clamp_page_size(limit)

# Delegates to the function just discussed — paginate_queryset doesn't know or care how a valid size is determined, only that this line guarantees it received one. This is composition in action: two small functions, each with one job, combined to do the full task.

# python
#     offset = max(0, offset or 0)

# This line is doing two things worth separating:

# offset or 0 — defends against offset=None being passed explicitly (falls back to 0). Note this uses or, not is None — meaning offset=0 and offset=None both produce 0 here, which is actually fine since 0 is already the value you'd want in either case (unlike the limit/None-vs-0 distinction above, there's no meaningful difference between "no offset specified" and "offset explicitly zero" — both mean "start from the beginning").
# max(0, ...) — defends against a negative offset (e.g., offset=-10), which would otherwise hit that same Django AssertionError: Negative indexing is not supported we discussed for negative limits.
# python
#     total_count = queryset.count()
#     items = list(queryset[offset : offset + size])

# The two-query pattern from your earlier, well-reasoned answer. One detail worth flagging precisely: list(...) around the slice forces immediate evaluation of the queryset slice into an actual Python list, right here, inside this function. Without the explicit list(), queryset[offset:offset+size] would still be a lazy queryset — Django wouldn't hit the database until something iterates it (e.g., later, when GraphQL serializes the response). Forcing evaluation here, inside a function whose whole job is "go fetch this page," keeps the laziness contained — the caller gets back a concrete, already-fetched list, not a lazy object that might unexpectedly re-query if iterated twice, or that defers a DB error to a confusing, distant point in the code.

# python
#     return items, total_count

# Plain tuple return — exactly the design point interrogated in Scenario 2 above. Worth noting the order: items, total_count, not total_count, items. This is a minor but real readability choice — most callers care about the actual data first and the metadata second, so items, total_count = paginate_queryset(...) reads naturally left-to-right in order of importance. A small thing, but consistent ordering across a codebase (always data-then-metadata, never mixed) is the kind of convention that makes code predictable to skim.