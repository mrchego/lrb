import uuid
from django.db import models
from django.utils import timezone

class UUIDMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        abstract = True
        
        
class TimeStampedMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        
class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
        
    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()
        
    class Meta:
        abstract = True
        
        
        
# core/mixins.py — UUIDMixin, TimeStampedMixin, SoftDeleteMixin
# 1. Purpose (Why this exists)

# What problem is this solving? Across your RBAC project, almost every model needs the same handful of behaviors: a UUID primary key (established convention, discussed back in validate_uuid), a created_at/updated_at timestamp pair, and — for some models — the ability to be "soft deleted" (marked as deleted without actually removing the row from the database, so you can restore it or keep historical records). Without this file, you'd have to retype these same fields on User, Company, Role, Order, and every other model, by hand, every time — and if you ever needed to tweak how timestamps work, you'd have to hunt down and edit every single model that has them.

# Why couldn't we just write the logic directly on each model? You could — but then fixing a bug or changing behavior (say, switching from UUID4 to UUID7) means editing dozens of files instead of one.

# When is this used in a real project? Any time you define a new Django model, you'd inherit from one or more of these mixins instead of manually re-adding id, created_at, updated_at, or soft-delete fields yourself.

# What happens if this doesn't exist? Massive duplication across every model file in every app, and near-certain inconsistency (one model's timestamp field named created, another's named created_at, a third forgetting updated_at entirely).

# 2. Imports — explained like you've never programmed
# python
# import uuid

# Same built-in toolbox from validate_uuid and upload_paths.py — here it's used again for generating a new random UUID (via uuid.uuid4), not checking one.

# python
# from django.db import models

# django.db is Django's database toolbox; models is the specific piece inside it containing everything needed to define a database table as a Python class — field types (UUIDField, DateTimeField, BooleanField), and the base models.Model class every Django model must inherit from.

# python
# from django.utils import timezone

# django.utils is a grab-bag toolbox of small Django helper utilities; timezone specifically helps you work with the current date/time in a way that respects timezone settings correctly (rather than Python's plain datetime.now(), which doesn't account for your project's configured timezone, and can cause subtle bugs when your server and your database disagree about what time it is).

# 3 & 4. The classes — one at a time
# UUIDMixin
# python
# class UUIDMixin(models.Model):

# Why a class here specifically, and why does it inherit from models.Model? Every Django model must inherit from models.Model — that's the base class giving it all its database-table powers (saving, querying, etc.). UUIDMixin isn't meant to be a real, standalone database table on its own — it's meant to be mixed into other real models, contributing just one field (id) to whatever inherits from it. This pattern — a small reusable class that gets combined with others via inheritance — is called a mixin, hence the name.

# python
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
# id — the attribute name; this becomes a real database column.
# models.UUIDField(...) — a Django field type telling the database "this column stores UUID values."
# primary_key=True — marks this as the table's unique identifier column (every row's primary key must be unique; Django uses it to look up specific rows).
# default=uuid.uuid4 — notice: no parentheses here. This isn't uuid.uuid4() (which would call the function immediately and produce one fixed UUID, shared incorrectly by every row — same class of bug as the default=list mistake in the last file!). It's uuid.uuid4 without parentheses — meaning "here's the function itself; call it fresh, yourself, every time you need a new default value." Django specifically knows how to handle this: whenever a new row is created without an explicit id, Django calls uuid.uuid4() itself, at that moment, generating a genuinely new, unique UUID per row.
# editable=False — tells Django's admin/forms "don't show this field as something a human should be able to type into or change" — it's system-generated, not user input.
# python
#     class Meta:
#         abstract = True
# class Meta: — a special nested class Django looks for inside every model, used to configure model-level settings (not a real field itself, just configuration).
# abstract = True — this is the single most important line in the whole mixin. It tells Django: "never create an actual database table for UUIDMixin itself — it only exists to be inherited from." Without this, Django would try to create a real, separate UUIDMixin table in your database, which isn't what you want — you just want its id field definition to be copied into whatever model inherits from it.
# TimeStampedMixin
# python
# class TimeStampedMixin(models.Model):
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

# Two new field options worth precisely distinguishing, since they sound similar but behave very differently:

# auto_now_add=True — "set this field's value automatically only once, the very first time this row is created, and never touch it again afterward." This is exactly what you want for created_at — a row's creation time shouldn't ever change.
# auto_now=True — "set this field's value automatically every single time this row is saved, including every future update." This is exactly right for updated_at — it should reflect the most recent change, always.

# Same class Meta: abstract = True pattern as before — this mixin also isn't a real standalone table.

# SoftDeleteMixin
# python
# class SoftDeleteMixin(models.Model):
#     is_deleted = models.BooleanField(default=False)
#     deleted_at = models.DateTimeField(null=True, blank=True)
# is_deleted — a true/false flag, defaulting to False (not deleted) for every new row.
# deleted_at — a timestamp for when it was deleted, but null=True, blank=True: null=True allows the database column itself to actually store "nothing" (Django's/SQL's NULL), and blank=True allows Django's forms/validation layer to accept this field being left empty. You generally need both together for an optional field — null controls the database level, blank controls the validation level; they're two separate concerns that happen to usually travel together.
# python
#     def soft_delete(self):
#         self.is_deleted = True
#         self.deleted_at = timezone.now()

# Right side, then left side, then whole line, for each:

# self.is_deleted = True — set this specific instance's is_deleted attribute to True.
# self.deleted_at = timezone.now() — timezone.now() asks "what's the current date and time, correctly accounting for timezone settings?" and stores that result onto this instance's deleted_at.

# Notice: no self.save() call anywhere in soft_delete(). This method changes the Python object's attributes in memory, but does not write those changes to the actual database. This is a real design decision worth flagging — I'll come back to it below, because it's inconsistent with the next method.

