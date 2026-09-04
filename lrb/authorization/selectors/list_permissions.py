from typing import Optional
from lrb.authorization.models.permission import Permission

def list_permissions(*, category: Optional[str] = None):
    qs = Permission.objects.all()
    if category:
        qs = qs.filter(category=category)
    return qs.order_by("category", "codename")


# Teaching: list_permissions

# This one's short, but it introduces a few genuinely new ideas: default parameter values, optional filtering, and a missing return type hint worth noticing. Since the selector shape (*, keyword-only, Permission.objects, lazy querysets) is exactly what you just learned in get_permission, I won't re-explain those — just the new pieces.

# 1 & 2. What's new here, and how it's written

# category: Optional[str] = None
# Two things are stacked on one parameter:

# Optional[str] — the type hint, same as before: "either a string, or None."
# = None — a default value. If the caller doesn't pass category at all, Python fills it in with None automatically, instead of raising an error demanding it.

# Why does this pairing matter? A type hint and a default value are two separate things that happen to often travel together, but they do different jobs:

# The type hint (Optional[str]) tells readers/tools "what shape of value is allowed here."
# The default value (= None) tells Python "what to use if nothing is provided."
# You could technically have a default without a matching Optional hint (bad practice — misleading), or Optional without a default (then the caller would be forced to explicitly pass None). Here they agree with each other, which is the correct, honest way to write it: "this parameter is optional, and here's exactly what 'not provided' looks like."

# Why is this useful? It lets one function serve two different calls:

# python
# list_permissions()                       # get everything
# list_permissions(category="orders")      # get just one category

# No need for two separate functions — category's presence or absence branches the behavior inside.

# qs = Permission.objects.all()
# .all() is a QuerySet method meaning "give me every row, unfiltered." Like .filter(...), this is still lazy — no database query has run yet, this just builds "select everything" as the starting query.

# if category:
# A truthiness check on a string. Remember from get_current_user_or_raise: Python treats things as False if they're empty/None. An empty string "" and None are both falsy; any non-empty string is truthy. So this line means: "only apply the category filter if the caller actually gave us a real, non-empty category string." If category is None (the default) or someone explicitly passed "", this if is False, and the filter step below is skipped entirely.

# qs = qs.filter(category=category)
# This is reassignment — take the existing queryset qs, narrow it further with .filter(...), and store the new, more restrictive queryset back into the same variable name qs. This is a common pattern for conditionally building up a query step by step: start broad, then narrow based on what inputs were actually given. If you had three optional filters, you'd repeat this shape three times — if x: qs = qs.filter(...) — chaining narrower and narrower queries.

# return qs.order_by("category", "codename")
# .order_by(...) takes one or more field names and returns a new queryset sorted by them — multiple arguments means multi-level sorting: first sort by category, and within each category, sort by codename. Think of it like sorting a spreadsheet by column A, then by column B as a tiebreaker for rows that share the same column-A value.

# 3. Signature — broken into pieces
# python
# def list_permissions(*, category: Optional[str] = None):
# Piece	Meaning
# def list_permissions(	defining a function named list_permissions
# *,	forces category to be passed by keyword only
# category	the parameter name
# : Optional[str]	type hint — string or None
# = None	default value if not provided
# )	end of parameter list
# :	body starts below

# Notice what's missing: there's no -> ... return type hint here, unlike your previous two functions. This is a small inconsistency worth flagging (see section 7) — the function returns a Django QuerySet[Permission], and a fully-typed version would say so.

# 4. Body — line by line
# python
# qs = Permission.objects.all()

# Start with "every permission" as an (unexecuted) query, stored under the name qs.

# python
# if category:
#     qs = qs.filter(category=category)

# If a real category string was passed in, narrow the query to only that category, replacing qs with the narrower version. If not, qs stays as "everything."

# python
# return qs.order_by("category", "codename")

# Apply sorting to whichever queryset we ended up with (filtered or not), and hand it back to the caller. This is also the moment the actual SQL query gets finalized — but still not executed yet. It only actually runs against the database once something iterates over it (like a for loop, or Strawberry serializing it into a GraphQL list response).

