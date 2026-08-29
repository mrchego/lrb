from django.db import models
from lrb.core.models.base import BaseModel


class Permission(BaseModel):
    codename = models.CharField(max_length=100, unique=True)
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["category", "codename"]

    def __str__(self):
        return self.codename


# This is a Django model — a completely different layer from the GraphQL files you've seen so far. Django models define the actual database tables. This one is central to your RBAC system: it's the Permission model your project notes describe as "atomic, developer-defined capabilities."

# Imports
# python
# from django.db import models
# from lrb.core.models.base import BaseModel
# django.db.models — Django's toolkit for defining database tables as Python classes. models.CharField, models.Model, etc. all come from here.
# lrb.core.models.base import BaseModel — a custom base class from your own core app, not from Django itself. This is your project's own foundation, likely adding shared fields like created_at/updated_at (you saw those exact fields on UserType in your first file) to every model that inherits from it.
# class Permission(BaseModel):

# What is it?

# class Permission(BaseModel): — defines a new class named Permission that inherits from BaseModel. Inheritance means Permission automatically gets everything BaseModel defines (fields, methods) plus whatever new things you add here — without copy-pasting that shared code into every model.

# How is it written?
# The parentheses (BaseModel) right after the class name is Python's inheritance syntax: class Child(Parent):. Compare this to the GraphQL files, where classes had no parentheses (class ImageType:) — those didn't inherit from anything meaningful; here, inheriting from BaseModel is the whole point, since it's how the model gets connected to Django's ORM (Object-Relational Mapper — the system that turns Python classes into database tables and rows) and to your project's shared fields.

# Signature
# There's no function signature here, just a class declaration with one part: the name (Permission) and its parent (BaseModel).

# The fields
# python
# codename = models.CharField(max_length=100, unique=True)
# label = models.CharField(max_length=255)
# category = models.CharField(max_length=100, blank=True)

# What is it?
# Each line is a class attribute assigned to a models.CharField(...) — Django's type for a short text column. Unlike the GraphQL files (where field: type used a colon, just a type hint), here it's field = SomeFieldType(...) — an actual assignment, because this isn't a hint about a type, it's a real object (a CharField instance) that Django inspects at startup to build your database table's columns.

# Breaking down each CharField(...) call:

# max_length=100 — a required argument for CharField, telling the database "reserve room for at most 100 characters" (this becomes a VARCHAR(100) column in SQL). Django requires this because, unlike Python strings, database text columns need a fixed maximum size.
# unique=True — on codename only. This tells the database "no two rows may ever have the same value here" — enforced at the database level, not just in your Python code. This matters a lot for codename: it's presumably the internal identifier used by require_permission(codename) in your services — if two permissions could share a codename, your permission checks would become ambiguous.
# blank=True — on category only. This is a validation setting (used by Django forms/admin), meaning "this field is allowed to be left empty in input forms." Note: this does not affect the database column itself — for that, you'd also need null=True. Its absence here means category still requires some value (even if it's just an empty string "") at the database level, but users/forms aren't forced to fill it in.

# Why three separate CharFields instead of, say, one JSON blob?
# Each field has a distinct job:

# codename — the machine-readable key your code checks against (e.g. "can_edit_orders"), hence unique=True — it must be a reliable lookup key.
# label — the human-readable name shown in an admin UI (e.g. "Can Edit Orders").
# category — a grouping tag (e.g. "Orders", "Staff") so an admin screen can organize a long list of permissions instead of showing one flat, unsorted list.

# This directly matches your project's convention: permissions are meant to be developer-defined (codename is what code refers to) but also need to be understandable to an admin building roles (label, category support a UI where an admin picks permissions to bundle into a role).

# class Meta:
# python
# class Meta:
#     ordering = ["category", "codename"]

# What is it?
# Meta is a special nested class (a class defined inside another class) that Django specifically looks for by that exact name. It doesn't represent a database column — it configures behavior for the whole model.

# Why nested, and why exactly this name?
# Django's ORM machinery specifically checks: "does this model have an inner class literally named Meta?" If so, it reads settings from it. This is a Django-specific convention you just have to know — it's not general Python behavior, it's a pattern Django's model base class looks for.

# ordering = ["category", "codename"]
# A list of field names, telling Django: "whenever you fetch a list of Permission rows without an explicit order, sort them first by category, then by codename (for permissions that share a category)." This is a default sort applied automatically to every query like Permission.objects.all(), unless a query overrides it. It makes sense with your fields: grouping permissions by category first, then alphabetically by codename within each group, is exactly how you'd want them displayed in a role-editing admin screen.

# def __str__(self):
# python
# def __str__(self):
#     return self.codename

# What is it?

# __str__ — a dunder method ("double underscore" method — Python's name for these special, built-in-recognized method names like __init__, __str__, __len__). Python automatically calls __str__ on an object whenever it needs to show that object as readable text — for example, when you print(some_permission), or when Django's admin site displays a Permission in a dropdown list.
# (self) — same self you saw in the GraphQL @strawberry.field methods: "the specific object this method is being called on" (one particular Permission row).
# return self.codename — instead of Python's default (unhelpful) text like <Permission object at 0x7f...>, this returns the permission's codename string instead.

# Why?
# Without __str__, if you opened Django's admin site and saw a dropdown list of permissions to attach to a role, every entry would show as a meaningless memory address. Defining __str__ to return codename makes every part of Django (admin, shell debugging, logs) automatically show something readable, with zero extra work anywhere else — one small method fixes the "how does this object look as text" question everywhere at once.

# Advanced concept: how this connects to "roles are collections of permissions"

# Your project notes say permissions are atomic and roles are admin-defined collections of them. This model is the atomic unit: Permission doesn't reference a Role at all — no foreign key here. That's the correct direction of the relationship: a separate Role model elsewhere almost certainly has a many-to-many field pointing at Permission (e.g. permissions = models.ManyToManyField(Permission)), meaning many roles can each contain many permissions, and this model doesn't need to know anything about roles to stay valid. Keeping Permission "dumb" and self-contained (just codename/label/category) is what makes it safe and simple to reuse across many roles.

# What I should remember
# class Child(Parent): — the parentheses after a class name mean inheritance; the child automatically gets the parent's fields/behavior. This is different from a plain type hint's colon syntax.
# field = SomeFieldType(...) in a Django model is a real object being built, not just a type hint — Django reads these objects at startup to construct actual database columns.
# unique=True is a database-level guarantee; blank=True is only a form/validation convenience — they solve different problems, and it's easy to confuse them.
# A nested class Meta: configures model-wide behavior (like default ordering) — Django looks for this exact name; it's a framework convention, not general Python.
# __str__(self) controls how an object prints/displays as text — always worth adding to models, since it makes admin panels, logs, and debugging far more readable for almost no cost.