# python
#     def restore(self):
#         self.is_deleted = False
#         self.deleted_at = None
#         self.save()

# Same idea in reverse — flips is_deleted back to False, clears deleted_at back to None — but this time, self.save() is called, actually persisting the change to the database immediately.

# 6. Beginner questions, answered

# Why is Meta capitalized and abstract isn't? Meta is a class name (classes are conventionally capitalized in Python — you've seen this with every class so far: User, ApplicationError, BulkActionResult). abstract is just a plain attribute/variable name inside that class, and those are conventionally lowercase.

# Why does default=uuid.uuid4 have no parentheses, but deleted_at = timezone.now() (inside the method) does? This is a genuinely important distinction. default=uuid.uuid4 is defined at the class level — Django needs to call this function itself, fresh, at the moment each new row is created, so it needs the function itself, not an already-computed result. timezone.now(), inside soft_delete, runs live, at the exact moment soft_delete() is actually called on a real instance — so calling it immediately (with parentheses) to get "right now, this instant" is exactly correct there.

# 7. Design Discussion — the real inconsistency worth catching

# Why does restore() call self.save(), but soft_delete() doesn't?

# This is worth treating as a genuine bug/inconsistency, not a stylistic quirk. Think through what actually happens if a service does:

# python
# company.soft_delete()

# The Python object company now has is_deleted=True in memory — but the database row itself still says is_deleted=False, because nothing was ever saved. If the request ends right there, the change is silently lost — the caller might reasonably assume "I called soft_delete(), so it's deleted now," and be wrong.

# Why might this matter, or might it not? It could be intentional — maybe the developer wanted soft_delete() to just set the fields, deliberately leaving the actual .save() call up to the calling service (e.g., so the service could set other fields too, then save everything together in one database write, which is slightly more efficient than saving twice). But if that's the intent, it should be consistent — restore() shouldn't then call .save() itself while soft_delete() doesn't. Right now, a developer using both methods would reasonably expect symmetric behavior and get a nasty surprise.

# The fix — pick one behavior and apply it to both methods:

# python
#     def soft_delete(self):
#         self.is_deleted = True
#         self.deleted_at = timezone.now()
#         self.save()

#     def restore(self):
#         self.is_deleted = False
#         self.deleted_at = None
#         self.save()

# Now both methods behave identically and predictably — call either one, and the database is updated immediately, matching what a caller would naturally expect.

# 8. DIY Recipe — How to Build Your Own Mixin
# Identify a field or small group of fields that repeats across many models. IDs, timestamps, soft-delete flags, "created by" user references — anything you'd otherwise copy-paste.
# Create a class inheriting from models.Model.
# Add the shared field(s).
# Always add class Meta: abstract = True — this is the one non-negotiable step; forgetting it means Django tries to create a real, useless standalone table for your mixin.
# Add any small helper methods that operate on those specific fields (like soft_delete/restore), keeping the mixin self-contained — it shouldn't need to know anything about the other fields on whatever model eventually uses it.
# Keep every method's side effects consistent — if one method saves to the database, every conceptually-similar method on the same mixin should too, unless you have a clear, documented reason not to.
# Combine mixins on a real model via multiple inheritance:
# python
# class Company(UUIDMixin, TimeStampedMixin, SoftDeleteMixin):
#     name = models.CharField(max_length=255)
#     class Meta:
#         pass  # not abstract - this IS a real table
# 9. General Pattern Recognition
# Identify repeated fields/behavior across models
#        ↓
# Extract into an abstract base class (mixin)
#        ↓
# Real models inherit from one or several mixins
#        ↓
# Each real model gets all the shared fields "for free," with zero duplication

# This exact pattern (small, focused, abstract = True base classes, combined via multiple inheritance) is extremely common in Django projects specifically, and the general idea — "extract common behavior into small reusable base units" — shows up in virtually every object-oriented language.

# 10. Real project usage

# In your RBAC project: User, Company, Role — basically every core model — likely inherits from UUIDMixin and TimeStampedMixin (since UUIDs and timestamps are project-wide conventions), while only models that need "undo-able" deletion (maybe Company, maybe Role, but perhaps not something like a VerificationCode, which is meant to just expire) would additionally inherit SoftDeleteMixin.

# 11. Common beginner mistakes
# ❌ Forgetting abstract = True — Django creates an unwanted, unusable real table for the mixin itself.
# ❌ Writing default=uuid.uuid4() (with parentheses) instead of default=uuid.uuid4 — generates one fixed UUID at import time, shared by every row, defeating the entire purpose (same bug family as default=list from the last file).
# ❌ Inconsistent .save() behavior across related methods — exactly the bug we just found in soft_delete()/restore().
# ❌ Forgetting that auto_now_add and auto_now are mutually exclusive in purpose — using auto_now=True on a "created at" field by mistake would silently update the creation timestamp on every save, corrupting your historical record of when something was actually created.
# 12. Think like the original developer
# "Every model in this project needs a UUID primary key, not an auto-incrementing integer — I don't want to repeat that field definition everywhere."
# "Same for timestamps — every model probably wants to know when it was created and last touched."
# "Some models also need 'soft delete' — marking as gone without actually removing the row, so I can restore it or keep it for auditing."
# "These are three separate concerns — a model might want UUIDs and timestamps but not soft-delete, so I shouldn't bundle them into one giant base class; I'll make three small, focused ones instead."
# "Django has a specific mechanism (abstract = True) for exactly this kind of 'inherit fields, but don't create a real table' need — I'll use that."
# "For soft-delete specifically, flipping a flag isn't useful unless it's actually saved to the database — I need to decide, deliberately and consistently, whether these helper methods save themselves or leave that responsibility to the caller."