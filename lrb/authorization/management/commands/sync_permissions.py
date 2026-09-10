from django.core.management.base import BaseCommand
from lrb.authorization.models.permission import Permission
from lrb.authorization.permissions import PERMISSION_REGISTRY


class Command(BaseCommand):
    def handle(self, *args, **options):
        codenames_in_code = {codename for codename, _, _ in PERMISSION_REGISTRY}

        for codename, label, category in PERMISSION_REGISTRY:
            Permission.objects.update_or_create(
                codename=codename,
                defaults={"label": label, "category": category},
            )

        stale = Permission.objects.exclude(codename__in=codenames_in_code)
        if stale.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"{stale.count()} permission(s) in DB no longer in code: "
                    f"{list(stale.values_list('codename', flat=True))}"
                )
            )
        self.stdout.write(self.style.SUCCESS("Permissions synced."))


# Teaching: The Permission Sync Management Command

# This is a completely different kind of file from everything else you've read — not a selector, not a service, but a Django management command: a script you run manually from the terminal (like python manage.py sync_permissions), rather than code triggered by a web request. New territory, so I'll build up the framework concepts from scratch before going through the logic.

# 1. What is it?

# A command that keeps your database's Permission table in sync with a hardcoded list of permissions defined in your Python code (PERMISSION_REGISTRY) — creating/updating rows to match the code, and warning about any leftover database rows that no longer correspond to anything in the code.

# New pieces:

# from django.core.management.base import BaseCommand
# class Command(BaseCommand): — a specific, required class name and inheritance
# def handle(self, *args, **options): — a specific, required method name
# PERMISSION_REGISTRY — a project-defined constant
# for codename, label, category in PERMISSION_REGISTRY: — unpacking 3 values at once
# self.stdout.write(...), self.style.WARNING(...), self.style.SUCCESS(...)
# .exclude(...), .count(), .values_list(..., flat=True)
# A subtle bug in the f-string itself
# 2. How is it written?

# class Command(BaseCommand):
# This is Django's required convention for management commands: Django's command-runner looks for a file at a specific location (<app>/management/commands/<command_name>.py) and expects it to contain a class literally named Command, inheriting from BaseCommand. BaseCommand is a class Django provides that already knows how to hook into python manage.py <command_name> — parse arguments, print output nicely, handle errors — your job is just to fill in what happens when it runs.

# (BaseCommand) after the class name is inheritance — you haven't seen this in any file so far in this conversation. It means "Command is a specialized version of BaseCommand; it automatically gets everything BaseCommand already knows how to do, and adds/overrides specific pieces." This is different from every other class you've read (UserMutation, which stood alone with no parent) — here, inheritance is why this class works as a management command at all; without extending BaseCommand, Django's manage.py wouldn't recognize it as a runnable command.

# def handle(self, *args, **options):
# Another required convention: Django's BaseCommand calls a method named exactly handle when the command runs — this is where your actual logic goes. *args and **options are new syntax:

# *args — collects any extra positional arguments into a tuple (again, unused here, but part of the required method signature BaseCommand expects).
# **options — collects any extra keyword arguments (like command-line flags, e.g. --dry-run) into a dictionary (also unused here, since this command doesn't define any custom flags, but again required as part of matching BaseCommand's expected method signature).

# Neither is used in this particular command's body, but they need to be present because Django's internal machinery always calls handle(*args, **options) — the method needs to accept whatever gets passed, even if this specific command ignores it.

# codenames_in_code = {codename for codename, _, _ in PERMISSION_REGISTRY}
# Read the right side first. PERMISSION_REGISTRY is presumably a list of tuples, each shaped like (codename, label, category). for codename, label, category in PERMISSION_REGISTRY: — but written here as for codename, _, _ in PERMISSION_REGISTRY: — is tuple unpacking inside a loop: each iteration, Python takes one 3-item tuple and assigns its three parts to three names in one line. Using _ (twice!) for the second and third positions means "I only care about the first item in each tuple (the codename), and I'm intentionally ignoring the other two here" — same throwaway convention you learned in remove_role's deleted, _ = ..., just applied twice in a row since there are two unwanted values.

# The whole line builds a set of every codename that currently exists in the code — used later to figure out what's stale.

# for codename, label, category in PERMISSION_REGISTRY:
# Same tuple-unpacking shape, but this time keeping all three parts, since the loop body needs label and category too.

# Permission.objects.update_or_create(codename=codename, defaults={"label": label, "category": category})
# Exactly the update_or_create method you learned in set_permission_override — find a Permission by codename (the lookup field); if found, update its label/category to match the code; if not found, create a new row with all three fields. This is the actual "sync" — for every permission defined in code, make sure a matching, up-to-date database row exists.

