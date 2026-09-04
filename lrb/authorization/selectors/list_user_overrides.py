from lrb.authorization.models.user_role import UserPermissionOverride

def list_user_overrides(*, user_id: str):
    return UserPermissionOverride.objects.filter(user_id=user_id).select_related("permission")


# Teaching: list_user_overrides

# This one reuses almost every pattern you already know — but it's the perfect place to actually explain select_related, which I mentioned last time only in passing. There's also a naming detail and a scoping gap worth catching, matching your instinct to spot drift.

# 1. What is it?

# A selector that returns every permission override belonging to one specific user — with that override's related Permission object pre-loaded efficiently. A "permission override" in an RBAC system typically means: a specific permission granted or revoked for this one user, layered on top of whatever their role normally grants — an exception to the role-based rule.

# New piece: .select_related("permission").

# 2. How is it written?

# The import line — a naming detail worth noticing

# python
# from lrb.authorization.models.user_role import UserPermissionOverride

# The class being imported is UserPermissionOverride, but it's coming from a file called user_role.py. This tells you the class's name and its file location don't perfectly match — probably because this model is closely related to (or defined alongside) role-assignment logic in the same file. Not a bug, just something to notice: the import path tells you where code lives, not necessarily what it's called — always trust the actual name after import, not the module name, when reasoning about what a class does.

# .select_related("permission")
# Now the real new concept. You already learned .prefetch_related(...) in list_roles, used for "many" relationships (many-to-many, or reverse foreign keys). select_related is the sibling tool, used for "one" relationships — specifically, when the current model has a ForeignKey pointing to exactly one related object. Here, each UserPermissionOverride almost certainly has a ForeignKey to a single Permission (this one override is about one specific permission).

# The mechanical difference matters:

# .prefetch_related("permissions") (last file) → Django runs a second, separate query, then stitches the results together in Python — needed because "many" relationships can't be safely flattened into one row via a SQL JOIN without duplicating data.
# .select_related("permission") (this file) → Django adds a SQL JOIN directly into the one query it already has to run — because each override has exactly one permission, the database can safely widen each row to include that permission's columns too, with no risk of duplication or multiplication.

# Same goal (avoid the N+1 problem — don't run one extra query per row when you access .permission later), different mechanism, chosen based on whether the relationship is "one" or "many."

# Everything else is fully familiar to you now:

# *, user_id: str — keyword-only, required (no default, no Optional) — same reasoning as list_roles's company_id: without a user_id, this function would leak every override for every user in the system, so it's correctly made mandatory.
# .filter(user_id=user_id) — narrow to this one user's overrides.
# No return type hint — same drift pattern you've now spotted three times (list_permissions, list_roles, and here).
# 3. Signature — broken into pieces
# python
# def list_user_overrides(*, user_id: str):
# Piece	Meaning
# *,	user_id must be passed by keyword
# user_id: str	required — no default, so every caller must scope this to one user
# no ->	missing return type hint (should be -> QuerySet[UserPermissionOverride])
# 4. Body — line by line
# python
# return UserPermissionOverride.objects.filter(user_id=user_id).select_related("permission")
# UserPermissionOverride.objects — enter the manager for the override table.
# .filter(user_id=user_id) — narrow to only rows belonging to this specific user (still lazy).
# .select_related("permission") — attach a JOIN instruction: "when this query finally runs, also pull in each override's related Permission row, in the same single query, so accessing .permission later doesn't trigger a separate database hit."
# return — hand back the still-unexecuted, JOIN-annotated queryset.

# Same "still lazy" rule as every selector before it — nothing executes until something consumes this queryset later.

# 5. Why?

# Why select_related here but prefetch_related in list_roles?
# This comes down to the actual relationship type, and it's the single most important thing to internalize from these two functions together:

# Role → Permission was many-to-many (a role has many permissions) → needed prefetch_related.
# UserPermissionOverride → Permission is (almost certainly) a single ForeignKey — each override row is about exactly one permission → needs select_related.

# A good habit: before reaching for either method, ask "from the object I'm querying, is the related thing singular (one ForeignKey) or plural (many-to-many / reverse FK)?" That answer picks the tool.

# Why prefetch/select the permission at all?
# Because this is a list of overrides that will almost certainly be displayed together with what permission each override refers to (e.g., "User X: orders.delete — GRANTED (override)"). Without select_related, accessing .permission.codename on each override in a loop would trigger one extra query per override — the same N+1 problem, just via the "one" relationship version instead of the "many" version.

