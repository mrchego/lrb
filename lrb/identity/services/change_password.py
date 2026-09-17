
from django.db import transaction
from django.utils import timezone

from lrb.core.exceptions import AppValidationError
from lrb.core.validators.password import validate_password_strength
from django.core.exceptions import ValidationError

def _set_new_password(*, user, new_password):
    try:
        validate_password_strength(password=new_password)
    except ValidationError as e:
        raise AppValidationError(message=" ".join(e.messages), field="new_password")

    user.set_password(new_password)
    user.last_password_change = timezone.now()
    user.failed_login_attempts = 0
    user.locked_until = None
    user.password_reset_required = False
    user.save(update_fields=["password", "last_password_change", "failed_login_attempts", "locked_until", "password_reset_required"])

@transaction.atomic
def change_password(*, user, current_password, new_password):
    if not user.check_password(current_password):
        raise AppValidationError(message="Current password is incorrect.", field="current_password")
    _set_new_password(user=user, new_password=new_password)

@transaction.atomic
def set_password_unchecked(*, user, new_password):
    _set_new_password(user=user, new_password=new_password)


# Imports
# python
# from django.db import transaction
# from django.utils import timezone

# from lrb.core.exceptions import AppValidationError
# from lrb.core.validators.password import validate_password_strength
# from django.core.exceptions import ValidationError

# What is it?

# from X import Y — Python's way of pulling a specific name (Y) out of a module (X) so you can use it directly, without writing the full path every time.
# transaction — a tool from Django for grouping several database writes into one "all or nothing" unit.
# timezone — Django's helper for getting the current date/time in a way that respects time zones (safer than Python's plain datetime.now()).
# AppValidationError — a custom error class this project built (lrb.core.exceptions), used to represent "the user did something invalid" in a way the rest of the app understands.
# validate_password_strength — a custom function this project built to check if a password is strong enough.
# ValidationError — Django's built-in error class for validation failures. Notice this is different from AppValidationError above — one is Django's, one is the project's own.

# Why?
# The project separates "Django's generic validation error" from "our app's validation error." This is a common pattern: wrap third-party/framework exceptions into your own exception type, so the rest of your code only has to know about one kind of error (AppValidationError), not every library's own error type.

# Function 1: _set_new_password
# python
# def _set_new_password(*, user, new_password):

# Signature, piece by piece:

# def — keyword that starts a function definition.
# _set_new_password — the function's name. The leading underscore _ is a Python convention (not a hard rule) meaning "private" — this function is meant to be used only inside this file, not imported elsewhere. It's a signal to other developers: "don't call this directly from outside."
# (*, user, new_password) — the parameters.
# * alone (not *args) is a special marker. It doesn't collect anything — it just says "everything after me must be passed by keyword, not by position."
# user and new_password — the two required keyword-only parameters.

# Why *?
# Without it, someone could call _set_new_password(some_user, "hunter2") and it would work — but it's easy to mix up which argument is which if the function grows more parameters later. Forcing keyword-only calls (_set_new_password(user=some_user, new_password="hunter2")) makes every call self-documenting and prevents order-mistake bugs. This is a very common pattern in Django codebases that follow the HackSoft styleguide (which your lrb project uses).

# Small example:

# python
# def greet(*, name):
#     print(f"Hello {name}")

# greet(name="Francis")   # works
# greet("Francis")        # TypeError! positional args not allowed
# Body, line by line
# python
#     try:
#         validate_password_strength(password=new_password)
#     except ValidationError as e:
#         raise AppValidationError(message=e.message, field="new_password")
# try / except — Python's error-handling block. Python runs the try block; if an error of the matching type happens, it jumps to except instead of crashing the program.
# validate_password_strength(password=new_password) — calls the imported function. If the password is too weak, this function raises Django's ValidationError.
# except ValidationError as e: — catches that specific error type and stores it in a variable named e (short for "exception" — just a name, could be anything).
# raise AppValidationError(message=e.message, field="new_password") — this is the "translation" step: Python catches Django's generic error and re-raises it as the project's own error type, carrying over the message (e.message) and telling the caller which field caused the problem ("new_password").

