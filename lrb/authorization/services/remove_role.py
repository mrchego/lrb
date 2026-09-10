from django.db import transaction

from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def remove_role(*, user_id: str, role_id: str, company_id: str):
    deleted, _ = UserRole.objects.filter(
        user_id=user_id,
        role_id=role_id,
        role__company_id=company_id,
    ).delete()
    if not deleted:
        raise ApplicationError(
            message="User does not have this role assigned.",
            code=ErrorCode.BUSINESS_RULE,
        )

    invalidate_user_permissions_cache(user_id=user_id)
    return True

# Yes — this is a very good real-world example of the pattern.

# deleted, _ = UserRole.objects.filter(
#     user_id=user_id,
#     role_id=role_id,
#     role__company_id=company_id,
# ).delete()

# Let's read it from the inside out.

# 1. UserRole.objects

# This means:

# "Work with the UserRole model through Django's database manager."

# Usually objects is Django's default manager.

# 2. .filter(...)
# .filter(
#     user_id=user_id,
#     role_id=role_id,
#     role__company_id=company_id,
# )

# This means:

# "Find UserRole records that satisfy all three conditions."

# So you're looking for a record where:

# user_id              = this user
# role_id              = this role
# role's company_id    = this company

# The interesting part is:

# role__company_id=company_id

# The double underscore __ lets Django traverse a relationship.

# Conceptually:

# UserRole
#    ↓
# role
#    ↓
# company_id

# So Django is saying:

# "The role related to this UserRole must belong to this company."

# 3. .delete()

# After finding the matching records:

# UserRole.objects.filter(...).delete()

# Django deletes those records.

# Importantly, .delete() returns two values:

# (number_deleted, deletion_details)

# For example:

# (1, {"rbac.UserRole": 1})
# 4. deleted, _ =

# Now we get to your original question.

# deleted, _ = UserRole.objects.filter(...).delete()

# Django might return:

# (1, {"rbac.UserRole": 1})

# Python unpacks that:

# deleted → 1
# _       → {"rbac.UserRole": 1}

# The programmer wants the number of records deleted, so they keep:

# deleted

# and intentionally throw away:

# _

# So afterward:

# if deleted:
#     print("Role removed")

# would work because deleted contains the number of deleted records.

# The whole line in plain English
# deleted, _ = UserRole.objects.filter(
#     user_id=user_id,
#     role_id=role_id,
#     role__company_id=company_id,
# ).delete()

# means:

# "Find this user's assignment to this role within this company, delete the matching record(s), keep the number deleted, and ignore Django's deletion details."

# And notice the security/design aspect too: role__company_id=company_id prevents the query from simply looking for a role assignment by user_id and role_id without verifying that the role belongs to the expected company.

# Teaching: remove_role

# This one introduces a genuinely different way of deleting data — bulk queryset deletion instead of the "fetch one object, then .delete() on it" pattern you saw in delete_role. It also brings back the __ traversal syntax from list_roles, used here for a security purpose instead of a performance one. Let's go through it fully.

# 1. What is it?

# A service that removes a role assignment from a user — deleting the UserRole join row directly by filtering, without ever loading it into a full Python object first. Confirms it actually deleted something, and raises a clear error if there was nothing to remove.

# New pieces:

# UserRole.objects.filter(...).delete() — bulk delete on a queryset
# deleted, _ = ... — tuple unpacking, with _ as a throwaway name
# role__company_id=company_id — __ traversal used inside a .filter(), for a security check
# 2. How is it written?

# UserRole.objects.filter(user_id=user_id, role_id=role_id, role__company_id=company_id).delete()
# This is meaningfully different from every delete you've seen so far. delete_role did:

# python
# role = Role.objects.filter(...).first()   # fetch one object first
# role.delete()                              # then delete it

# This function skips the "fetch first" step entirely:

# python
# UserRole.objects.filter(...).delete()      # filter AND delete, in one call, no fetch

# Calling .delete() directly on a queryset (rather than on a single model instance) is called a bulk delete. Django translates this into a single SQL DELETE ... WHERE ... statement that matches and removes rows directly in the database — it never loads any UserRole object into Python memory at all. This is more efficient specifically because nothing here needs the actual row's data (its fields, its relationships) — the code only cares "does a matching row exist, and can it be removed," not anything about what's inside it. Compare this to delete_role, which did need the fetched role object afterward (to check role.user_roles.exists() before deleting) — that's exactly why delete_role couldn't skip the fetch step, but this function can.

