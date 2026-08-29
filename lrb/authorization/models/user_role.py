from django.db import models
from lrb.core.models.base import BaseModel


class UserRole(BaseModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(
        "authorization.Role", on_delete=models.CASCADE, related_name="user_roles"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")
        ]


class UserPermissionOverride(BaseModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="permission_overrides"
    )
    permission = models.ForeignKey("authorization.Permission", on_delete=models.CASCADE)
    is_granted = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "permission"], name="unique_user_permission_override"
            )
        ]


# This file introduces relationships between models — how Django connects tables to each other. Both classes here are what's called "junction" or "link" tables, and together they implement the exact RBAC pattern your project notes describe: roles made of permissions, plus per-user exceptions.

# UserRole
# python
# class UserRole(BaseModel):
#     user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_roles")
#     role = models.ForeignKey("authorization.Role", on_delete=models.CASCADE, related_name="user_roles")

# What is it?
# models.ForeignKey(...) is a Django field type that creates a link to another table — it means "each row in UserRole points to exactly one row in another model." This is how Django represents a real-world relationship: "this user has this role."

# Breaking down user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_roles") piece by piece:

# "accounts.User" — the target model, written as a string, in the form "app_name.ModelName", instead of importing and writing the actual User class directly. This is a deliberate Django pattern called a lazy reference. Why use a string instead of from lrb.accounts.models import User? Because accounts and authorization might need to reference each other's models, and if both files tried to import each other directly at the top, Python would hit a circular import error (file A needs file B, which needs file A, which isn't finished loading yet — a chicken-and-egg problem). Writing the model as a string lets Django resolve the actual class later, after all app models have finished loading, sidestepping the circular dependency entirely.
# on_delete=models.CASCADE — this tells the database: "if the User this row points to gets deleted, automatically delete this UserRole row too." This is a required argument for every ForeignKey — Django forces you to explicitly decide what happens to a link when the thing it points to disappears (other options exist, like SET_NULL or PROTECT, but CASCADE is the natural choice here: a user-role link makes no sense once the user is gone, so it should vanish with them).
# related_name="user_roles" — this names the reverse relationship — the path backwards, from a User object to all its UserRole rows. Without related_name, Django would auto-generate something clunky like userrole_set. With related_name="user_roles", you can write some_user.user_roles.all() to get every role-link belonging to that user — clean and readable. Notice both ForeignKeys here (user and role) are named related_name="user_roles" — that's fine, because they point to different models (User and Role), so some_user.user_roles and some_role.user_roles don't collide with each other.

# Why does this table exist at all — why not just put a role field directly on User?
# Because a user can have multiple roles, and a role can be assigned to multiple users. That's a many-to-many relationship, and a single ForeignKey on User could only point to one role at a time. UserRole is a dedicated junction table: each row is one (user, role) pairing. This is the classic way to represent "many-to-many" in a relational database — instead of one table trying to hold a list inside a single cell (which relational databases can't do cleanly), you create a separate table where each row is one link.

# class Meta: constraints = [...]
# python
# class Meta:
#     constraints = [
#         models.UniqueConstraint(fields=["user", "role"],
#         name="unique_user_role")
#     ]

# What is it?
# Another Meta class (you learned last time: Django-recognized, configures model behavior, not a real column). This time it sets constraints — a list of extra rules enforced by the database itself.

# Breaking down models.UniqueConstraint(fields=["user", "role"], name="unique_user_role"):

# fields=["user", "role"] — a list of two field names. This is different from the single-field unique=True you saw on Permission.codename last time. A multi-field unique constraint means: "the combination of user and role must be unique," not either field alone. In plain English: the same user can have many different roles (many rows with that user), and the same role can be assigned to many different users (many rows with that role) — but that exact same pairing (this user + this role) can only exist once. This stops the database from accidentally storing the same role twice for the same person.
# name="unique_user_role" — every database constraint needs an internal name (used in error messages and migration files); this just labels it descriptively.

