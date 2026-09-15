from django.db import models
from django.utils import timezone

from lrb.core.models.base import BaseModel


class VerificationCode(BaseModel):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification"
        PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="verification_codes"
    )
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    code = models.CharField(max_length=10)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "used_at"]),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def __str__(self):
        return f"{self.purpose} code for {self.user.email}"


# 1. Purpose

# This file defines a Django model — a Python class that represents a table in your database. VerificationCode stores one-time codes used for two things in your lrb project: verifying a user's email, and resetting a forgotten password.

# Each row in the resulting database table will answer: which user, why (purpose), what code was sent, when does it expire, has it been used yet.

# Without this class, you'd have no structured way to store, expire, or check OTP codes — you'd be inventing ad-hoc dictionaries or raw SQL every time you needed one. A model gives you a table, validation, and a Python API (VerificationCode.objects.create(...), code.is_expired, etc.) for free.

# ⚠️ Before we go further — there's a real bug in this file. I'll flag it where it appears, but I want you to know it's there so you read the imports critically, not just accept them.

# 2. Imports — explained like you've never programmed
# python
# from tkinter import CASCADE
# from X import Y means: go into module X, find the name Y defined there, and make it available in this file as Y.
# tkinter is Python's built-in GUI (graphical user interface) toolkit — the library for building desktop windows, buttons, menus. It has nothing to do with Django or databases.
# tkinter.CASCADE exists, but it's just the string "cascade", used to describe menu-tearoff styling in GUI menus.

# This is a mistake, almost certainly caused by an editor's autocomplete picking the wrong CASCADE from a dropdown of suggestions (Django's is called the same thing). It should be:

# python
# from django.db.models import CASCADE

# Why this matters: further down, the code does on_delete=CASCADE. Django's on_delete parameter requires a callable (a function) — django.db.models.CASCADE is a function. tkinter.CASCADE is just the text "cascade". Django checks this when the model class is built (at import time, not just at migration time) and will raise:

# TypeError: on_delete must be callable.

# This means the app won't even start — Django crashes the moment it tries to load this model. This is the single most important thing to catch in this file. I'll note it again in "Common Mistakes" below, but wanted it right up front since it changes how the rest of the file behaves.

# python
# from django.db import models
# django.db is Django's database sub-package. models is the module inside it holding everything you need to define tables: Model, CharField, DateTimeField, ForeignKey, etc.
# Convention: import the whole models module (not individual pieces) so every usage is prefixed models.X — this makes it instantly clear in the code below that CharField, DateTimeField, etc. are Django's, not something custom.
# python
# from django.utils import timezone
# Django's helper module for working with dates/times in a timezone-safe way. timezone.now() returns the current time as a timezone-aware datetime, which is the correct way to compare times in Django (plain Python datetime.now() is not timezone-aware and can silently cause bugs when comparing to database timestamps).
# python
# from lrb.core.models.base import BaseModel
# This is your own project code, not a third-party library. lrb is your project's Python package name (matches what your memory says the project is called). BaseModel is presumably a shared parent class living in core that every model in the project inherits from — likely giving you common fields like id, created_at, updated_at automatically (notice the code below uses created_at in Meta.ordering without defining it anywhere — it must come from BaseModel).

# Why import it this way? Because in a real project, every model needs the same boilerplate fields (timestamps, maybe soft-delete flags). Instead of repeating that in every model file, you define it once in BaseModel and every model inherits it. This is the DRY principle: Don't Repeat Yourself.

# 3. Signature — breaking apart the class definitions
# python
# class VerificationCode(BaseModel):
# class — the keyword that starts a class definition. A class is a blueprint: it doesn't do anything by itself, but every time Django (or you) creates a VerificationCode(), it's building one object that follows this blueprint.
# VerificationCode — the name you're giving this blueprint. By Django convention, this name doubles as the database table name (Django will make a table called something_verificationcode).
# (BaseModel) — this is inheritance. It means "VerificationCode is a BaseModel, plus whatever extra stuff I define below." Every field, method, and behavior on BaseModel is automatically available here without rewriting it.
# : — Python syntax meaning "the following indented block is the body of this class." Every line indented under class VerificationCode(BaseModel): belongs to this class.
# python
#     class Purpose(models.TextChoices):
#         EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification"
#         PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"

# This is a nested class — a class defined inside another class. Let's break it down:

# models.TextChoices is a special Django base class for building an enum (a fixed, named set of allowed string values) that's meant to be stored in a CharField.
# Each line like EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification" defines one choice. The right side is a tuple (two values separated by a comma) — ("EMAIL_VERIFICATION", "Email Verification").
# First value: "EMAIL_VERIFICATION" — the actual value stored in the database.
# Second value: "Email Verification" — the human-readable label shown in Django admin dropdowns, forms, etc.
# EMAIL_VERIFICATION (the name on the left, no quotes) becomes an attribute you can reference in code as Purpose.EMAIL_VERIFICATION, without ever typing the raw string yourself.

