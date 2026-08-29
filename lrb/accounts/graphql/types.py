from __future__ import annotations
from typing import List, Optional
import strawberry
import strawberry_django
from strawberry import auto
from lrb.accounts.models import User

@strawberry.type
class ImageType:
    url: str
    name: str

@strawberry.type
class CompanyBasicType:
    id: strawberry.ID
    name: str

@strawberry_django.type(User)
class UserType:
    id: auto
    email: auto
    first_name: auto
    last_name: auto
    phone: auto
    can_login: auto
    is_active: auto
    is_staff: auto
    is_superuser: auto
    is_founder: auto
    password_reset_required: auto
    last_password_change: auto
    failed_login_attempts: auto
    locked_until: auto
    date_joined: auto
    last_login: auto
    created_at: auto
    updated_at: auto

    @strawberry.field
    def avatar(self) -> Optional[ImageType]:
        if not self.avatar:
            return None
        return ImageType(url=self.avatar.url, name=self.avatar.name)

    @strawberry.field
    def full_name(self) -> str:
        return self.full_name

    @strawberry.field
    def display_name(self) -> str:
        return self.display_name

    @strawberry.field
    def is_locked(self) -> bool:
        return self.is_locked

    @strawberry.field
    def company(self) -> Optional[CompanyBasicType]:
        if not self.company_id:
            return None
        return CompanyBasicType(id=self.company.id, name=self.company.name)

@strawberry.type
class UserConnection:
    items: List[UserType]
    total_count: int 


# from __future__ import annotations
# from typing import List, Optional
# import strawberry
# import strawberry_django
# from strawberry import auto
# from lrb.accounts.models import User

# What is it?

# from __future__ import annotations — a special import that changes how Python treats type hints. Normally Python evaluates type hints (like -> str) immediately when it reads the file. This import tells Python: "treat all type hints as plain text (strings) until something actually needs to look at them." It's a "future" feature because it eventually became Python's default behavior in later versions — this line opts into it early.
# typing — Python's built-in module for describing what kind of data something is (a list, a number that might be missing, etc.).
# List, Optional — two "shapes" from typing. List[X] means "a list containing items of type X." Optional[X] means "either a value of type X, or None."
# strawberry — the GraphQL library itself. It gives you decorators like @strawberry.type to turn plain Python classes into GraphQL types.
# strawberry_django — an extension of strawberry that connects GraphQL types directly to Django models, so you don't have to redeclare every field by hand.
# auto — a special marker (not a real type) that means "copy the type from the Django model field automatically."
# User — your actual Django model, imported from your accounts app.

# How is it written?
# from X import Y pulls one specific name (Y) out of a module (X) so you can use it directly (Y) instead of writing X.Y everywhere. import X (no from) imports the whole module, so you must write X.something to use its contents — that's why you see strawberry.type and strawberry_django.type used with the full module name, but auto and User used bare.

# Why?
# GraphQL needs to know the "shape" of your data (what fields exist, what type each one is) before it can answer queries. This file is where you translate your Django User model into a shape GraphQL understands.

# ImageType — the simplest building block
# python
# @strawberry.type
# class ImageType:
#     url: str
#     name: str

# What is it?

# @strawberry.type — a decorator. A decorator is a function that wraps another piece of code (here, a class) and changes or enhances what it does, without you rewriting the class. Written with @ directly above the thing it modifies. Here, it takes the plain Python class ImageType and registers it with Strawberry as an official GraphQL type — meaning GraphQL clients can now ask for ImageType { url name } in a query.
# class ImageType: — defines a new class (a blueprint for objects) named ImageType.
# url: str and name: str — these are type-annotated class attributes. The : separates the field name from its type. This is Python's "type hint" syntax: variable_name: type. Strawberry reads these annotations to know "this GraphQL type has two fields, both plain text (strings)."

# Signature (there's no function here, just a class with two fields)

# url → field name, str → its type (a string of text, like a web address)
# name → field name, str → its type

# Body
# There's no logic to run — this class has no methods, just declarations. When Python loads this file, it doesn't "do" anything with url and name except store them as metadata (type hints) that Strawberry later reads.

# Why?
# Your User model probably has an avatar field that's an image (a Django ImageField or similar), which typically stores a file, not simple text. GraphQL can't return a raw file object — it needs a defined shape. So ImageType is a small custom "wrapper" shape: instead of returning the whole complicated avatar file object, you return just a url (where to find the image) and a name (the filename).