# stale = Permission.objects.exclude(codename__in=codenames_in_code)
# .exclude(...) is the logical opposite of .filter(...) — instead of "keep rows matching this condition," it means "keep rows that do NOT match this condition." Combined with __in (which you learned in create_role: "matches any value in this collection"), this line means: "give me every Permission row in the database whose codename is not found anywhere in the code's registry" — i.e., permissions that used to be defined in code (and got saved to the database at some point), but have since been removed from the code without being cleaned up from the database.

# if stale.exists():
# Same .exists() method you learned in delete_role — cheap yes/no check, no need to fetch actual rows just to know if there are any.

# self.stdout.write(self.style.WARNING(f"..."))
# Two BaseCommand-provided tools, working together:

# self.stdout — a safe, testable way to print output from a management command (rather than Python's plain print()) — BaseCommand wires this up so it works correctly whether you're running the command normally, piping its output somewhere, or running it inside an automated test.
# self.style.WARNING(...) — wraps the given text in terminal color-coding (yellow/warning-colored, typically), so when a human runs this command in a terminal, stale permissions visually stand out as a warning, distinct from self.style.SUCCESS(...) (green, used for the final "Permissions synced." message). These are purely cosmetic/readability tools — they don't change the underlying string's meaning, just how it displays in a terminal that supports color.

# f"{stale.count()} permission(s) in DB no longer in code: {list(stale.values_list("codename", flat=True))}"
# Two new pieces inside this f-string:

# .count() — a queryset method that asks the database "how many rows match?" and returns a plain integer, without ever loading the actual rows — more efficient than len(list(stale)) when you only need a number.
# .values_list("codename", flat=True) — instead of returning full Permission objects, this returns just the values of one specific field (codename), as a flat list of plain strings rather than a list of one-tuples. Wrapped in list(...) to force it into a real Python list for display (same "stop being lazy, give me real data now" reasoning you've seen throughout this conversation).
# 3. A real bug hiding in this exact line

# Look very closely at the f-string:

# python
# f"{stale.count()} permission(s) in DB no longer in code: "
# f"{list(stale.values_list("codename", flat=True))}"

# Notice: the outer string uses double quotes (f"..."), and inside the {...} expression, "codename" also uses double quotes. In Python versions before 3.12, this is a syntax error — you cannot nest the same quote character inside an f-string's {} expression without it being misread as ending the string early. Python would see f"...{list(stale.values_list(" and interpret the inner " as closing the f-string right there, leaving codename", flat=True))}" as leftover, broken code.

# (Python 3.12 introduced more flexible f-string parsing that does allow this — so whether this line actually crashes depends entirely on which Python version your project runs. Worth checking your project's Python version directly if you want to know whether this line works as-is or needs fixing.)

# The safe, portable fix — and the standard convention regardless of Python version — is to use a different quote character for the inner string than the outer one:

# python
# f"{list(stale.values_list('codename', flat=True))}"

# Using single quotes 'codename' inside a double-quoted f-string avoids the ambiguity entirely, and works correctly on every Python version. This is a good, simple rule to adopt in your own code: when writing an f-string, use a different quote style inside {} expressions than the one wrapping the whole string.

# 4. Body — full walkthrough
# python
# codenames_in_code = {codename for codename, _, _ in PERMISSION_REGISTRY}

# Snapshot every codename currently defined in code, as a set.

# python
# for codename, label, category in PERMISSION_REGISTRY:
#     Permission.objects.update_or_create(
#         codename=codename,
#         defaults={"label": label, "category": category},
#     )

# For every permission the code says should exist, make sure the database has a matching, up-to-date row — creating new ones, updating existing ones' label/category if they've changed in code.

# python
# stale = Permission.objects.exclude(codename__in=codenames_in_code)
# if stale.exists():
#     self.stdout.write(
#         self.style.WARNING(
#             f"{stale.count()} permission(s) in DB no longer in code: "
#             f"{list(stale.values_list("codename", flat=True))}"
#         )
#     )

# Find any database permissions that no longer correspond to anything in the current code, and print a colored warning listing them (with the quoting caveat above).

# python
# self.stdout.write(self.style.SUCCESS("Permissions synced."))

# Always print a final success message, regardless of whether stale entries were found.

# 5. Why?

# Why does this command exist at all — why not just define permissions directly as database rows from an admin panel?
# This reflects a deliberate architectural choice: PERMISSION_REGISTRY, living in your project's actual Python code, is the source of truth for what permissions exist — not the database. This makes sense for your RBAC design: permissions are described as "atomic, developer-defined capabilities" (from your project's conventions) — meaning developers, not admins, decide what permissions exist, by writing code, and that gets version-controlled, reviewed, and deployed like any other code change. The database is just a reflection of that code, kept in sync by running this command (probably as part of your deployment process). This is a common, solid pattern: code defines the schema of "what's possible"; the database just needs to catch up to match it.