# Why is user_id required?
# Exactly the same reasoning as list_roles's company_id: this function's entire purpose is "overrides for one user." Making it optional would allow — maybe even invite — a caller to accidentally fetch every user's overrides across the whole system, a real data-leak risk in a multi-tenant app.

# 6. Connections

# What comes in: user_id — likely from an admin screen viewing/editing one specific user's effective permissions.
# What goes out: a lazy QuerySet[UserPermissionOverride], JOIN-optimized to include each override's Permission without extra queries.
# Where this fits: this is almost certainly one ingredient in computing a user's effective permissions — role-based permissions (from list_roles/role assignments) plus these individual overrides layered on top. A service like get_effective_permissions(user_id=...) would likely call both list_roles-style lookups and this function, then merge the results (role permissions, with per-user overrides applied on top) — a common, more flexible RBAC design than roles alone.

# A gap worth flagging (matches your "catch drift" instinct):
# Unlike get_role, which added a company_id scoping check specifically to prevent cross-company access, this function has no company scoping at all — only user_id. Is that a problem? It depends on whether user_id alone is enough to guarantee the caller is authorized to view this data — e.g., does the resolver calling this already confirm (via get_current_user_or_raise + a permission/ownership check) that the requesting admin belongs to the same company as the target user, before calling this selector? If not, this selector alone can't stop someone in Company A from passing another company's user_id and reading their permission overrides. Worth checking the resolver/service that calls this — the same kind of verification you were right to flag for get_role.

# 7. Advanced concepts

# A) select_related vs prefetch_related — the decision rule, stated plainly

# Relationship is "this object points to exactly one other object" (ForeignKey or OneToOneField, from this model's side) → select_related → one query, joined.
# Relationship is "this object can point to many others" (ManyToManyField, or the reverse side of a ForeignKey — "many roles point to this company") → prefetch_related → two-or-more queries, stitched in Python.
# Getting this backwards doesn't crash your code — Django will still technically run it — but you lose the performance benefit, or in some cases it's simply not supported for that relationship shape. Recognizing which kind of relationship you're looking at is the real skill here.

# B) Why a JOIN can't safely represent a "many" relationship as one row
# If select_related were used for something like roles-to-permissions (many-to-many), a SQL JOIN would produce one row per permission, meaning a role with 5 permissions would show up as 5 duplicate-ish rows, each differing only in which permission is attached — completely breaking "one row = one role." That's precisely why "many" relationships need the separate-query-and-stitch approach of prefetch_related instead.

# 8. Small example
# python
# class Permission:
#     def __init__(self, codename): self.codename = codename

# class Override:
#     def __init__(self, user_id, permission):
#         self.user_id = user_id
#         self.permission = permission   # like a ForeignKey — ONE permission per override

# overrides = [
#     Override("u1", Permission("orders.delete")),
#     Override("u1", Permission("staff.invite")),
#     Override("u2", Permission("orders.view")),
# ]

# def list_user_overrides(*, user_id):
#     return [o for o in overrides if o.user_id == user_id]

# for o in list_user_overrides(user_id="u1"):
#     print(o.permission.codename)   # orders.delete, staff.invite

# (In real Django, select_related is what makes o.permission.codename avoid an extra query per loop — this plain-Python version has no query cost to demonstrate, but the shape of "one override → one permission" is the same.)

# 9. What you should remember
# Pick select_related for "one" relationships (ForeignKey/OneToOneField from this model), and prefetch_related for "many" relationships (ManyToManyField, reverse FKs). The choice isn't stylistic — using the wrong one either fails or silently loses the performance benefit.
# A required, no-default parameter (user_id: str, no Optional) signals "there is no safe default — omitting this would leak data across boundaries." You've now seen this reasoning three times (list_roles, list_user_overrides) — it's a real, recurring design rule in multi-tenant code, not a one-off choice.
# The module a class is imported from doesn't have to match the class's own name. Trust the actual class name for behavior; the file path just tells you where it physically lives.
# A selector missing an ownership/tenancy scope isn't automatically a bug — but it does mean the responsibility for that check has moved to whatever calls it. Always check the caller before assuming a lookup is safe.
# When comparing two similar selectors, spot what changed and ask why — here, the meaningful change (many-to-many vs. one-to-one relationship) explains the different optimization method used; that comparison instinct is exactly how you build real intuition for a codebase instead of memorizing each function in isolation.