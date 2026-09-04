from lrb.authorization.models.role import Role


def list_roles(*, company_id: str):
    return Role.objects.filter(company_id=company_id).prefetch_related(
        "permissions", "user_roles__user"
    )


# Teaching: list_roles

# Short function, but it introduces one genuinely new and important Django concept: prefetch_related — plus a subtle syntax detail ("user_roles__user") worth unpacking carefully. Everything else (*,, required keyword param, .filter()) you already know from the last three functions.

# 1. What is it?

# A selector that returns all roles belonging to one company, pre-loading their related permissions and the users assigned to them, so that displaying a role list (with its permissions and members) doesn't trigger a flood of extra database queries.

# New pieces:

# .prefetch_related(...) — a queryset method
# "permissions" and "user_roles__user" — string arguments to it, including the __ (double underscore) syntax
# 2. How is it written?

# company_id: str — no Optional, no default

# python
# def list_roles(*, company_id: str):

# Unlike get_role, where company_id was optional, here it's required — plain str, no = None, no Optional[...]. This is a meaningful design choice, not an accident (more in section 5).

# .prefetch_related("permissions", "user_roles__user")
# This is a performance-optimization method on a queryset. To understand why it exists, you need to understand the problem it solves first — the N+1 query problem.

# Imagine Role has a many-to-many relationship to Permission (a role has many permissions, a permission can belong to many roles). If you just did:

# python
# roles = Role.objects.filter(company_id=company_id)
# for role in roles:
#     print(role.permissions.all())   # accessing related data

# Django would run one query to get the roles, and then one additional query per role to fetch that role's permissions — if there are 20 roles, that's 21 total queries. This is the N+1 problem: 1 query for the main list, plus N more queries (one per item) for related data.

# .prefetch_related("permissions") fixes this: it tells Django, "I know I'm about to access .permissions on every role in this queryset — go ahead and fetch all of that related data in one extra query (or a couple), right now, instead of waiting to be asked one row at a time." Django then quietly caches the results, so when your code later loops through and accesses role.permissions.all(), it's reading from memory, not hitting the database again.

# Why two separate string arguments, "permissions" and "user_roles__user", instead of one?
# Because they're two independent relationships you want pre-loaded — Permission records and User records (via role assignments) are unrelated to each other, so each needs its own prefetch instruction. You pass as many relationship names as you need, comma-separated.

# "user_roles__user" — the double-underscore (__) traversal syntax
# This is Django's way of writing "follow a relationship, then follow another relationship from there" as a single string. Read it left to right:

# user_roles — this is the related name for some other model (probably a UserRole junction/through model, connecting users to roles — common in RBAC systems where you need extra info on the assignment itself, like "assigned by whom, when").
# __ — "now, from each of those, go one level deeper."
# user — from each UserRole object, follow its user field to get the actual User.

# So "user_roles__user" means: "prefetch this role's UserRole assignment records, and prefetch the actual User object each assignment points to, all in one go" — saving you from needing two separate prefetch_related calls, and saving Django from running queries at each level separately when you eventually access role.user_roles.all()[0].user.

# This __ syntax is the same double-underscore convention Django uses throughout its ORM (you'll also see it in .filter(company__name="Acme")-style lookups) — it always means "traverse into a related object's field."

# 3. Signature — broken into pieces
# python
# def list_roles(*, company_id: str):
# Piece	Meaning
# *,	company_id must be passed by keyword
# company_id: str	required (no default) — every caller must supply it
# no ->	(missing return type hint — same drift you already spotted in list_permissions; the honest hint would be -> QuerySet[Role])
# 4. Body — line by line
# python
# return Role.objects.filter(company_id=company_id).prefetch_related(
#     "permissions", "user_roles__user"
# )

# Read this as one chained pipeline, left to right this time (each step transforms the queryset from the last):

# Role.objects — start at the manager for the Role table.
# .filter(company_id=company_id) — narrow to only this company's roles.
# .prefetch_related("permissions", "user_roles__user") — attach instructions: "when this queryset is eventually executed, also fetch each role's permissions, and each role's assigned users, efficiently, in a small number of extra queries rather than one query per role."
# return — hand the still-lazy, still-not-yet-executed queryset back to the caller, now carrying these prefetch instructions along with it.

# Nothing hits the database yet, even after .prefetch_related(...) — that's still just adding to the query plan. Execution only happens when something iterates this queryset (a GraphQL resolver serializing the list, a for loop, etc.), at which point Django runs the main query and the prefetch queries together as a batch.

# 5. Why?

# Why is company_id required here, but optional in get_role?
# This is a meaningful, correct difference — not inconsistency. Think about the shape of each function's job:

