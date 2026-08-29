from django.core.cache import cache

USER_PERMISSIONS_CACHE_TTL = 300


def user_permissions_cache_key(*, user_id: str) -> str:
    return f"user_perm: {user_id}"


def invalidate_user_permissions_cache(*, user_id: str) -> None:
    cache.delete(user_permissions_cache_key(user_id=user_id))


def invalidate_role_permissions_cache(*, role) -> None:
    user_ids = list(role.user_roles.values_list("user_id", flat=True))
    if user_ids:
        cache.delete_many([user_permissions_cache_key(user_id=uid) for uid in user_ids])

def get_user_permission_codenames(*, user) -> set[str]:
    from lrb.authorization.models.user_role import UserPermissionOverride, UserRole

    cache_key = user_permissions_cache_key(user_id=user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    role_perms = set(UserRole.objects.filter(user=user).values_list("role__permissions__codename", flat=True))
    role_perms.discard(None)

    overrides = UserPermissionOverride.objects.filter(user=user).select_related("permission")
    for o in overrides:
        if o.is_granted:
            role_perms.add(o.permission.codename)
        else:
            role_perms.discard(o.permission.codename)

    cache.set(cache_key, role_perms, timeout=USER_PERMISSIONS_CACHE_TTL)
    return role_perms


# This file is the service layer for permission checks — the actual require_permission() logic almost certainly calls into get_user_permission_codenames() here. It introduces caching, a big performance concept, plus a few Django ORM tricks worth slowing down for.

# Imports and the constant
# python
# from django.core.cache import cache
# USER_PERMISSIONS_CACHE_TTL = 300
# from django.core.cache import cache — imports Django's built-in caching system. cache here is a ready-to-use object (not a class you instantiate yourself) with methods like .get(), .set(), .delete() — think of it as a fast, temporary key-value storage (often backed by Redis or memory) that sits in front of your database, so repeated lookups don't have to hit the database every time.
# USER_PERMISSIONS_CACHE_TTL = 300 — a module-level constant (written in ALL_CAPS by convention, to signal "this doesn't change while the program runs"). TTL stands for "Time To Live" — how many seconds a cached value stays valid before it's automatically thrown away. 300 seconds = 5 minutes.

# Why cache this at all?
# Think about what get_user_permission_codenames() does (you'll see below): it queries the database, possibly joining across UserRole → Role → Permission, every single time any code checks "does this user have permission X?" If your app checks permissions on nearly every request (very likely, given require_permission() is probably called constantly), that's a lot of repeated, identical database work for data that rarely changes. Caching means: compute it once, remember the answer for 5 minutes, and reuse it — much faster for something checked constantly but changed rarely.

# user_permissions_cache_key
# python
# def user_permissions_cache_key(*, user_id: str) -> str:
#     return f"user_perm: {user_id}"

# Signature, piece by piece

# def user_permissions_cache_key(...) — a plain function (no self, so it's not a method on a class — it doesn't belong to any particular object).
# *, — this is a syntax you'll see in every function in this file, and it matches your project's convention of keyword-only arguments. The * by itself (not attached to a name) is a marker in a function's parameter list meaning: "everything listed after this must be passed by name, never by position." Without it, someone could call user_permissions_cache_key("abc123") and it would work by luck of ordering; with the *, they're forced to write user_permissions_cache_key(user_id="abc123"). This matters a lot once functions have several parameters — it prevents bugs where two arguments of the same type get silently swapped by position.
# user_id: str — parameter name and its expected type (a string).
# -> str — return type hint: this function gives back a string.

# Body
# return f"user_perm: {user_id}" — builds and returns a string like "user_perm: 42". This is the actual cache key — the "label" used to store and retrieve this user's permission data inside the cache.

# Why a separate tiny function just for building a string?
# This is an important pattern: never construct a cache key by hand in more than one place. If three different functions each typed out f"user_perm: {user_id}" themselves, and later you needed to change the key format (say, to f"user_perm_v2: {user_id}" after a data structure change), you'd have to remember to update it everywhere — miss one spot, and you'd get stale or mismatched cache reads. By centralizing key-building in one function, every other function calls this one, so the format only needs to be right in a single place.

# invalidate_user_permissions_cache
# python
# def invalidate_user_permissions_cache(*, user_id: str) -> None:
#     cache.delete(user_permissions_cache_key(user_id=user_id))

# Signature
# -> None — a return type hint meaning "this function doesn't give back a meaningful value." It performs an action (deleting something) rather than computing an answer.

# Body
# cache.delete(...) removes whatever is stored under that key. Notice it calls user_permissions_cache_key(user_id=user_id) to build the key, rather than writing the string again — exactly the reuse benefit just described.

# Why does this function need to exist?
# This is the other half of caching, and it's the harder half. If a user's role changes (say, an admin grants them a new permission), but the cache still holds their old permission list for up to 5 more minutes, the user would be wrongly denied access to something they should now have. Cache invalidation means: whenever the underlying data changes, immediately throw away the stale cached copy, so the next read is forced to recompute a fresh answer from the database. This function is what a mutation (like "assign role to user," from your earlier UserRole model) should call right after making that change.

# invalidate_role_permissions_cache
# python
# def invalidate_role_permissions_cache(*, role) -> None:
#     user_ids = list(role.user_roles.values_list("user_id", flat=True))
#     if user_ids:
#         cache.delete_many([user_permissions_cache_key(user_id=uid) for uid in user_ids])

# Signature
# role has no type hint here (unlike everywhere else in this file) — this is a minor inconsistency in the code (it's probably a Role model instance), but Python doesn't require every parameter to be typed; it just means slightly less documentation for this one argument.

# Body, line by line

# role.user_roles — remember related_name="user_roles" from the UserRole model? This is that reverse relationship in action: starting from one Role object, .user_roles gives you every UserRole row linking to it (i.e., every user who has this role).
# .values_list("user_id", flat=True) — a new Django ORM method. Normally, querying gives you back full model objects (e.g., whole UserRole instances, with every field loaded). values_list("user_id", ...) says "I don't want full objects — just pull out this one column's values." flat=True further says "and don't wrap each value in a tuple — give me a flat list of plain values" (without flat=True, you'd get awkward single-item tuples like [(1,), (2,), (3,)]; with it, you get [1, 2, 3]). This is a performance optimization: fetching only the one column you actually need is faster and lighter than loading entire rows.
# list(...) — wraps the result. Django querysets are lazy — role.user_roles.values_list(...) doesn't actually hit the database the moment it's written; it builds up a description of the query, and only runs it when you actually use the result (like converting it to a list, or looping over it). Wrapping it in list(...) here forces it to execute immediately and store the results as a real Python list, so you can check its length and reuse it below without re-querying.
# if user_ids: — an empty list is "falsy" in Python (treated as False in an if), so this simply means "only bother doing the next step if there's at least one user with this role."
# cache.delete_many([...]) — deletes multiple cache keys in one call, more efficient than calling .delete() in a loop. The [...] inside is a list comprehension: [user_permissions_cache_key(user_id=uid) for uid in user_ids] reads as "build a new list by running user_permissions_cache_key(user_id=uid) for every uid in user_ids." It's a compact way of writing what would otherwise be a multi-line for loop that builds up a list.

# Why does this function exist, separately from the one above?
# Think about what happens when an admin edits a role itself — say, adding a new permission to the "Manager" role. That single change affects every user who has that role, potentially dozens of people, all at once. invalidate_user_permissions_cache only clears one user's cache; this function is for the case where the change happened at the role level and needs to ripple out to everyone holding that role.

# get_user_permission_codenames — the main function
# python
# def get_user_permission_codenames(*, user) -> set[str]:
#     from lrb.authorization.models.user_role import UserPermissionOverride, UserRole

#     cache_key = user_permissions_cache_key(user_id=user.id)
#     cached = cache.get(cache_key)
#     if cached is not None:
#         return cached
#     ...

# Signature
# -> set[str] — the return type hint here is set[str], meaning "a Python set (an unordered collection with no duplicates) containing strings." This is different from List[str] you've seen before — a set is the right choice here because permission checks care about membership ("is 'can_edit_orders' in this collection?"), not order or duplicates, and sets are much faster than lists for that kind of "is X in here?" check.

# The local import — from lrb.authorization.models.user_role import UserPermissionOverride, UserRole

# Notice this import is written inside the function body, not at the top of the file with the others. This is called a local import, and it's a deliberate technique (not a mistake) for one specific reason: avoiding circular imports. If this services.py-style file (in the authorization app) imported UserRole/UserPermissionOverride at the top level, and those model files (or something they depend on) ever imported something from this service file, Python would hit the same chicken-and-egg problem you learned about with ForeignKey string references. Putting the import inside the function delays it until the function is actually called — by then, every module has finished loading, so there's no ordering conflict.

# Body

# cache_key = user_permissions_cache_key(user_id=user.id) — build the cache key for this specific user, reusing your key-builder function again.
# cached = cache.get(cache_key) — try to fetch a cached value. If nothing's stored (or it expired), Django's cache returns None.
# if cached is not None: return cached — the cache hit path. If we already have an answer, return it immediately and skip everything below — no database work at all. This is not None check (rather than just if cached:) matters here: if the cached value happened to be an empty set (a user with zero permissions), a plain if cached: would treat that empty set as falsy and incorrectly fall through to recompute — is not None correctly distinguishes "nothing cached" from "cached, and the answer is an empty set."
# python
#     role_perms = set(UserRole.objects.filter(user=user).values_list("role__permissions__codename", flat=True))
#     role_perms.discard(None)
# UserRole.objects.filter(user=user) — get every UserRole row for this user (their role assignments).
# .values_list("role__permissions__codename", flat=True) — this is the same values_list trick as before, but with a new detail: "role__permissions__codename" uses Django's double-underscore (__) traversal syntax, which lets one query "walk across" relationships without writing separate queries for each step. Reading it left to right: from UserRole, go to its role (the linked Role), then that role's permissions (the ManyToManyField you saw in the Role model), then each permission's codename. One database query, following three hops of relationships, directly extracting the final string you actually want.
# set(...) — wraps the whole result in a set, automatically removing any duplicate codenames (e.g., if a user has two roles that both include the same permission, it only appears once).
# role_perms.discard(None) — if a user has a role with no permissions attached (remember blank=True on Role.permissions), that role__permissions__codename traversal produces a None for that row instead of skipping it. .discard(None) removes a None from the set if it's present — .discard() is used instead of .remove() specifically because .discard() does nothing (no error) if the value isn't there, whereas .remove() would crash if there's no None to remove. This is a small but important detail: the developer anticipated an edge case (empty roles) and handled it defensively.
# python
#     overrides = UserPermissionOverride.objects.filter(user=user).select_related("permission")
#     for o in overrides:
#         if o.is_granted:
#             role_perms.add(o.permission.codename)
#         else:
#             role_perms.discard(o.permission.codename)
# .filter(user=user) — get every override row for this user.
# .select_related("permission") — another performance-focused ORM method, and an important one to understand deeply. Without it, the loop below (o.permission.codename) would trigger a separate database query every single time you access o.permission for each override row — known as the "N+1 query problem" (1 query to get the overrides, then N more queries, one per override, to fetch each one's related permission). select_related("permission") tells Django to fetch the related Permission rows upfront, in the same original query (via a SQL JOIN), so accessing o.permission.codename later doesn't cost anything extra — it's already loaded in memory.
# for o in overrides: — loop through each override row.
# if o.is_granted: role_perms.add(...) — if this override grants the permission, add its codename to the set (even if it was already there from a role — sets don't care about duplicates, .add() is safe either way).
# else: role_perms.discard(...) — if the override revokes it (is_granted=False), remove that codename from the set — even if a role had granted it. This is exactly the "override wins" logic you predicted from reading the UserPermissionOverride model earlier.
# python
#     cache.set(cache_key, role_perms, timeout=USER_PERMISSIONS_CACHE_TTL)
#     return role_perms
# cache.set(cache_key, role_perms, timeout=USER_PERMISSIONS_CACHE_TTL) — store the freshly computed set in the cache under this user's key, set to expire after USER_PERMISSIONS_CACHE_TTL (300) seconds.
# return role_perms — hand back the final, correct set of permission codenames.
# Why this whole function is written this way (design discussion)

# This function is a great example of the "cache-aside" pattern: check the cache first; on a miss, compute the real answer from the source of truth (the database), store it in the cache for next time, then return it. The invalidation functions above exist because this pattern has exactly one weakness — a cache and a database can disagree if you forget to clear the cache when the underlying data changes. That's why invalidate_user_permissions_cache and invalidate_role_permissions_cache exist as first-class functions: whoever writes the "assign role" or "edit role permissions" service function is expected to call the matching invalidator right after saving, inside the same @transaction.atomic block, so the cache and database never drift apart for long.

# Connections

# This is very likely what sits underneath your project's require_permission(codename) helper — something like:

# python
# def require_permission(user, codename):
#     if codename not in get_user_permission_codenames(user=user):
#         raise PermissionDenied(...)

# And your UserRole/Role/Permission/UserPermissionOverride models from earlier files are exactly what this function reads from. Any mutation that creates/deletes a UserRole, or edits a Role's permissions, or creates a UserPermissionOverride, should call the matching invalidate_* function here — otherwise a permission change won't take effect for up to 5 minutes.

# What I should remember
# *, before parameters forces keyword-only arguments — every function in this file uses it, matching your project's convention; it prevents accidental positional-argument mix-ups.
# Cache-aside pattern: check cache → miss → compute from DB → store in cache → return. Every cache read needs a matching invalidation path, or you risk serving stale data.
# values_list(..., flat=True) and select_related(...) are ORM performance tools — the first avoids loading whole objects when you only need one column; the second avoids the "N+1 queries" trap by fetching related data in the same query.
# Django's __ (double underscore) syntax lets one query traverse multiple relationships (role__permissions__codename) — read it left to right as "go to this related model's this field."
# Local imports (inside a function, not at the top of the file) are a legitimate way to break circular import problems — recognize this pattern rather than assuming it's a mistake.