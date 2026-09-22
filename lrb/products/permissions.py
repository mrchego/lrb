PERMISSION_REGISTRY = [
    # (codename, label, category)
    ("products.view_product", "Can view products", "products"),
    ("products.add_product", "Can create products", "products"),
    ("products.change_product", "Can edit products", "products"),
    ("products.delete_product", "Can delete products", "products"),
    ("products.activate_product", "Can activate products", "products"),
    ("products.deactivate_product", "Can deactivate products", "products"),
    ("products.bulk_activate_products", "Can bulk activate products", "products"),
    ("products.bulk_deactivate_products", "Can bulk deactivate products", "products"),
    ("products.bulk_delete_product", "Can bulk delete products", "products"),
]


# 1. Purpose

# This file defines PERMISSION_REGISTRY — a plain Python list holding every permission your app knows about for the products feature. This is the concrete, code-level expression of something you already have written down in your own project notes: "Permissions are atomic, developer-defined capabilities; roles are admin-defined collections of permissions — role names are never hardcoded." This file is exactly where that principle lives — a single, central, developer-maintained source of truth for "what actions can even exist," which admins then combine into roles later (in the database, not in code).

# No functions, no classes — just data. That's worth sitting with for a second: not every important file in a real project does something active. Some files exist purely to declare "here is a fixed list of things the rest of the system can refer to."

# 2. What is it? — every piece explained
# python
# PERMISSION_REGISTRY = [
#     ...
# ]
# PERMISSION_REGISTRY — a variable name in ALL_CAPS_WITH_UNDERSCORES. This isn't required by Python syntax — Python would run identically if it were named permission_registry — but it's a very strong, widely-followed convention: ALL_CAPS signals "this is a constant — a value that's set once, here, and never reassigned anywhere else in the codebase." The moment you see a name like this anywhere in Python, you should read it as "treat this as fixed configuration data, not something to mutate."
# = [...] — assigns a list literal to that name. [ and ] are the syntax for building a list: an ordered collection of items, written comma-separated inside square brackets.
# python
#     # (codename, label, category)
# # starts a comment — everything after it on that line is ignored entirely by Python; it exists purely for humans reading the file. This particular comment is doing real work: it's documenting the shape of every entry below it, telling you exactly what each position in the upcoming tuples means, before you even look at one.
# python
#     ("products.view_product", "Can view products", "products"),
# (...) here builds a tuple — similar to a list, but conventionally used (as here) for a small, fixed-size group of related values that always travel together, rather than a growable collection of similar items. Each tuple has exactly three items, matching the three-part shape the comment above promised: (codename, label, category).
# "products.view_product" — the codename: a unique, machine-readable identifier for this specific permission. Notice the format: <app>.<action>_<model> — this isn't arbitrary; it mirrors Django's own built-in permission-naming convention (Django auto-generates permissions like add_product, change_product, delete_product, view_product for every model). This project's version prefixes the app name (products.) explicitly, likely so codenames stay globally unique across your whole project (orders.view_product could exist as a totally different permission from products.view_product, if that ever made sense).
# "Can view products" — the label: a human-readable description, meant for an admin UI where someone assigns permissions to roles and needs to read plain English, not a codename.
# "products" — the category: a grouping tag, presumably used to cluster related permissions together in that same admin UI (so all products.* permissions show up under one "Products" section, rather than one long flat list mixed with orders.* and staff.* permissions).
# The trailing comma after each tuple (and after the closing )) is a small Python convention: even the last item in a multi-line list is often given a trailing comma, because it means adding a new entry later only requires adding a new line — you never have to edit the previous line to add a comma to it. Small detail, but it's why real-world lists like this are usually formatted one item per line with trailing commas throughout.
# 3. Body — reading the data structure as a whole

# There's no "body" in the sense of executable steps here — the whole file is the data. But it's worth reading its shape: a list of four tuples, each with the identical (codename, label, category) structure. This uniformity is itself meaningful — every reader (human or code) can rely on "position 0 is always the codename" without needing to check each entry individually.