# get_role(role_id, company_id=None) — you already have a specific ID; company_id is an extra safety check layered on top of an otherwise-precise lookup. In rare, deliberate contexts (like a superuser tool), you might reasonably want to skip that check.
# list_roles(company_id) — there is no ID to narrow by at all. Without company_id, this function would return every role for every company in the entire system — a serious data leak, and almost certainly never what any caller wants. Making it required removes the possibility of accidentally calling this with no scoping at all. Good design: when a missing filter would be catastrophic rather than just occasionally-useful-to-skip, make it mandatory, not optional.

# Why prefetch instead of just querying normally and letting related data load "lazily" as needed?
# Because this selector is almost certainly feeding a list view — a UI screen showing many roles at once, each displaying its permissions and assigned users. If you don't prefetch, and the resolver or template loops through, say, 15 roles and touches .permissions.all() and .user_roles.all() on each one, that's 15 × 2 = 30 extra queries beyond the first one. prefetch_related collapses that down to a small, fixed number of queries regardless of how many roles there are — a huge, predictable performance win for exactly this "list with nested related data" shape.

# 6. Connections

# What comes in: company_id — the current caller's company, almost certainly current.company_id.
# What goes out: a QuerySet[Role], still lazy, but pre-loaded with .permissions and .user_roles.user relationships ready for efficient access.
# Where this fits: feeds directly into a GraphQL query like roles: [RoleType] — a resolver that needs to return roles along with their nested permissions and member lists in one response. This is exactly the situation prefetch_related was built for: GraphQL resolvers frequently need to serialize nested relationships, and without prefetching, a naive resolver would silently generate massive numbers of queries per request (a very common real-world GraphQL performance bug, called the "N+1 problem in GraphQL resolvers").

# 7. Advanced concepts

# A) prefetch_related vs. select_related (a distinction worth knowing, even though this file only uses one)
# Django actually has two tools for this kind of problem:

# select_related — used for "single-valued" relationships (a role has one company, via a ForeignKey). It works by adding a SQL JOIN, pulling everything into one query.
# prefetch_related — used for "multi-valued" relationships (a role has many permissions, many user assignments — many-to-many or reverse-foreign-key relationships). A JOIN doesn't work cleanly here because it would multiply/duplicate rows, so Django instead runs a second, separate query for the related data and stitches it together in Python.
# This function uses prefetch_related for both, which tells you permissions and user_roles are both "many" relationships on Role — consistent with a role having many permissions and many assigned users.

# B) The __ traversal can go more than two levels deep
# "user_roles__user" goes two levels (role → user_roles → user). Django allows chaining further — "user_roles__user__company" would go a third level, if you needed it. This is a general-purpose relationship-traversal syntax, not something specific to prefetch_related — the same __ pattern is used in .filter() lookups too (e.g., .filter(user_roles__user__is_active=True)).

# C) Prefetching doesn't change what rows come back — only how efficiently related data is fetched afterward
# It's worth being clear: .prefetch_related(...) never filters or changes the main Role results. It's purely an optimization instruction layered on top of an otherwise-identical query — this is why it's safe to always chain it onto queries feeding list views, without worrying it'll change your results.

# 8. Small example (conceptual, since prefetching needs a real database to demonstrate meaningfully)
# python
# # WITHOUT prefetch_related — 1 query for roles + 1 query per role for permissions
# roles = Role.objects.filter(company_id="A")
# for role in roles:
#     print(role.permissions.all())   # extra DB hit, every single loop

# # WITH prefetch_related — 1 query for roles + 1 batch query for ALL permissions at once
# roles = Role.objects.filter(company_id="A").prefetch_related("permissions")
# for role in roles:
#     print(role.permissions.all())   # reads from memory, no extra DB hit
# 9. What you should remember
# prefetch_related(...) batch-loads "many" relationships (many-to-many, or reverse foreign keys) ahead of time, turning "one query per row" into "one extra query total" — always reach for it when a list view will access related data on every item.
# select_related is the equivalent tool for "one" relationships (a ForeignKey pointing to a single related object) — different mechanism (SQL JOIN), same underlying goal.
# "a__b" (double underscore) means "traverse into a related object's field," and can chain multiple levels deep — this is a general Django ORM convention, used both in .filter() lookups and in prefetch_related/select_related arguments.
# Whether a scoping parameter should be optional or required depends on the consequence of omitting it. get_role's company_id could reasonably be optional (a precise ID lookup, occasionally skippable by design); list_roles's company_id should be mandatory (omitting it would leak every company's data) — recognize this distinction rather than treating "keyword-only optional filter" as one universal pattern.
# A queryset with .filter() and .prefetch_related() chained together is still entirely lazy — no database work happens until the queryset is actually consumed (looped, listed, serialized). The prefetch instructions just ride along, waiting to be triggered efficiently all at once.