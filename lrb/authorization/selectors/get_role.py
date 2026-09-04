from typing import Optional
from lrb.authorization.models.role import Role

def get_role(*, role_id: str, company_id: Optional[str] = None) -> Optional[Role]:
    qs = Role.objects.filter(pk=role_id)
    if company_id:
        qs = qs.filter(company_id=company_id)
    return qs.first()

# Teaching: get_role

# Good news: this function is basically get_permission and list_permissions combined — a single-object lookup (like get_permission) that also has an optional filter (like list_permissions). Since you already know both of those patterns, I'll focus mainly on what's new: pk=, and the security reasoning behind the optional company_id filter — which is the most important part of this one.

# 1. What is it?

# A selector that fetches one Role by its ID — but optionally, also requires that role to belong to a specific company. Returns the Role object, or None if no match.

# New piece: pk=role_id inside .filter(...).

# 2. How is it written?

# Role.objects.filter(pk=role_id)
# pk stands for primary key. Every Django model automatically has a primary key field (usually an auto-generated id, though your project might use UUIDs). pk is a special, built-in alias Django provides that always means "whatever the primary key field is, no matter what it's actually named." Instead of writing Role.objects.filter(id=role_id) (which assumes the primary key column is literally called id), pk=role_id works correctly even if your Role model uses a UUID field with a different name as its primary key. It's a portability convention — use pk whenever you mean "the identity field," not a specific column name.

# Everything else in this function is a direct combination of patterns you already know:

# *, role_id: str, company_id: Optional[str] = None — keyword-only, one required parameter (role_id, no default → caller must supply it), one optional parameter (company_id, defaults to None) — same shape as list_permissions's category.
# if company_id: qs = qs.filter(...) — same conditional-narrowing pattern as list_permissions.
# qs.first() — same "get one or None" pattern as get_permission.
# -> Optional[Role] — correctly typed this time (unlike list_permissions, which was missing its hint).
# 3. Signature — broken into pieces
# python
# def get_role(*, role_id: str, company_id: Optional[str] = None) -> Optional[Role]:
# Piece	Meaning
# *,	both parameters below must be passed by keyword
# role_id: str	required — no default value, so the caller must always supply this
# ,	separates the two parameters
# company_id: Optional[str] = None	optional — string or None, defaults to None if not given
# -> Optional[Role]	returns a Role, or None if nothing matched

# Notice the difference between role_id and company_id: both have type hints, but only company_id has = None. That's what makes one required and one optional — the presence of a default value, not the type hint, is what Python actually checks.

# 4. Body — line by line
# python
# qs = Role.objects.filter(pk=role_id)

# Start with: "the one role whose primary key matches role_id" (still lazy — not yet a real database hit, and technically this could match more than one row if role_id weren't unique, but primary keys are guaranteed unique by definition, so in practice this narrows to at most one row).

# python
# if company_id:
#     qs = qs.filter(company_id=company_id)

# If a company_id was given, narrow the query further: the role must belong to that specific company too, not just have the right ID.

# python
# return qs.first()

# Execute the query, return the single matching Role — or None if either the ID didn't exist at all, or (importantly) it existed but belonged to a different company than the one specified.

# 5. Why? (this is the important part)

# Why bother filtering by company_id at all, if role_id alone should already uniquely identify one row?

# This is a security/tenancy pattern, not a data-correctness one. Here's the real-world danger it defends against:

# Your RBAC project is multi-company — each company has its own roles. Imagine Company A has a role with ID 42. If a resolver just did Role.objects.filter(pk=role_id).first() using an ID the frontend sent, then a malicious or buggy request from a user in Company B could pass role_id="42" and successfully fetch (or worse, if this pattern were copied into an update/delete service, modify) a role that belongs to a completely different company. The ID alone doesn't prove ownership — it just proves "a role with this ID exists somewhere in the whole database."

# By making the caller also pass their own company_id (almost certainly current.company_id, from your get_current_user_or_raise gatekeeper) and filtering on it, the query becomes: "give me this role, but only if it also belongs to the company I say I'm operating as." If someone tries to reach across company boundaries, the .filter(company_id=...) step silently excludes that row, and .first() returns None — treated the exact same way as "role doesn't exist," which is exactly the right response (you don't want to leak whether a role with that ID exists in another company; a flat "not found" is the safe, uninformative answer).