# 4. Why this approach
# One central list instead of scattering permission strings across the codebase — directly enforces your project's stated rule of never hardcoding meaningful strings loosely. Any code needing to check "products.delete_product" can import it from here (or, more robustly, from a constant derived from this list) instead of retyping the literal string somewhere else, where a typo could silently create a permission that doesn't match anything real.
# Tuples of primitive data, not a class or Django model, for something that's still just "developer-defined capabilities" — this registry is meant to be read by a startup/migration process that syncs these entries into the database (likely into an authorization app's Permission model, matching your project's app list). The plain-Python-list form makes it trivial for a developer to add a new permission with a one-line diff in version control — no migration file to write by hand, no admin UI clicking required, just add a tuple here and let a sync process handle turning it into a real database row.
# Separating codename (for code) from label (for humans) mirrors the exact same reasoning you saw in Purpose.EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification" back in the very first file today — a stable, code-safe identifier paired with a separate, freely-editable human-facing string. Renaming the label later (say, to "View product listings") never breaks any code checking the codename.
# 5. Connections
# This is almost certainly consumed by a management command or a data-migration, run at deploy time, that loops over PERMISSION_REGISTRY and does something like Permission.objects.get_or_create(codename=codename, defaults={"label": label, "category": category}) for each entry — syncing this file's contents into the actual authorization app's database table.
# Directly connects to your project's require_permission(codename) convention — somewhere in your authorization app, a function checks "does this user's role include a permission with this exact codename?" The codenames defined here ("products.view_product", etc.) are exactly the strings that function would be called with: require_permission("products.delete_product").
# Roles, defined elsewhere (admin-created, in the database), are built by picking a subset of these registry entries — this file defines the complete universe of possible permissions; it deliberately says nothing about which roles get which ones.
# You'd expect sibling files — orders/permissions.py, staff/permissions.py, company/permissions.py — each following this identical shape for their own app, probably all combined together (imported and concatenated) into one master list somewhere central, for the sync process to consume in one pass.
# 6. Advanced concepts

# Why permissions being "atomic, developer-defined capabilities" (per your own project notes) matters architecturally: the alternative — letting admins type arbitrary permission strings through a UI — sounds more flexible, but it's actually a foot-gun: an admin could create a role with a permission codename that doesn't correspond to any actual require_permission(...) check anywhere in the code, giving a false sense of restriction (or worse, silently granting nothing, since no code path ever checks that exact string). By making the registry developer-defined and code-reviewed, every permission that can ever exist is guaranteed to correspond to a real, working check somewhere in the actual application logic — admins can only ever combine real capabilities into roles, never invent fictitious ones.

# 7. Small example
# python
# PERMISSION_REGISTRY = [
#     # (codename, label, category)
#     ("orders.view_order", "Can view orders", "orders"),
#     ("orders.cancel_order", "Can cancel orders", "orders"),
# ]

# # somewhere else in the codebase:
# require_permission("orders.cancel_order")   # checks against a role's assigned permissions
# 8. What to remember
# ALL_CAPS names signal "constant, set once, never reassigned" — a convention, not a Python rule, but one worth respecting the moment you see it.
# A comment above a list of tuples documenting the tuple's shape (# (a, b, c)) is a lightweight, informal alternative to defining a real class — appropriate for simple, fixed, rarely-changing structured data like this.
# Separate a stable machine identifier (codename) from a human-facing label whenever code needs to reference something by name and a UI needs to display it — this is the same shape as TextChoices, just expressed as plain tuples instead of a Django-specific class.
# Not all important files contain logic — some are pure declared data, and reading them well means understanding what consumes this data elsewhere, not tracing execution steps that don't exist in the file itself.
# A central registry is what makes a "no hardcoded strings" rule actually enforceable in practice — the rule only holds if there's exactly one place permissions get defined, and everywhere else refers back to it rather than reinventing the string.