# role__company_id=company_id — the __ traversal, used for security this time
# You first learned __ in list_roles's prefetch_related("user_roles__user"), where it meant "follow a relationship, then go one level deeper" for pre-loading data. Here it's the exact same syntax, but inside a .filter(...) call, meaning "follow a relationship, then filter on a field of the related object." Read it as: "starting from UserRole, follow its role field (a ForeignKey to Role), and check that related Role's company_id field." This lets one .filter() call reach through a relationship to check something on the other side of it, without needing a separate query.

# Why does this matter here? Because UserRole itself doesn't store company_id directly — only its related Role does. This is exactly the same "don't let one company touch another company's data" principle you learned in get_role, delete_role, and assign_role — just expressed by reaching through a relationship instead of filtering a field on the model being queried directly.

# deleted, _ = UserRole.objects.filter(...).delete()
# Two new things stacked together:

# What .delete() on a queryset actually returns. Unlike role.delete() (deleting a single already-loaded instance, which returns nothing useful), calling .delete() on a queryset returns a tuple: (total_number_of_objects_deleted, a_dictionary_breaking_that_count_down_by_model_type). The dictionary part exists because a bulk delete can cascade — deleting a UserRole might also cascade-delete other related rows depending on your model setup, so Django reports exactly how many of each type got removed, not just one flat number.
# Tuple unpacking with _. deleted, _ = some_tuple means: "this function returns two values; call the first one deleted, and I don't care about the second one, so I'll name it _ as a throwaway." _ is a Python convention (not a special keyword — it's just a valid, very short variable name) meaning "I'm intentionally ignoring this value." Any reader seeing _ instantly understands: "this position exists, but nothing later in the code uses it."

# if not deleted:
# deleted is an integer — how many rows got removed. 0 is falsy, any positive number is truthy. So if not deleted: means "if nothing was actually deleted" — i.e., the filter matched zero rows, meaning either the user never had this role, or (thanks to the role__company_id check) they had it but under a different company's scope, treated identically as "not assigned" for the same information-hiding reasons you learned in get_role.

# 3. Signature — broken into pieces
# python
# def remove_role(*, user_id: str, role_id: str, company_id: str):
# Piece	Meaning
# *,	keyword-only
# user_id: str	which user to remove the role from
# role_id: str	which role to remove
# company_id: str	security scope

# All three parameters are typed — matching clone_role's good habit, not create_role/update_role's gaps. Still no return type hint (should be -> bool), consistent with every write service you've read.

# 4. Body — line by line
# python
# deleted, _ = UserRole.objects.filter(
#     user_id=user_id,
#     role_id=role_id,
#     role__company_id=company_id,
# ).delete()

# Build a query matching exactly one specific user-role assignment, scoped to the right company via the relationship traversal, and delete whatever matches — all as one database operation. Unpack the result into deleted (count) and _ (ignored breakdown dict).

# python
# if not deleted:
#     raise ApplicationError(
#         message="User does not have this role assigned.",
#         code=ErrorCode.BUSINESS_RULE,
#     )

# If nothing matched (count is 0), raise a clear business-rule error.

# python
# invalidate_user_permissions_cache(user_id=user_id)
# return True

# Clear this user's cached effective permissions (exact mirror of assign_role's cache invalidation — makes sense, since removing a role changes effective permissions just as much as adding one does), and signal success.

# 5. Why?

# Why bulk-delete via .filter().delete() here, but fetch-then-.delete() in delete_role?
# This is the key comparison to internalize. Ask: does the code need the object's data for anything before deleting it?

# delete_role needed role.user_roles.exists() — a check that depends on the specific role object and its relationships — so it had no choice but to fetch it first.
# remove_role needs nothing from the UserRole row itself — it only needs to know "does an assignment matching these three criteria exist, and can it go away." Bulk delete answers that in one step, with one query, instead of two (fetch, then delete).

# This is a real, reusable decision rule: fetch-then-delete when you need the object for something else first (validation, related checks); bulk-delete when the filter criteria alone are the complete decision.

# Why is "not assigned" treated as a BusinessRuleViolationError-style error (via ErrorCode.BUSINESS_RULE) rather than, say, silently succeeding (return True even if nothing was deleted)?
# Because silently succeeding on a no-op would hide a real problem from the caller — if a frontend tries to remove a role assignment that doesn't exist (maybe due to a stale UI, or a double-click, or a bug elsewhere), telling the truth ("this wasn't actually assigned") is more honest and debuggable than pretending it worked. This mirrors the same philosophy you saw in create_role's unknown-codename check: don't quietly do less than what was asked; say so clearly.