# Why? This keeps a clean boundary: nothing outside this function ever needs to know Django's ValidationError exists. Every error that escapes this module is an AppValidationError, which probably has a consistent shape (message + field) that the GraphQL layer or API layer knows how to turn into a user-facing error response.

# python
#     user.set_password(new_password=new_password)
# user.set_password(...) — calls a method on the user object. This is Django's built-in User model method that hashes the password (never stores it as plain text) and sets it on the object in memory. Note: this doesn't hit the database yet — it just changes the Python object.
# . — the "dot" is how you access an attribute or method that belongs to an object. user.set_password means "look inside the user object for something named set_password."
# python
#     user.last_password_change = timezone.now()
#     user.failed_login_attempts = 0
#     user.locked_until = None
#     user.password_reset_required = False
# Each line sets an attribute on user directly using = (assignment). These are all still just changes to the in-memory Python object — nothing is saved to the database yet.
# timezone.now() — calls the imported timezone module's now function to get the current timestamp.
# None — Python's special "nothing here" value. Setting locked_until = None means "this account is no longer locked until any specific time."
# 0 and False — plain literal values resetting counters/flags.

# Why reset these fields together?
# This function isn't just "change the password" — it's "change the password and clean up security state that should no longer apply." If someone was locked out (failed_login_attempts, locked_until) or forced to reset their password (password_reset_required), a successful password change should clear all of that. Bundling this logic here means every caller gets this cleanup for free, instead of every caller having to remember to do it.

# python
#     user.save(update_fields=["password", "last_password_change", "failed_login_attempts", "locked_until", "password_reset_required"])
# user.save(...) — this is the line that actually writes to the database. Everything before this was just changing the Python object in memory.
# update_fields=[...] — a keyword argument telling Django: "only update these specific columns in the database, not the whole row."
# [...] — a list literal. Square brackets [] create a list; the strings inside, separated by commas, are the field names.

# Why update_fields?
# Without it, .save() would rewrite every column of the row, even ones nothing touched. That's slower and riskier — if another part of the app changed a different field on this same row a moment ago (a race condition), a full save could silently overwrite that change. Naming the exact fields is safer and faster, and also documents exactly what this function changes — you can read the list and know precisely what side effects this function has, without reading the whole body.

# Function 2: change_password
# python
# @transaction.atomic
# def change_password(*, user, current_password, new_password):

# What is @transaction.atomic?

# @ — this is a decorator. A decorator is a function that wraps another function to add extra behavior around it, without changing the original function's code. Think of it like a plastic wrap you put around a gift — the gift (the function) is unchanged inside, but the wrap changes how it behaves from the outside.
# transaction.atomic — Django's decorator that makes everything inside the function happen as one database transaction: either all the database writes succeed, or none of them do. If any exception is raised partway through, Django automatically rolls back (undoes) every database change made so far in that function.

# Why here?
# change_password calls _set_new_password, which does a .save(). If something went wrong after that save but before the function finished (unlikely here, but imagine more steps were added later — like sending a notification, logging an audit event, etc.), you wouldn't want a half-finished password change sitting in the database. @transaction.atomic guarantees it's all-or-nothing.

# Body
# python
#     if not user.check_password(current_password=current_password):
#         raise AppValidationError(message="Current password is incorrect.", field="current_password")
#     _set_new_password(user=user, new_password=new_password)
# user.check_password(current_password=current_password) — Django's built-in method that checks whether the given plain-text password matches the hashed password stored for this user. Returns True or False.
# not — Python's boolean operator that flips True to False and vice versa. So if not user.check_password(...) reads as "if the password does not match."
# raise AppValidationError(...) — if the current password is wrong, stop immediately and throw an error, using the same AppValidationError pattern as before, so the error shape is consistent across the whole file.
# _set_new_password(user=user, new_password=new_password) — if the check passed, delegate to the helper function you just read above, reusing all its logic (validate strength, hash, reset security fields, save).

# Why split this into two functions?
# change_password is for the normal case: a user who knows their current password wants to change it, so you must verify the current password first. But there's another case — see below — where you don't want that check. Rather than duplicating the "set the new password" logic in both places, it's pulled out into _set_new_password once, and each public function adds its own rule on top.

