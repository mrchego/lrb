from django.db import transaction
from lrb.authorization.models.role import Role
from lrb.core.exceptions import ApplicationError, ErrorCode


@transaction.atomic
def clone_role(*, role_id: str, company_id: str, new_name: str):
    source = Role.objects.filter(pk=role_id, company_id=company_id).first()
    if not source:
        raise ApplicationError(message="Role not found", code=ErrorCode.ROLE_NOT_FOUND)

    new_name = new_name.strip()
    if len(new_name) < 2:
        raise ApplicationError(
            message="Role name must be at least 2 characters long.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    clone = Role.objects.create(company_id=company_id, name=new_name, is_default=False)
    clone.permissions.set(source.permissions.all())
    return clone


# Teaching: clone_role

# Almost everything here is fully familiar to you now — scoped lookup, not-found guard, name validation, @transaction.atomic. So this one is a great test of your own pattern-recognition: I'll walk it fully, but the real value is in what's different from create_role, since two things here quietly diverge from established conventions.

# 1. What is it?

# A service that duplicates an existing role — same permissions, but a new name — for the same company. It's built almost entirely by recombining pieces from get_role and create_role that you already know.

# New piece: company_id=company_id (as opposed to company=company).

# 2. How is it written?

# source = Role.objects.filter(pk=role_id, company_id=company_id).first()
# Identical shape to update_role/delete_role's lookup — nothing new here, you should recognize this instantly by now.

# new_name = new_name.strip() then length check
# Identical logic to create_role's name validation, just renamed to new_name.

# clone = Role.objects.create(company_id=company_id, name=new_name, is_default=False)
# This is the one genuinely new syntax detail. Compare it to create_role:

# python
# # create_role:
# Role.objects.create(company=company, name=name, is_default=is_default)
# # clone_role:
# Role.objects.create(company_id=company_id, name=new_name, is_default=False)

# create_role passes company=company — a real Company object (a ForeignKey field, when set directly by its plain name, expects an actual model instance). clone_role instead passes company_id=company_id — a plain string/ID value, using the field name with _id appended.

# This works because of a Django convention: for every ForeignKey field named company, Django automatically also creates a matching column attribute called company_id that holds just the raw ID — and you're allowed to assign to either one. Setting company=some_company_object requires Django to already have (or fetch) the full related object in memory. Setting company_id=some_id_string skips that entirely — you're just telling Django "put this raw ID directly into the foreign key column," without ever needing to load the actual Company row into Python. This is why clone_role can create the clone without ever fetching a Company object at all — it never needed one; it only ever had company_id (a plain string) to begin with, passed straight through from its own parameter.

# clone.permissions.set(source.permissions.all())
# source.permissions.all() — get every permission currently on the original role (a queryset, still lazy at this point). .set(...) — same many-to-many "replace with exactly this list" method you saw in create_role/update_role, called on the new clone. Passing a queryset directly into .set() (rather than a Python list) works fine — .set() will accept anything iterable and evaluate it as needed. The overall line means: "give the clone the exact same set of permissions the source role currently has."

# 3. Signature — broken into pieces
# python
# def clone_role(*, role_id: str, company_id: str, new_name: str):
# Piece	Meaning
# *,	keyword-only
# role_id: str	which role to copy from
# company_id: str	scope for lookup, and the company the clone belongs to
# new_name: str	the clone's name
# no ->	missing return type hint — same drift as every write service so far

# Worth noting positively: this signature actually has type hints on every parameter — unlike create_role and update_role, which had none at all. This is real, meaningful consistency with your project's stated convention, even though the return hint is still missing. Good to notice improvements, not just regressions, as you compare functions against each other.

# 4. Body — line by line
# python
# source = Role.objects.filter(pk=role_id, company_id=company_id).first()
# if not source:
#     raise ApplicationError(message="Role not found", code=ErrorCode.ROLE_NOT_FOUND)

# Fetch the role to copy, scoped to company; reject if missing/wrong company.

# python
# new_name = new_name.strip()
# if len(new_name) < 2:
#     raise ApplicationError(message="Role name must be at least 2 characters long.", code=ErrorCode.VALIDATION_ERROR)

# Normalize and validate the new name — same shape as create_role, but worth stopping on: see section 5, this is one of the two real inconsistencies in this file.

# python
# clone = Role.objects.create(company_id=company_id, name=new_name, is_default=False)
# clone.permissions.set(source.permissions.all())
# return clone

# Create a brand-new role (always is_default=False — a clone should never automatically become the default role, that's a deliberate, sensible hardcoded choice, not a missed parameter), copy over the source's permissions, and return the new role.

# 5. Why? — and two things worth flagging

# Why company_id=company_id instead of fetching a Company object first, like create_role does?
# This is actually a reasonable, efficient choice, not a mistake: this function never needs to do anything with the Company object itself (no reading its name, no validating anything about it) — it only ever needs to store its ID as a foreign key reference. Fetching the full Company row from the database just to immediately throw away everything except its ID would be a wasted query. Using company_id= directly avoids that unnecessary database hit entirely. This is a subtle but genuine performance-awareness difference worth recognizing — not every write needs the full related object, just its identity.

# Inconsistency worth flagging #1 — the error type for a validation failure
# Look closely: every previous validation failure in create_role and update_role used:

# python
# raise AppValidationError(message="...", field="name")

# This file instead uses:

# python
# raise ApplicationError(message="...", code=ErrorCode.VALIDATION_ERROR)

# Different exception class entirely (ApplicationError instead of the more specific AppValidationError), and a different way of describing what went wrong — code=ErrorCode.VALIDATION_ERROR (a generic code) instead of field="name" (which field, specifically, was invalid). If your frontend relies on field to highlight the exact input box that failed validation (a very common UI pattern for form errors), this inconsistency means a "name too short" error from clone_role wouldn't be able to point at the name field the way the same error from create_role does — the frontend would only know "something about validation failed," not what. This is exactly the kind of copy-paste drift that's easy to introduce when writing similar code in different files without checking siblings — a good one to have caught yourself, matching the instinct you've been building this whole conversation.

# Inconsistency worth flagging #2 — missing permission validation entirely
# clone_role doesn't accept a permission_codenames parameter at all — it always copies all of the source role's current permissions, with no option to customize them during cloning. That's not necessarily wrong (maybe "clone" is intentionally meant to be an exact copy, and customization happens via a follow-up update_role call) — but it's worth noticing as a design question rather than assuming it's complete: does the product actually want "clone with optional permission overrides in one step," or is "clone exact, then edit separately" the intended workflow? Not a bug, but a good question to ask when reading a function that seems to do "less" than a sibling might suggest it could.

# 6. Connections

# What comes in: role_id/company_id (identifying the source role) and new_name (for the clone).
# What goes out: the newly created Role (a clone), or ApplicationError for not-found/validation failure.
# Where this fits: a convenience operation likely triggered from an admin UI's "Duplicate Role" button — saves an admin from manually re-checking every permission checkbox when creating a role very similar to an existing one. Reuses the exact lookup pattern from get_role/update_role/delete_role, and the exact creation pattern from create_role, without needing to call either selector/service directly — it's built from the same underlying Django operations, just recombined for this specific use case.

# 7. Advanced concepts

# A) field_id= vs field= on a ForeignKey — when to use which
# Use field=some_object when you already have (or need to have, for other reasons) the full related object in memory. Use field_id=some_raw_id when you only need to establish the link, and fetching the full object would be pure waste. This choice can matter meaningfully for performance in write-heavy code — recognizing "do I actually need the object, or just its identity?" is a useful habit whenever you're about to write a ForeignKey assignment yourself.

# B) Passing a queryset directly into .set()
# clone.permissions.set(source.permissions.all()) — notice this doesn't wrap the result in list(...) first, unlike create_role/update_role, which did list(Permission.objects.filter(...)) before validating and using it. Here, there's no need to force evaluation early, because the queryset is used exactly once, immediately, with no intermediate validation step that needs to inspect it twice — .set() will just iterate it once itself. This is a good contrast to notice: list(...) was necessary earlier specifically because the result needed to be reused (once for the unknown-codename check, once for attaching) — not a universal requirement every time you touch a queryset.

# 8. Small example
# python
# class Role:
#     def __init__(self, name, permissions):
#         self.name = name
#         self.permissions = permissions

# def clone_role(source, new_name):
#     new_name = new_name.strip()
#     if len(new_name) < 2:
#         raise ValueError("Name too short")
#     return Role(name=new_name, permissions=list(source.permissions))

# manager = Role(name="Manager", permissions=["orders.view", "orders.edit"])
# manager_copy = clone_role(manager, "  Manager Copy  ")
# print(manager_copy.name, manager_copy.permissions)
# # "Manager Copy", ['orders.view', 'orders.edit']
# 9. What you should remember
# field_id=raw_value is a valid, sometimes more efficient alternative to field=full_object on a ForeignKey — use it when you only need to establish the link, not read or validate anything about the related object itself.
# Even functions with fully correct type hints can still drift in exception choice — having role_id: str, company_id: str, new_name: str typed correctly doesn't guarantee the error-handling matches its siblings; check both separately.
# A validation error should carry enough structured detail (like field=) for the frontend to act on it precisely — swapping AppValidationError(field=...) for a generic ApplicationError(code=...) silently loses that precision, even though both "work" in the sense of raising an error.
# When a function does noticeably less than a sibling with a similar name might suggest (here: no permission customization during clone), ask whether that's intentional design or a missing feature — don't assume either way without checking the broader workflow it's meant to support.
# Recognizing when NOT to force a queryset into a list (list(...)) is just as important as knowing when you should — only do it when you need to reuse or inspect the results more than once; a single-use queryset passed straight into something like .set() doesn't need it.