# Why enforce this in the database, instead of just checking in Python before saving?
# This connects to something important about reliability: Python-level checks can be skipped (a bug, a race condition where two requests run at nearly the same time, a script that bypasses your normal code path). A database constraint is the last line of defense — it's physically impossible to insert a duplicate row, no matter what code path tries to do it. This is the same spirit as your project's @transaction.atomic convention: relying on the database itself to guarantee correctness, not just trusting application code to behave.

# UserPermissionOverride
# python
# class UserPermissionOverride(BaseModel):
#     user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="permission_overrides")
#     permission = models.ForeignKey("authorization.Permission", on_delete=models.CASCADE)
#     is_granted = models.BooleanField(default=True)

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(fields=["user", "permission"], name="unique_user_permission_override")
#         ]

# What's new here, compared to UserRole?

# The permission field has no related_name. This is allowed — related_name is optional. When omitted, Django falls back to its default naming (permission.userpermissionoverride_set). The developer likely didn't bother naming this one because the reverse lookup ("give me all the overrides pointing at this permission") probably isn't something the app needs to do often, whereas user.permission_overrides (checking a user's overrides) clearly is — hence that one did get a clean name.
# is_granted = models.BooleanField(default=True) — a new field type: BooleanField stores True/False. default=True means if a row is created without explicitly setting is_granted, it defaults to True.

# Why does this model exist, given Permission and UserRole already exist?
# This is the key design idea, and it directly matches your project note: "require_owner() for superuser-only actions; require_permission(codename) for delegable staff permissions." Normally, a user's permissions come from their roles (via UserRole → Role → its permissions). But real systems often need individual exceptions — "this one staff member should NOT have a permission their role normally grants" or "this one staff member SHOULD have an extra permission their role doesn't normally include," without creating a whole new custom role just for one person.

# is_granted is what makes this an override rather than just an addition:

# A row with is_granted=True means: grant this specific permission to this specific user, regardless of their roles.
# A row with is_granted=False means: revoke this specific permission from this specific user, even if one of their roles would normally grant it.

# So your actual "does this user have permission X?" check (likely inside require_permission()) probably follows logic like: check role-based permissions first, then check if there's an override row for this exact user+permission — and if so, let the override have the final say.

# Advanced concept: why default=True specifically?
# Think about why someone would create an override row in the first place. The far more common real-world case is "grant this one extra thing" (add an exception) rather than "revoke this one specific thing" (which is rarer and more deliberate). Defaulting to True means the simpler, more common case (an admin says "give this permission to this user") requires the least typing/config — they can create the override without explicitly setting is_granted at all, and it'll do the expected thing.

# Connections — the full permission-resolution chain

# Putting all four files together, here's how a permission check likely flows, from your require_permission() helper down to the database:

# require_permission("some_codename") (in a service function) needs to know: does this user have this permission?
# It looks at UserRole rows for this user → gets their Role(s).
# Each Role has its own permissions attached (a Role↔Permission many-to-many, likely a similar junction table you haven't shown me yet).
# It also checks UserPermissionOverride for this exact user+permission combination — if found, is_granted overrides whatever the roles said.
# If none of that grants it, the check fails, and the mutation is rejected — this is the backend enforcement that GraphQL mutations like AdminUpdateUserInput rely on before doing anything.
# What I should remember
# ForeignKey("app.Model", ...) as a string avoids circular imports between apps that need to reference each other — a common pattern once your project has multiple interlinked apps.
# on_delete is mandatory and meaningful — it's Django forcing you to decide what happens to dependent rows when their "parent" is deleted; CASCADE means "delete along with it."
# A junction table (UserRole) is the standard way to model many-to-many relationships — one row per pairing, instead of trying to cram a list into a single field.
# UniqueConstraint(fields=[...]) on multiple fields enforces uniqueness of the combination, not each field individually — and doing this at the database level is more reliable than checking in application code.
# An "override" pattern (is_granted boolean) lets you handle exceptions to a general rule (role-based permissions) without redesigning the whole system — a reusable idea any time you need "usually X, but sometimes make a specific exception."