# Why nest it inside the model? Because Purpose only makes sense in the context of VerificationCode — nobody else needs an "email verification vs password reset" enum. Nesting keeps related code physically close and avoids polluting the module's top-level namespace. This mirrors your project's rule that permission/role names are never hardcoded strings scattered through the codebase — here, instead, you get one canonical source (Purpose.PASSWORD_RESET) that autocompletes and can't be typo'd.

# 4. Body — line by line
# python
#     user = models.ForeignKey(
#         "accounts.User", on_delete=CASCADE, related_name="verification_codes"
#     )

# Right side first (the value being assigned): models.ForeignKey(...) — this creates a relationship field: "this table points to a row in another table."

# "accounts.User" — the target model, written as a string "app_label.ModelName" instead of importing the User class directly. This is called a lazy reference. Why? To avoid circular imports — if accounts/models.py ever needs to import something from this file (or vice versa), a direct from accounts.models import User at the top could create an import loop that crashes on startup. The string form lets Django resolve it later, after all apps have loaded.
# on_delete=CASCADE — tells Django: "if the related User row is deleted, delete this VerificationCode row too." (This is the parameter broken by the bad import above — as written, this will crash.) It makes sense here: an orphaned verification code with no user attached is meaningless, so cascading the delete is the right behavior — the bug is only in which CASCADE got imported.
# related_name="verification_codes" — lets you go backwards from a User object to all their codes: some_user.verification_codes.all(). Without this, Django would auto-generate a clunkier default name.

# Left side: user — the attribute name on this model. In the database, Django actually creates a column called user_id (foreign keys store the related row's primary key).

# python
#     purpose = models.CharField(max_length=30, choices=Purpose.choices)
# models.CharField — a text column with a required maximum length.
# max_length=30 — the database column can hold at most 30 characters (required by CharField, unlike TextField).
# choices=Purpose.choices — restricts this field's valid values to whatever's defined in Purpose above. Purpose.choices is an automatically-generated list of (value, label) pairs that Django builds for you from the TextChoices class. This gives you validation (Django admin/forms reject anything not in the list) and a dropdown UI, all from the enum you defined earlier.
# python
#     code = models.CharField(max_length=10)
# Stores the actual OTP code as text (your memory notes it's a 6-digit code — max_length=10 leaves a little headroom).
# python
#     expires_at = models.DateTimeField()
#     used_at = models.DateTimeField(null=True, blank=True)
# models.DateTimeField() — a column storing a full date+time.
# expires_at has no extra options, meaning it's required — every code must have an expiry.
# used_at has null=True, blank=True:
# null=True — allowed to be empty (NULL) in the database.
# blank=True — allowed to be empty in Django forms/validation.
# You need both because they control two different layers. A code starts life with used_at = None (unused), and gets set to a real timestamp the moment someone redeems it. This is how the model tracks "used vs unused" without a separate boolean field — the timestamp itself is the flag, and it also tells you when it was used.
# python
#     class Meta:
#         ordering = ["-created_at"]
#         indexes = [
#             models.Index(fields=["user", "purpose", "used_at"]),
#         ]
# class Meta: is a special nested class Django looks for by name — it doesn't hold fields, it holds configuration about the model itself.
# ordering = ["-created_at"] — by default, any query (VerificationCode.objects.all()) comes back newest-first. The - prefix means descending. created_at isn't defined in this file — it must come from BaseModel, confirming that inheritance is doing real work here.
# indexes = [...] — a database index is a lookup structure that makes searches faster at the cost of slightly slower writes. models.Index(fields=["user", "purpose", "used_at"]) builds one index across all three columns together, because the most common query this model needs to answer fast is: "find this user's active (unused) code for this purpose" — e.g., VerificationCode.objects.filter(user=u, purpose=Purpose.PASSWORD_RESET, used_at__isnull=True). A composite index (multiple columns together) speeds up exactly that combined filter, far more than three separate single-column indexes would.
# python
#     @property
#     def is_expired(self) -> bool:
#         return timezone.now() >= self.expires_at