# Why warn about stale permissions instead of automatically deleting them?
# Because deleting a Permission row could have serious, hard-to-reverse consequences — if roles or users still reference that permission somewhere (through the role-permission many-to-many table, or overrides), automatically deleting it could silently strip access from people, or fail due to foreign key constraints, or cascade-delete related data unexpectedly. Surfacing a warning and letting a human decide what to do (was this permission intentionally removed? should associated roles be cleaned up first?) is a much safer default than automating a potentially destructive cleanup.

# Why update_or_create here instead of, say, deleting everything and recreating it fresh each time?
# Because existing Permission rows are likely referenced by other data (roles that grant them, overrides that reference them) — deleting and recreating would break all of those foreign key relationships, or at minimum, needlessly cascade-delete related data. update_or_create preserves each permission's actual database identity (its primary key) across syncs, only touching the fields that might have changed (label, category) — a much safer, more surgical approach.

# 6. Connections

# What comes in: nothing from a request — this command runs standalone, driven by PERMISSION_REGISTRY, a constant defined elsewhere in your authorization app.
# What goes out: no return value — its "output" is entirely side effects: database rows updated/created, and text printed to the terminal.
# Where this fits: almost certainly run during deployment or local setup (python manage.py <command_name>) — the bridge between "permissions as code" (PERMISSION_REGISTRY) and "permissions as database rows" (what get_permission, list_permissions, create_role, etc. all actually query against). Every selector and service you've read this whole conversation assumes Permission rows already exist in the database — this command is what makes that assumption true in the first place.

# 7. Advanced concepts

# A) Management commands as a distinct architectural layer
# Everything you've read before this (selectors, services, GraphQL mutations) runs in response to a live request from a user. A management command runs outside that request/response cycle entirely — triggered manually or by a deployment script, with direct database access and no GraphQL/HTTP layer involved at all. It's a different kind of entry point into your codebase, worth recognizing as distinct from the resolver → service → selector flow you've been tracing throughout this whole conversation.

# B) "Code as source of truth, database as a synced reflection"
# This is a broader software design pattern worth naming: rather than manually managing reference data (like permission definitions) through an admin UI or database migrations by hand, you define it declaratively in code (PERMISSION_REGISTRY) and write a small, idempotent sync script to reconcile the database to match. Running this command repeatedly should always be safe — running it twice in a row with no code changes should have zero effect (another real-world example of the idempotency concept from clear_permission_override) — it's designed to be run over and over, as part of every deploy, without ever causing harm.

# C) f-string quote nesting is a genuinely common, easy-to-miss bug
# Worth remembering as a standalone lesson: any time you write an f-string and need a string literal inside the {} part, deliberately choose the opposite quote style from the one wrapping the whole f-string. It's a small, mechanical rule, but forgetting it produces a syntax error that can be confusing to debug if you're not specifically looking for a quote mismatch (and depending on your Python version, might not error at all — making it even easier to miss until it actually breaks in production on an older Python version).

# 8. Small example
# python
# PERMISSION_REGISTRY = [
#     ("orders.delete", "Delete Orders", "Orders"),
#     ("staff.invite", "Invite Staff", "Staff"),
# ]

# db_permissions = {"orders.delete": {}, "orders.archive": {}}  # simulated DB

# codenames_in_code = {codename for codename, _, _ in PERMISSION_REGISTRY}

# for codename, label, category in PERMISSION_REGISTRY:
#     db_permissions[codename] = {"label": label, "category": category}   # simulated update_or_create

# stale = [c for c in db_permissions if c not in codenames_in_code]
# if stale:
#     print(f"Stale: {stale}")   # note: single quotes not even needed here since no nesting
# print("Permissions synced.")
# # Stale: ['orders.archive']
# # Permissions synced.
# 9. What you should remember
# class Command(BaseCommand): with a handle(self, *args, **options): method is Django's required shape for a management command — inheriting from BaseCommand is what makes manage.py recognize and run it; the method name and signature are fixed conventions, not arbitrary choices.
# update_or_create is the right tool for "reconcile the database to match a known, external source of truth" — here, code-defined data syncing into the database — because it preserves existing rows' identity while updating only what's changed.
# .exclude(field__in=...) is the inverse of .filter(field__in=...) — "everything NOT matching" versus "everything matching" — useful specifically for finding orphaned/stale data that no longer has a counterpart elsewhere.
# Don't nest the same quote character inside an f-string's {} expression — always switch quote styles (double outside, single inside, or vice versa) to avoid a syntax error that may or may not surface depending on your Python version.
# A sync/reconciliation script should almost always warn about orphaned data rather than auto-deleting it — deletion can cascade or break references in ways that are hard to reverse; surfacing the problem to a human for a deliberate decision is the safer default.