# Connections
# This type is used inside UserType below, as the return type of the avatar field. It's a dependency: UserType can't compile without ImageType existing first.

# Advanced concept — why not use strawberry_django.type here too?
# strawberry_django.type(User) auto-generates fields from a Django model. But there's no Image Django model — the avatar is just a field on User. So for this small custom shape, you use the simpler @strawberry.type, which builds a GraphQL type from a plain Python class instead of a database model.

# Small example
# If a client queries:

# graphql
# { user(id: 1) { avatar { url name } } }

# Your resolver could reply with:

# python
# ImageType(url="/media/avatars/bob.png", name="bob.png")
# CompanyBasicType — same pattern
# python
# @strawberry.type
# class CompanyBasicType:
#     id: strawberry.ID
#     name: str

# Same idea as ImageType, one new piece: strawberry.ID — a special type meaning "this is a unique identifier." GraphQL treats ID differently from a plain string in its schema (clients and tools know it's meant for identifying/looking up objects, not for displaying text), even though under the hood it behaves like a string.

# Why does this exist as a separate small type instead of just using your full Company type? Because when you show a user's company, you often don't want to expose every company field (address, tax ID, internal notes, etc.) — just enough to identify it (id, name). This is a common GraphQL pattern called a "basic" or "summary" type — a deliberately trimmed-down view of a bigger object, used to avoid over-exposing data and to avoid slow queries that fetch things nobody asked for.

# UserType — the main type, built from your Django model
# python
# @strawberry_django.type(User)
# class UserType:
#     id: auto
#     email: auto
#     first_name: auto
#     ...

# What is it?

# @strawberry_django.type(User) — this decorator is different from plain @strawberry.type. It takes an argument: User, your Django model class. This is why there are parentheses — @strawberry.type needs no configuration, but @strawberry_django.type(...) needs to know which Django model to link this GraphQL type to.
# id: auto — normally you'd write id: strawberry.ID, but since this type is linked to the User model, auto says: "don't make me repeat the type — look at the User model's id field in Django and copy its type automatically." This saves you from keeping two lists of field types in sync (Django's model, and a separate GraphQL type) — a real source of bugs if they drift apart.

# How is it written?
# Every line follows the same pattern: django_field_name: auto. Each one must exactly match a real field name on the User model — Strawberry-Django looks it up by that name. There's no logic here, just a declaration: "expose this Django field to GraphQL, and figure out its type yourself."

# Why so many auto fields listed individually, instead of "just expose everything"?
# This is a deliberate security/design choice, and it connects directly to your project's RBAC conventions. If Strawberry auto-exposed every model field by default, you could accidentally leak something sensitive — like a password hash — to the outside world. By listing fields explicitly, the developer controls exactly what's queryable. Notice: there's no password field listed here, even though User almost certainly has one. That's not an accident — it's excluded on purpose.

# The custom @strawberry.field methods — computed fields
# python
# @strawberry.field
# def avatar(self) -> Optional[ImageType]:
#     if not self.avatar:
#         return None
#     return ImageType(url=self.avatar.url, name=self.avatar.name)

# What is it?

# @strawberry.field — a different decorator, used on a method (function inside a class) instead of a class. It tells Strawberry: "this isn't a plain data field copied from the model — it's computed by running this function whenever someone asks for it."
# def avatar(self) -> Optional[ImageType]: — a method definition.

# Signature, piece by piece

# def — keyword that starts a function/method definition.
# avatar — the method's name; this becomes the GraphQL field name clients will query (avatar { url name }).
# (self) — self is the first parameter of every instance method in Python. It refers to "this specific object" — in this case, the specific User row being resolved (e.g., the user with id=5). Strawberry passes the underlying Django User instance in as self automatically; you don't call this function yourself.
# -> Optional[ImageType] — the return type hint. The -> arrow, read after the closing ), tells you (and tools, and Strawberry) what type the function returns. Optional[ImageType] means "either an ImageType object, or None."

# Body, line by line