# Why fold "role not assigned" and "role belongs to a different company" into the same single error, instead of distinguishing them?
# Same information-hiding principle from get_role: if the code distinguished "not assigned" from "assigned, but under a different company you can't touch," it would leak information about what exists in other companies' data. One flat "not assigned" message is the safe, correct answer regardless of which underlying reason applies.

# 6. Connections

# What comes in: user_id, role_id, company_id — the reverse operation of assign_role.
# What goes out: True, or ApplicationError if nothing matched.
# Where this fits: the exact undo operation for assign_role; together they form a matched create/delete pair on the UserRole join table, just like create_role/delete_role form a matched pair on Role itself. Both assign_role and remove_role invalidate the same per-user cache (invalidate_user_permissions_cache), confirming that cache tracks "this specific user's effective permissions," refreshed any time their role assignments change in either direction.

# 7. Advanced concepts

# A) Bulk .delete() skips Django's per-instance .delete() signals
# Worth knowing as a genuine trade-off, even though it's not visible in this file: Django models can have pre_delete/post_delete signals — code that runs automatically whenever instance.delete() is called (e.g., "when a UserRole is deleted, also log it to an audit table"). A bulk .filter().delete() call, like this one, does not trigger those per-instance signals — it deletes rows directly at the database level, bypassing that Python-level hook entirely. This is exactly why the trade-off matters: bulk delete is faster, but only safe to use when you're certain no such signal-based side effect is expected to fire. If your project relies on UserRole deletion signals anywhere for auditing, this function would silently skip them — worth being aware of as a real gotcha when choosing between the two deletion styles.

# B) _ as "I'm ignoring this" is a convention, not special syntax
# Nothing about _ is magic to Python — it behaves exactly like any other variable name. It's a convention, understood by essentially every Python developer, that signals "this value exists structurally (because the function returns a tuple), but I have no use for it." You'll see this constantly whenever unpacking a value you only partially care about.

# C) Reaching through a relationship inside .filter() versus inside prefetch_related
# Same __ syntax, genuinely different purpose depending on context:

# Inside .filter(role__company_id=...) — this narrows which rows match, becoming part of the SQL WHERE clause via a JOIN.
# Inside .prefetch_related("user_roles__user") (from list_roles) — this doesn't filter anything; it just tells Django which additional related data to pre-load for rows that already matched.
# Same double-underscore, opposite jobs — filtering versus loading — determined entirely by which method it's passed to.
# 8. Small example
# python
# assignments = [
#     {"user_id": "u1", "role_id": "r1", "company_id": "A"},
#     {"user_id": "u2", "role_id": "r2", "company_id": "B"},
# ]

# def remove_role(*, user_id, role_id, company_id):
#     before = len(assignments)
#     assignments[:] = [
#         a for a in assignments
#         if not (a["user_id"] == user_id and a["role_id"] == role_id and a["company_id"] == company_id)
#     ]
#     deleted = before - len(assignments)
#     if not deleted:
#         raise ValueError("User does not have this role assigned.")
#     return True

# remove_role(user_id="u1", role_id="r1", company_id="A")   # works, deleted=1
# remove_role(user_id="u2", role_id="r2", company_id="A")   # raises — wrong company
# 9. What you should remember
# .delete() called on a queryset (bulk delete) skips fetching the object entirely and skips per-instance signals — use it when the filter criteria alone fully decide what to remove, and you don't need the object's data or its delete-time side effects.
# .delete() on a queryset returns (total_count, breakdown_dict) — unpack it, and use _ for the part you don't need. _ is just a naming convention for "intentionally ignored," not special syntax.
# __ traversal works identically inside .filter() as it does inside prefetch_related/select_related — "follow this relationship, then reach this field" — but its purpose changes with context: filtering narrows results; prefetching only affects loading efficiency.
# Choosing between fetch-then-delete and bulk-delete comes down to one question: do you need anything from the object besides "does it exist"? If yes, fetch first (like delete_role). If no, bulk-delete directly (like this function).
# A count of zero from a bulk operation is a legitimate, checkable signal of "nothing matched" — use it the same way you'd use if not role: after a .first() lookup, to raise a clear, honest error rather than silently treating a no-op as success.