# Why make company_id optional instead of always required, if it's this important for security?
# This is worth thinking about carefully rather than just accepting. A plausible reason: this selector might be reused in two different contexts —

# Normal company-scoped calls (the common, security-sensitive case) — pass company_id=current.company_id always.
# A superuser/owner-level admin context that's allowed to look up any role across any company (e.g., a platform-wide admin tool) — deliberately omit company_id.

# That said, this is exactly the kind of function where you should be cautious as you read real callers: if any regular (non-owner) resolver calls get_role(role_id=...) without also passing company_id, that's a real security bug — it would let any authenticated user fetch any role from any company just by guessing/incrementing IDs. When you read the code that calls this function next, check: does every non-privileged call site pass company_id=current.company_id? That's worth verifying, not assuming.

# 6. Connections

# What comes in: role_id (which role to look up — likely from GraphQL input) and optionally company_id (the scope to restrict the search to — likely current.company_id from the caller's session).
# What goes out: the matching Role, or None — treated identically whether the role truly doesn't exist, or exists but belongs to someone else's company.
# Where this fits: almost certainly called from a resolver or service that assigns roles to staff, or edits a role's permissions — anywhere your project needs to "get the role the request is talking about, but only if it's really this company's role." This is the read-side counterpart to whatever service later does update_role or assign_role_to_user — those write operations would likely call get_role first to confirm the role exists and belongs to the right company before touching it.

# 7. Advanced concepts

# A) pk vs the actual field name
# Using pk= instead of id= is a small but genuinely important Django idiom: it keeps your code correct even if the underlying primary key field is renamed or changed to a UUID later — pk always means "whatever the current primary key is," so this line never needs to change even if the model's ID strategy does.

# B) Treating "wrong company" the same as "doesn't exist" — an information-security principle
# This is a general pattern worth remembering beyond Django: when access should be scoped (multi-tenant systems, per-user data, etc.), the safe response for "exists but you're not allowed to see it" and "doesn't exist" should usually be identical from the outside. If your API responded differently — e.g., "403 Forbidden" for "wrong company" vs. "404 Not Found" for "no such role" — an attacker could use that difference to figure out which role IDs are real, even ones they can't access. By folding "wrong company" into the same None/not-found outcome as "doesn't exist," this function avoids leaking that information. This is a subtle but real security-design decision baked into a two-line queryset chain.

# C) Combining .filter() calls vs one .filter() with two conditions
# This function could have been written as one call:

# python
# Role.objects.filter(pk=role_id, company_id=company_id).first()

# ...but only if company_id were always provided. Because it's optional, splitting into two conditional .filter() steps is required — you can't put company_id=None into a single .filter() call and expect it to mean "skip this condition"; Django would instead try to match rows where company_id is actually NULL in the database, which is a completely different (and wrong) query. This is a subtle trap — good to have surfaced it explicitly.

# 8. Small example
# python
# roles = [
#     {"id": "1", "company_id": "A"},
#     {"id": "2", "company_id": "B"},
# ]

# def get_role(*, role_id, company_id=None):
#     matches = [r for r in roles if r["id"] == role_id]
#     if company_id:
#         matches = [r for r in matches if r["company_id"] == company_id]
#     return matches[0] if matches else None

# print(get_role(role_id="1", company_id="A"))   # found — same company
# print(get_role(role_id="1", company_id="B"))   # None — wrong company, treated as "not found"
# print(get_role(role_id="1"))                    # found — no scoping requested
# 9. What you should remember
# pk= is the portable way to filter by a model's primary key — use it instead of hardcoding id=, so your code survives changes to the underlying key field.
# A required parameter has just a type hint; an optional one adds = default. The default's presence, not the type hint, is what Python checks to decide "must this be passed?"
# Scoping a lookup by an ownership field (like company_id) is a core multi-tenant security pattern — it prevents IDs from being usable across boundaries they shouldn't cross. Whenever you see an ID-based lookup in a multi-tenant system, ask: "is this scoped to the right owner, or could any ID work regardless of who's asking?"
# Treat "forbidden" and "doesn't exist" identically in the response, when the alternative would leak information — None here means "no accessible match," full stop, not "I found it but you can't have it."
# When a selector accepts an optional scoping parameter, check every call site — an optional security filter is only as safe as the discipline of every caller that's supposed to pass it. This is exactly the kind of thing to verify, not assume, when reading the resolvers that call get_role.