# if not self.avatar: — self.avatar accesses the avatar attribute on the underlying Django User object (this is Django's file field, not the GraphQL ImageType!). not self.avatar is True when there is no avatar set (Django file fields are "falsy" — treated as False in an if — when empty).
# return None — if there's no avatar, immediately stop the function and give back None. This matches the Optional[...] promise — it's allowed to return nothing.
# return ImageType(url=self.avatar.url, name=self.avatar.name) — if there is an avatar, build a new ImageType object. self.avatar.url and self.avatar.name are Django's own built-in properties on a file field (they give you the file's public URL and its filename). ImageType(url=..., name=...) calls the class like a function to construct an object — this is called keyword argument construction: url= and name= explicitly say which value goes into which field, so order doesn't matter and it's harder to mix them up by mistake.

# Why?
# This is the classic reason for @strawberry.field instead of auto: the raw Django avatar field isn't directly GraphQL-shaped (it's a Django FileField/ImageField object, not a simple string or the ImageType shape). So the developer writes a small function to translate the raw model data into the GraphQL shape, and to safely handle the "no avatar" case instead of crashing.

# Advanced concept: read this method "right side first"
# Since you've been learning to read code by finding the action first: in return ImageType(url=self.avatar.url, name=self.avatar.name), the rightmost things evaluate first — Python reads self.avatar.url and self.avatar.name (fetches those values), then plugs them into ImageType(...) to build the object, then return sends that finished object back out. Constructing an object is really just "gather the ingredients, then call the recipe."

# The next three follow the exact same pattern, just simpler (no if, straight passthrough):

# python
# @strawberry.field
# def full_name(self) -> str:
#     return self.full_name

# @strawberry.field
# def display_name(self) -> str:
#     return self.display_name

# @strawberry.field
# def is_locked(self) -> bool:
#     return self.is_locked

# Why do these exist at all, if they just return self.full_name directly — isn't that what auto does?
# Here's the key insight: full_name, display_name, and is_locked are almost certainly not real database columns on the User model — they're Python @property methods defined on the Django model itself (computed values, like combining first_name + " " + last_name). auto only works for actual database fields that Strawberry-Django can introspect from the model's schema. For computed Python properties, you must manually expose them with @strawberry.field, because Strawberry has no automatic way to know their type or that they even exist — you have to tell it explicitly with the -> str / -> bool return hint.

# python
# @strawberry.field
# def company(self) -> Optional[CompanyBasicType]:
#     if not self.company_id:
#         return None
#     return CompanyBasicType(id=self.company.id, name=self.company.name)

# Same shape as avatar. One detail worth noting: it checks self.company_id, not self.company. This is a Django performance pattern — company_id is just a plain integer (the foreign key value) sitting on the object already, no database query needed to check it. Accessing self.company (without _id) would trigger a database lookup to fetch the full related Company row. Checking the cheap _id field first avoids an unnecessary query when there's no company at all.

# UserConnection
# python
# @strawberry.type
# class UserConnection:
#     items: List[UserType]
#     total_count: int

# What is it?
# Back to the simple @strawberry.type pattern (no Django model attached). Two fields:

# items: List[UserType] — a list where every item is a UserType.
# total_count: int — a plain whole number.

# Why?
# This is the pagination pattern. If you have 10,000 users, you never return all of them in one GraphQL response. Instead, a resolver returns one "page" of users (items) plus the total number that exist (total_count), so the frontend can build page controls ("showing 20 of 10,000") without fetching everything.

# Connections
# This is the type a query like users(offset: 0, limit: 20) would return. It sits at the top of the chain: UserConnection → contains many UserType → each UserType contains one ImageType and one CompanyBasicType.

# What I should remember
# @strawberry.type vs @strawberry_django.type(Model): use the plain one for custom/computed shapes with no matching database table; use the Django-linked one when the type mirrors a real model, so you get auto field-typing for free.
# auto only works for real model fields. Computed Python properties (full_name, is_locked, etc.) need a manual @strawberry.field method with an explicit return type, because there's no database column for Strawberry to inspect.
# @strawberry.field methods take self and return a translated value — they're the bridge between "how Django stores it" and "how GraphQL should expose it," and a great place to hide None-safety checks (if not self.avatar) so the API never crashes on missing data.
# Never auto-expose everything — this file explicitly lists safe fields and leaves out sensitive ones (like the password). Being explicit about what's exposed is a security habit, not just a style choice.
# Read foreign keys the cheap way when possible: check thing_id before touching thing itself, to avoid triggering an unneeded database query.