#     @property
#     def is_used(self) -> bool:
#         return self.used_at is not None
# @property is a decorator — a function that wraps another function to change how it behaves. @ followed by a name, placed directly above a function, means "pass the function below to this decorator and use whatever it returns instead."
# What @property specifically does: it lets you call some_code.is_expired without parentheses, like it's a plain attribute, even though it's actually running a method behind the scenes. Compare: without @property, you'd need some_code.is_expired().
# def is_expired(self) -> bool: — a method definition.
# def — keyword starting a function/method definition.
# is_expired — the method's name.
# (self) — every instance method's first parameter is self, which Python automatically fills in with "the specific object this method was called on." When you write code.is_expired, Python internally calls is_expired(code) — self is code.
# -> bool — a type hint saying this method returns a bool (True/False). It's documentation for humans and tools (like your IDE or type checkers) — Python doesn't enforce it at runtime.
# Body: timezone.now() >= self.expires_at — compares the current time to the stored expiry. self.expires_at reaches into this specific instance's data (the row this Python object represents).
# is_used follows the same pattern: self.used_at is not None — checks whether the timestamp has been set. is not None (not != None) is the Pythonic way to check for None, because is compares object identity, which is the correct and faster check for the singleton None.
# python
#     def __str__(self):
#         return f"{self.purpose} code for {self.user.email}"
# __str__ is a dunder method ("double underscore" — __str__). Python calls this automatically whenever it needs to turn an object into a human-readable string — print(code), or when Django admin displays this object in a list.
# f"{...}" is an f-string — a string with {} placeholders that get filled in with live Python values.
# self.user.email — this walks the relationship: self.user follows the foreign key to fetch the related User object, then .email reads its email field. (This triggers a database query if user wasn't already loaded — worth knowing for performance later.)
# 5. Why this approach
# Timestamp-as-flag pattern (used_at): instead of two separate fields (is_used: bool, used_timestamp: datetime), one nullable timestamp does both jobs and can never disagree with itself (you can't have is_used=True but used_timestamp=None by accident).
# @property for derived state: is_expired and is_used aren't stored in the database — they're computed from data that is stored (expires_at, used_at). This avoids duplicated/stale truth: you never have to remember to update an is_expired flag somewhere, because it's always calculated fresh from the real timestamp.
# TextChoices instead of raw strings: matches your project's broader rule of never hardcoding meaningful strings loosely — Purpose.PASSWORD_RESET is checked by your editor/IDE and can't typo into "PASWORD_RESET" silently.
# 6. Connections — inputs, outputs, and where this fits
# Upstream (what creates these rows): a service function (per your project's service/selector split) — something like create_verification_code(*, user, purpose) — generates a random code, sets expires_at to now + 5 minutes, and saves it.
# Downstream (what reads/uses this model): another service checks hmac.compare_digest() (per your project notes) against the submitted code, then checks not code.is_expired and not code.is_used before accepting it, then sets used_at = timezone.now().
# The GraphQL layer: resolvers/mutations stay thin — they call the service, they never touch VerificationCode.objects directly. This file is pure data + derived properties; it has zero business logic about when to expire codes or how to compare them — that logic correctly lives elsewhere.
# BaseModel: supplies id, created_at, updated_at (inferred, since Meta.ordering uses created_at without defining it).
# 7. Advanced concepts

# Lazy string references ("accounts.User") — Django doesn't need the actual class at the moment this file is read; it only needs to know the name so it can look it up once every app's models have finished loading. This avoids the classic circular-import trap: File A imports File B, File B imports File A, Python gets stuck. Strings sidestep the problem entirely.

# Composite indexes — a database index on (user, purpose, used_at) together is not the same as three indexes on each column separately. Think of it like a phone book sorted by (last name, first name, city) — you can quickly search "last name = Smith AND first name = John," but searching by city alone gets no speed boost from this index. Design indexes around your actual query patterns, left-to-right.

# Decorators (@property) — a decorator is a function that takes a function and returns a (possibly modified) function. @property specifically returns a special object that intercepts attribute access. Simplified mental model:

# python
# class Foo:
#     def bar(self):
#         return 42
#     bar = property(bar)   # roughly what @property does
# 8. Small example
# python
# class Cat(models.Model):
#     name = models.CharField(max_length=20)
#     fed_at = models.DateTimeField(null=True, blank=True)

#     @property
#     def is_hungry(self):
#         return self.fed_at is None or (timezone.now() - self.fed_at).seconds > 14400

# c = Cat(name="Milo")
# print(c.is_hungry)   # True — never fed, no parentheses needed

# This mirrors your file exactly: nullable timestamp as a flag, @property computing derived truth from it.

# 9. What to remember
# Watch your imports — a wrong symbol with the right name (like tkinter.CASCADE vs django.db.models.CASCADE) can compile fine as Python but crash your app logically. Always know which module a name is coming from, not just that autocomplete accepted it.
# Nullable timestamp > separate boolean flag — when you need "did X happen, and when," one DateTimeField(null=True) beats a bool + datetime pair.
# @property = a method that reads like an attribute — use it for values computed from other stored fields, so there's only ever one source of truth.
# String references ("app.Model") break circular imports between Django apps — reach for this pattern whenever two apps need to reference each other.
# Design database indexes around your actual query shape — a composite index should match the columns you filter together most often, in the order you filter them.

# Want me to send you the one-line fix for the CASCADE import so you can patch it, or would you rather find and fix it yourself as practice?