# 5. Why?

# Why build the query in steps (qs = ..., then maybe qs = qs.filter(...)) instead of one big expression?
# Because the filtering is conditional — you don't know until runtime whether category was given. Writing it as a multi-step, reassigned variable is the natural way to express "start here, then maybe add this constraint" in Python. Compare this to get_permission, where the whole query was known upfront and fit on one line — here it genuinely branches, so it needs more than one line.

# Why sort by two fields?
# This function is a list view — likely used to populate something like a permissions-management screen in the frontend. Grouping by category first, then alphabetically by codename within each group, produces a predictable, readable order for a UI to display (e.g., grouped sections: "Orders" category showing orders.create, orders.delete, orders.view in order; then "Staff" category, etc.) — rather than arbitrary database insertion order.

# Why default to None and skip filtering, rather than requiring category always be passed?
# This selector serves two real use cases from one function: "give me all permissions" (for an admin screen showing every permission grouped by category) and "give me permissions in this one category" (maybe for a smaller, scoped picker). Making category optional avoids needing two nearly-identical functions.

# 6. Connections

# What comes in: an optional category string.
# What goes out: a Django QuerySet of Permission objects — not a Python list. This is worth understanding: a queryset is still lazy and database-connected when it leaves this function. Whoever calls list_permissions() can keep chaining more filters onto it, or it can be handed straight to a GraphQL resolver that will iterate it lazily when serializing the response. This is different from get_permission, which returns a single, already-resolved object (or None) — .first() forced execution; nothing here does.

# Where this fits: almost certainly backs a GraphQL query like permissions(category: String) — a frontend admin screen listing available permissions, optionally filtered by category, to help an admin build up a role.

# 7. Advanced concepts

# A) Missing return type hint — a real inconsistency
# Your last two functions were carefully typed (-> Optional[Permission], and your project convention calls for type hints on service functions generally). This one has none. The honest hint would be:

# python
# from django.db.models import QuerySet

# def list_permissions(*, category: Optional[str] = None) -> QuerySet[Permission]:

# Worth flagging as drift from your established pattern — good instinct to notice and correct this kind of thing as you read real code.

# B) Lazy chaining across conditional branches
# This is a slightly more advanced use of laziness than get_permission showed: because nothing executes until the very end, you can build a query across multiple lines and even conditional branches, and Django will still combine everything into one efficient SQL statement at execution time — it doesn't run one query for .all() and a second one for .filter(). Understanding "no database work has happened yet" at every point before the final trigger is key to reasoning about Django code correctly.

# C) .order_by() with multiple arguments
# Order matters in the argument list: .order_by("category", "codename") is not the same as .order_by("codename", "category") — the first argument is the primary sort key, later arguments only break ties within groups that share the same value for earlier keys.

# 8. Small example
# python
# data = [
#     {"category": "orders", "codename": "orders.delete"},
#     {"category": "staff", "codename": "staff.invite"},
#     {"category": "orders", "codename": "orders.create"},
# ]

# def list_permissions(category=None):
#     result = data
#     if category:
#         result = [p for p in result if p["category"] == category]
#     return sorted(result, key=lambda p: (p["category"], p["codename"]))

# for p in list_permissions():
#     print(p)
# # orders.create, orders.delete, then staff.invite — grouped, then alphabetical
# 9. What you should remember
# param: Optional[X] = None pairs a type hint with a default value — the hint says "this could be missing," the default says exactly what "missing" looks like at runtime. Keep them consistent.
# if some_string: is a truthiness check — both None and "" are falsy; use this pattern to mean "only if a real value was given."
# Reassigning a queryset (qs = qs.filter(...)) inside a conditional is the standard way to build a query step by step when some filters are optional.
# Querysets stay lazy across multiple chained/conditional steps — nothing hits the database until the result is actually consumed (looped, listed, or serialized).
# Compare functions against each other, not just in isolation — noticing that this function skips the return type hint your other selectors have is exactly the kind of pattern-drift worth catching as you read more of a real codebase.