# Function 3: set_password_unchecked
# python
# @transaction.atomic
# def set_password_unchecked(*, user, new_password):
#     _set_new_password(user=user, new_password=new_password)

# This is the shortest function, and its whole job is to skip the current-password check. It calls _set_new_password directly.

# Why would you ever skip the check?
# Think about real situations:

# Password reset via email link — the user forgot their password entirely, so they can't provide the current one. An admin, or the app itself (after verifying an email token), needs to set a new password without knowing the old one.
# Admin resetting a user's password — an administrator forcing a reset doesn't know (and shouldn't need) the user's current password.

# The function name is very honest about the risk: _unchecked tells any developer reading the codebase "be careful — this skips a normal safety check." Whoever calls this function is responsible for having already verified the user's identity through some other means (like an email token).

# Connections — how these fit into the bigger picture
# Inputs: a user object (a Django model instance, probably lrb's custom User model), plus password strings.
# Outputs: nothing returned (None implicitly) — these are service functions that perform an action and either succeed silently or raise an exception.
# Upstream callers: based on the RBAC/service pattern you've been learning (selectors read, services write), these functions live in lrb/accounts/services/. Something above them — probably a GraphQL mutation resolver — calls change_password(...) or set_password_unchecked(...), catches AppValidationError if it's raised, and turns it into a GraphQL error response the frontend can display.
# Downstream dependencies: validate_password_strength (a validator function elsewhere in lrb.core), and Django's own User model methods (set_password, check_password, save).

# This is the same "selectors read / services write, raise typed errors" pattern you've already been learning — this file is a service module for one specific domain: password management.

# Advanced concepts, explained simply

# 1. Private helper function pattern (_set_new_password)
# The underscore prefix plus splitting shared logic into a helper is a way of applying the DRY principle ("Don't Repeat Yourself"). Two public functions (change_password, set_password_unchecked) need the exact same "actually change the password and reset security fields" logic, but each has a different rule about when that's allowed to happen. The shared part becomes one private function; the differing part (the current-password check) stays in the public functions.

# 2. Exception translation / boundary
# Catching one exception type and raising a different, app-specific one at a "boundary" (here, the boundary between Django's validators and this app's error system) means the rest of the codebase never needs to import or handle Django's internal exception types. This makes the app's error handling consistent everywhere else (e.g., in the GraphQL layer).

# 3. Atomicity / transactions
# A database transaction groups multiple writes into one unit. @transaction.atomic is Django's decorator form of "start a transaction, and if anything inside raises an exception, undo everything and don't leave partial data behind." This matters even more as functions grow more steps over time — it's a safety net against bugs causing half-saved, inconsistent data.

# 4. In-memory changes vs. database writes
# Every line like user.last_password_change = timezone.now() only changes the Python object sitting in memory. Nothing touches the database until .save() is called. This distinction — "changing an object" vs. "persisting an object" — is fundamental to how Django (and most ORMs) work.

# Small example tying it together
# python
# # Imagine a simplified version, no Django, just to see the shape:

# def _apply_new_password(*, account, new_password):
#     account.password = new_password
#     account.attempts = 0

# def change_password(*, account, current_password, new_password):
#     if account.password != current_password:
#         raise ValueError("wrong current password")
#     _apply_new_password(account=account, new_password=new_password)

# def admin_reset_password(*, account, new_password):
#     _apply_new_password(account=account, new_password=new_password)  # no check!

# Same shape: one private helper, two public entry points with different rules.

# What you should remember
# Keyword-only args (*,) force every caller to name their arguments — this prevents mix-up bugs and is common in service-layer functions.
# A leading underscore (_name) signals "internal use only" — it's a convention for humans, not something Python enforces.
# Setting attributes vs. .save() — changing obj.field = value only updates memory; you must explicitly call .save() (often with update_fields=[...]) to write to the database.
# @transaction.atomic wraps a function so all its database writes succeed together or none do — reach for this whenever a function does more than one related write.
# Translate low-level exceptions into your own app's exception type at the boundary where they first appear, so the rest of the codebase only deals with one consistent error shape.
# Write a message…




# Claude is AI and can make mistakes. Please double-check responses.