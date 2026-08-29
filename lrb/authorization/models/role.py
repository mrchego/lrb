from django.db import models
from lrb.authorization.models.permission import Permission
from lrb.core.models.base import BaseModel


class Role(BaseModel):
    company = models.ForeignKey(
        "company.Company", on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField(max_length=100)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Pre-selected for newly invited staff if no role is chosen.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="unique_role_name_per_company"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


# This file brings in Role, the piece that ties Permission and UserRole together into a working RBAC system. It also has a real bug in it — I'll point that out where it happens, since it's exactly the kind of thing worth catching when reading code.

# Imports
# python
# from django.db import models
# from lrb.authorization.models.permission import Permission
# from lrb.core.models.base import BaseModel

# Notice something different from last time: Permission is imported directly as a real class (from ... import Permission), not referenced as a lazy string like "authorization.Permission" was in the UserPermissionOverride file. Why the difference? Because Role and Permission live in the same app (authorization) — there's no cross-app circular import risk here, so a normal direct import is safe and preferred (it's also nicer for tools like autocomplete and type-checkers, since they can "see" the real class). You'll see below that company.Company — a genuinely different app — still uses the string-reference pattern, for the reason you already learned.

# Fields
# python
# company = models.ForeignKey(
#     "company.Company", on_delete=models.CASCADE, related_name="roles"
# )
# name = models.CharField(max_length=100)
# permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
# is_default = models.BooleanField(
#     default=False,
#     help_text="Pre-selected for newly invited staff if no role is chosen.",
# )

# company — a ForeignKey, exactly like user/role in UserRole from your last file: one Role belongs to exactly one Company, but a Company can have many Roles (via related_name="roles", so some_company.roles.all() works). This tells you something important about the whole system: roles are scoped per-company, not global. Two different companies can each have their own role called "Manager" with completely different permissions — the system supports multi-tenant RBAC, not one shared set of roles for everyone.

# name = models.CharField(max_length=100) — nothing new; the human-readable role name (e.g. "Manager", "Cashier").

# permissions = models.ManyToManyField(Permission, related_name="roles", blank=True) — this is the key new concept. You already learned that UserRole is a hand-built junction table for the user↔role many-to-many. ManyToManyField is Django's built-in shortcut for exactly that pattern — instead of writing your own junction table class, Django creates one automatically, invisibly, behind the scenes.

# Breaking it down:

# Permission — the target model (imported directly, as noted above), meaning "each Role can be linked to many Permissions."
# related_name="roles" — same idea as before: lets you go backwards, some_permission.roles.all(), to see every role that includes this permission.
# blank=True — you saw this on Permission.category too (form-level: not required to fill in). Here it means a role is allowed to exist with zero permissions attached (a brand-new empty role before an admin configures it), rather than being forced to pick at least one permission at creation time.

# Why did the developer use ManyToManyField here, but hand-build a separate UserRole model for the user↔role link instead of also using ManyToManyField(Role) on User?
# This is worth sitting with, because it's a real design decision. The answer: UserRole needs to become its own explicit model because it might need extra data of its own later (e.g., "when was this role assigned," "who assigned it") — you already saw it inherits from BaseModel, which likely gives it created_at/updated_at. A plain ManyToManyField can support extra fields too (via a through= model), but explicitly building UserRole as its own class from the start is simpler and clearer. For Role↔Permission, though, there's no need for that extra data — a permission is either part of a role or it isn't, nothing more to say about the pairing — so the simple, automatic ManyToManyField is the right tool, with less code to maintain.

# is_default = models.BooleanField(default=False, help_text="...")

# default=False — same pattern you already know (BooleanField, default value).
# help_text="..." — a new field option. This is a string shown as guidance text in Django's auto-generated admin forms (and picked up by some form libraries) — it doesn't affect the database at all, it's purely there to explain the field's purpose to whoever is filling it out (e.g., an admin building roles in the Django admin panel). Notice the field is written across multiple lines with the arguments each on their own line — this is just a formatting choice for readability once a field call gets long (Python doesn't care about the line breaks here, since everything is still inside the (...) parentheses).

# Combined with its help_text, is_default answers a real product question: "when a new staff member is invited but nobody explicitly assigns them a role, which role should they get automatically?" One role per company can be flagged is_default=True to answer that.

# class Meta: — constraints and ordering together
# python
# class Meta:
#     constraints = [
#         models.UniqueConstraint(
#             fields=["company", "name"], name="unique_role_name_per_company"
#         )
#     ]
#     ordering = ["name"]

# You've now seen both constraints and ordering separately — here they appear together in one Meta, which is completely normal; Meta can hold as many configuration options as you need, each as its own line.

# UniqueConstraint(fields=["company", "name"], ...) — same multi-field pattern as UserRole. Here it means: within one company, role names must be unique (no two "Manager" roles for the same company) — but, since company is part of the combination, "Manager" can still exist independently at many different companies. This directly enforces the multi-tenant design you spotted above.

# ordering = ["name"] — sort roles alphabetically by name by default, which makes sense for a UI listing roles to pick from.

# The bug: __str__ is in the wrong place
# python
#     class Meta:
#         constraints = [...]
#         ordering = ["name"]

#         def __str__(self):
#             return f"{self.name} ({self.company.name})"

# Look closely at the indentation: def __str__(self): is indented inside class Meta:, not inside class Role:. In Python, indentation is not just style — it's what determines which class a piece of code actually belongs to. As written, this defines a method on the inner Meta class, which Django never looks at or calls — Meta is only inspected for its plain attributes (constraints, ordering, etc.), never for methods like __str__. The result: this __str__ method is dead code. It will never run, and Role objects will still print using Django's default, unhelpful <Role object (3)> form in the admin, shell, and logs.

# The fix is to shift __str__ one level left, so it's a sibling of class Meta:, not a child of it:

# python
# class Role(BaseModel):
#     company = models.ForeignKey(...)
#     name = models.CharField(max_length=100)
#     permissions = models.ManyToManyField(...)
#     is_default = models.BooleanField(...)

#     class Meta:
#         constraints = [...]
#         ordering = ["name"]

#     def __str__(self):
#         return f"{self.name} ({self.company.name})"

# On the f"{self.name} ({self.company.name})" syntax itself (once it's actually placed correctly): this is an f-string — a string literal prefixed with f, where anything inside {} gets evaluated as real Python and inserted into the text. self.company.name reads the linked Company object's name field. This would display something like "Manager (Acme Corp)" — useful precisely because role names aren't globally unique (as you just learned from the constraint), so showing the company alongside the name avoids confusion when an admin is looking at roles from multiple companies in one list.

# Connections

# This completes the picture from your last few files:

# Permission (atomic capability) ← ManyToManyField ← Role (bundle of permissions, scoped to a Company) ← UserRole (which users have which roles) ← optionally overridden per-user by UserPermissionOverride.
# Your require_permission(codename) helper almost certainly walks this exact chain: user → their roles (via UserRole) → each role's permissions (via this ManyToManyField) → check if codename is in that combined set → then check UserPermissionOverride for a final say.
# What I should remember
# ManyToManyField is Django's built-in shortcut for a many-to-many relationship — use it when the link itself needs no extra data; hand-build a junction model (like UserRole) when the link needs its own fields (timestamps, extra metadata).
# Import directly within the same app; use a string reference across apps — you can now see both patterns side by side in one file and know exactly why each was chosen.
# help_text is documentation for admin/forms only — it has zero effect on the database. Don't confuse it with validation.
# Indentation determines class membership in Python — always check what a method is actually nested inside, especially when a class Meta: sits right above it; a method meant for the outer class can silently end up trapped inside Meta and never run.
# Multi-tenant uniqueness is expressed by including the "tenant" field (company) inside a multi-field constraint — ["company", "name"] unique, rather than just name unique, is what allows the same name to exist safely across different companies.
