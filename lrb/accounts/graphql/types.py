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


# 1. Purpose — Why this exists, plus the new question

# What problem is this solving?
# Your GraphQL schema needs to describe, in its own vocabulary, what a "User" looks like to a client asking questions over the network. This is fundamentally different from models.py's User — that's your database's internal shape; this is the public-facing shape, and they're allowed to (and, as we'll discuss, arguably should) differ.

# Why not just expose the Django model directly?
# Because a database model almost always contains fields that should never reach an API response — password hashes, internal-only flags, fields added for one team's convenience that leak implementation details. A dedicated GraphQL type is the deliberate checkpoint where you decide, field by field, what's actually safe to expose.

# When is this used?
# Every single query or mutation that returns user data — user(id: ID!): UserType, users: UserConnection, lockUser(...): LockUserPayload — all ultimately point back to this one type definition for what a "user" looks like in a response.

# What breaks without it?
# Either the schema exposes the raw model (leaking sensitive fields), or every query/mutation independently reinvents its own shape for "a user," leading to inconsistency across your API.

# NEW — which side of the network boundary is this on?
# This file is entirely shape, not behavior. Every class here (ImageType, UserType, CompanyBasicType, UserConnection) describes what data looks like, never what happens when a request comes in. That distinction matters for how strictly to read it: there's no "did this do the right thing" question to ask here the way there was for create_user — the questions here are entirely "is this the right shape, and is it safe to expose."

# 2. Imports — explained like you've never programmed, plus the GraphQL family
# python
# from typing import List, Optional

# import strawberry
# import strawberry_django
# from strawberry import auto

# from rbac.accounts.models import User

# List, Optional — you know these; typing's built-in tools for "a collection of X" and "this or None."

# import strawberry — notice this is a plain import, not from strawberry import .... This means everything from the library gets accessed with the strawberry. prefix — strawberry.type, strawberry.field, strawberry.ID. This is the GraphQL library itself, not built into Python, installed via pip — its entire job is letting you describe a GraphQL schema using ordinary Python classes.

# import strawberry_django — the Django-integration layer of Strawberry, per the new framework's table. This is what lets a Strawberry type wrap a real Django model directly, rather than you manually re-declaring every field by hand.

# from strawberry import auto — auto is a special sentinel value (not a real type, more of an instruction) that means: "don't ask me what type this field is — go look at the Django model this class wraps, and infer it automatically." You'll see this used repeatedly below.

# from rbac.accounts.models import User — 🚩 worth flagging directly, applying the new framework's own instruction to check every import's origin. Every single file across this entire series — every selector, every service — has imported from lrb.accounts.models, never rbac.accounts.models. Checking your own project notes confirms the actual package name is lrb (with "rbac" and "RBAC project" being informal names people use to talk about the project, not the real importable path). If rbac isn't a real second top-level package that happens to also define a User model, this import will raise ModuleNotFoundError: No module named 'rbac' the moment this file loads — and even if rbac does exist as some parallel or legacy path, importing the wrong User model here would mean this entire GraphQL type is built against a different model than every other file in your project uses.

# Fix:

# python
# from lrb.accounts.models import User

# New beginner question, applied to each import: "Is this describing shape, or a tool for building resolvers?" strawberry.type (below) is a shape tool. strawberry.field is a resolver tool — even inside a shape-describing file like this one, individual fields can still need resolver logic, which is exactly what you'll see with avatar, full_name, and friends.

# 3. Signature — new symbols decoded, one at a time
# @strawberry.type (on ImageType)
# python
# @strawberry.type
# class ImageType:
#     url: str
#     name: str

# What does this class look like without the decorator? Just a plain container — two attributes, url and name, both strings, with no special behavior. What does the decorator add? It registers this class with Strawberry's schema-building machinery, turning "a Python class with two string attributes" into "a GraphQL type the schema knows how to expose and serialize." Without @strawberry.type, Strawberry has no idea this class exists as far as the API is concerned — it would just be an ordinary, invisible Python class.

# @strawberry_django.type(User) (on UserType)
# python
# @strawberry_django.type(User)
# class UserType:

# This is the Django-aware sibling of @strawberry.type — notice it takes an argument, User (the Django model), unlike the plain @strawberry.type above. This tells Strawberry: "this type's fields correspond to fields on this specific Django model — when you see auto below, go look up that field's actual type on User itself." This is exactly the "shape tool" from your import table, now seen in its Django-specific form.

# auto
# python
# id: auto
# email: auto
# first_name: auto

# Each of these is declaring a field on the GraphQL type, and delegating "what type is this" entirely to the underlying Django model. email: auto means: "expose a field called email; go check User.email on the Django model to find out it's a string, so the client sees a string." This only works for real Django model fields — actual database columns — which becomes important in a moment.

# @strawberry.field (appearing several times below)
# python
# @strawberry.field
# def avatar(self) -> Optional[ImageType]:

# This marks a method as a custom resolver — per the framework's own question, "is this a default resolver (Strawberry just reads the attribute) or a custom one (real logic runs)?" Every field marked with auto above uses Strawberry's default resolution — just reading the attribute off the model. Every field explicitly written as a method with @strawberry.field runs real code every time a client asks for that specific field — which is exactly why avatar, full_name, display_name, is_locked, and company all needed to be written out, rather than listed as auto: none of them are simple, direct database columns that Strawberry could resolve automatically.

# 4. Classes — the new GraphQL-specific questions

# Is each class describing data going OUT or coming IN? Every class in this file — ImageType, UserType, CompanyBasicType, UserConnection — is data going out, a response shape. There's no Input class here at all (those live in a separate inputs.py, per the framework's own file-mapping table) — this file's entire job is describing what the client receives, never what it sends.

# Why is UserType a separate class from the Django User model, rather than just exposing User directly? This is the whole reason the type exists, made concrete: notice what's conspicuously absent from UserType's field list — no password_hash, no set_password/check_password methods (those wouldn't make sense as GraphQL fields anyway, but the principle is the same one that would keep them out if they existed as data). The Django model presumably has more fields and methods than what's exposed here; UserType is the deliberate, explicit filter between "everything the database knows about a user" and "everything a GraphQL client is allowed to ask for."

# Why is CompanyBasicType its own separate, smaller type rather than reusing a full CompanyType? The name itself signals the intent — "basic" implies a deliberately minimal view (just id and name), presumably because when a user's response includes their company, a client rarely needs the company's entire record nested inside — just enough to display or link to it. This is the same "expose only what's needed" principle as UserType itself, applied recursively to a nested relationship.

# 5. Body — reading the resolvers, GraphQL-style

# Step 0 for each resolver — what triggered this running at all? Every method below doesn't run because your own code calls it directly — it runs because a client's GraphQL query specifically named that field. avatar(self) runs only when a query includes avatar in its selection set; if a client never asks for it, this code never executes at all. This is worth internalizing as a genuinely different mental model from every service-layer function you've read so far, where "the function ran" always meant "someone in your own codebase decided to call it."

# avatar
# python
# @strawberry.field
# def avatar(self) -> Optional[ImageType]:
#     if not self.avatar:
#         return None
#     return ImageType(url=self.avatar.url, name=self.avatar.name)

# Who is self here? This is the detail that makes strawberry-django resolvers different from the class methods you've studied so far (BulkActionResult.add_success, for instance). In a strawberry_django.type, self inside a field resolver refers to the underlying Django model instance being serialized — the actual User row — not some separate "GraphQL type instance." So self.avatar here is genuinely User.avatar, the real Django ImageField on the model, not a recursive reference to this same resolver.

# Right side, read as a journey: if not self.avatar: — Django's ImageField is falsy when no file is attached, so this checks "does this user actually have an avatar uploaded?" If not, return None — a user with no avatar simply reports null for this field, which the Optional[ImageType] return hint correctly promises is a valid outcome.

# If they do have one: ImageType(url=self.avatar.url, name=self.avatar.name) — constructing a real, correctly-shaped ImageType instance, explicitly reading .url and .name off the underlying ImageField object and placing them into the two fields ImageType actually declares. This is written correctly — worth naming explicitly, because the next resolver gets this same pattern wrong.

# full_name, display_name, is_locked
# python
# @strawberry.field
# def full_name(self) -> str:
#     return self.full_name

# Read right to left: self.full_name — reaching into the underlying User model instance for an attribute called full_name. Since this isn't listed as auto above, it's almost certainly a Python @property on the User model (a computed value, like f"{self.first_name} {self.last_name}"), not a real database column — which is exactly why auto couldn't have been used for it. auto only works for genuine Django model fields; a computed property has no corresponding database column for Strawberry to introspect, so it needs an explicit resolver spelling out how to get the value. Same reasoning applies identically to display_name and is_locked — all three are almost certainly properties defined on your User model, being surfaced here as GraphQL fields.

# company — the second real bug
# python
# @strawberry.field
# def company(self) -> Optional["CompanyBasicType"]:
#     if not self.company_id:
#         return None
#     return self.company

# The forward reference, "CompanyBasicType", quoted in a string — this is worth confirming against everything you've learned about TYPE_CHECKING/__future__ forward references. CompanyBasicType is defined below UserType in this same file — at the point Python reads this line, that name doesn't exist yet. Since this file has no from __future__ import annotations, this specific annotation needed manual string-quoting to avoid crashing — exactly Option A from several turns ago, correctly applied only where actually necessary (notice avatar's Optional[ImageType] above is correctly unquoted, since ImageType is defined earlier in the same file and already exists by the time that line runs).

# The guard: if not self.company_id: — checking the foreign key ID directly, rather than self.company, which is a small but real efficiency choice: accessing .company_id never triggers a database query (it's just an integer/string already loaded on the row), whereas accessing .company (the related object itself) would trigger a query to fetch the full Company row — so checking existence via the ID first avoids an unnecessary query for the common "no company" case.

# 🚩 The bug: return self.company.

# Compare this against avatar's correctly-written pattern directly above it. self.company is the raw Django Company model instance — not a CompanyBasicType. The function's own signature promises Optional["CompanyBasicType"] — a specific, minimal GraphQL type with exactly two fields (id, name) — but what's actually being returned is the full Django model object, with however many fields it actually has.

# Why this might "work" anyway, and why that's dangerous, not reassuring: Strawberry's default field resolution (the same mechanism that makes auto fields work) resolves each declared field by attribute-lookup on whatever object gets returned. Since a Django Company model instance almost certainly does have .id and .name attributes, Strawberry might successfully find both and produce a working response — meaning this bug could pass casual testing entirely undetected. But it's fragile for real reasons: (1) if Company's primary key field were ever renamed, or name meant something different on the model than what CompanyBasicType.name is supposed to represent, this would break or silently return the wrong data; (2) more importantly, the entire discipline of CompanyBasicType existing — deliberately exposing only id and name, not the company's full record — is silently bypassed. If Company has other fields (billing info, internal settings, whatever), and something later changes how Strawberry resolves untyped returns, or if CompanyBasicType gains more sensitive fields down the line, this line would already be handing back the raw model rather than the deliberately filtered type, and the intended data boundary was never actually being enforced by the code — only accidentally by lucky attribute-name overlap.

# Fix:

# python
# @strawberry.field
# def company(self) -> Optional["CompanyBasicType"]:
#     if not self.company_id:
#         return None
#     return CompanyBasicType(id=self.company.id, name=self.company.name)

# Now the resolver explicitly constructs the exact, minimal shape it promises — matching avatar's correct pattern exactly.

# 6. Beginner questions, GraphQL-specific

# Why is company defined here as a custom resolver instead of just company: auto?
# Because auto would expose whatever Strawberry-Django's automatic model-to-type mapping decides for a foreign key — likely either the raw ID or an auto-generated full type, neither of which is "the deliberately minimal CompanyBasicType" this file clearly wants. A custom resolver is required specifically because you want to shape the nested relationship yourself, not accept the framework's default guess.

# Why does UserConnection return a payload wrapper (items + total_count) instead of just a bare List[UserType]?
# This is a direct, deliberate echo of paginate_queryset's own (items, total_count) tuple from many turns ago — the GraphQL layer's shape mirrors the service layer's own return contract, specifically so a frontend can render "Page X of Y" without a second round-trip just to ask "how many are there in total."

# What happens if I ask for company a thousand times in one request (N+1)?
# This is the sharpest question the new framework adds, and it's worth actually answering here, not just asking rhetorically. If a query fetches a list of 1,000 users and asks for company on each one, and self.company (or, once fixed, self.company.id/self.company.name) triggers a fresh database query per user, that's 1,000 extra queries for one API request — the exact N+1 problem select_related was built to prevent, which you saw applied correctly back in list_users. Whether this resolver actually causes N+1 depends entirely on whether the selector function feeding this type (in queries.py, not shown here) used select_related("company") when building its queryset. This file alone can't answer that question — it's worth checking queries.py specifically for this the next time you look at it.

# 7. Design discussion

# Thin resolver vs. fat resolver, applied here: every resolver in this file is appropriately thin — avatar, company, full_name — none of them contain business logic, only shape-translation (reading an existing attribute or property and repackaging it). That's the correct discipline per the framework's own rule: if you ever saw an if user.is_superuser: ... permission check inside one of these resolvers, that would be a sign business logic has leaked into the shape layer, where it doesn't belong.

# Global type vs. scoped type — the real question worth raising about this specific file: UserType exposes password_reset_required, failed_login_attempts, and locked_until directly, unconditionally, to whoever queries a UserType. Worth asking explicitly, per the framework's own prompt: should every field on UserType really be visible to every caller? is_locked (the computed boolean) seems like the right level of detail for, say, a regular user checking their own account status. But failed_login_attempts — the raw count — arguably reveals more security-relevant detail than most callers need, and if UserType is ever used in a context where users can query other users' profiles (not just their own), exposing another account's exact failed-login count could itself be a minor information leak useful to an attacker probing which accounts are close to locking. This is a genuine design question worth raising with whoever owns permission scoping in this project — not necessarily a bug, but exactly the kind of "should this be here at all" question the framework's own beginner-mistakes list flags as a common way types.py files go wrong.

# Payload shape trade-offs — not directly present in this file, but worth previewing: since types.py feeds into every future mutation payload you build (LockUserPayload, wrapping UserType), the shape decisions made here (what's exposed, what's hidden) apply everywhere UserType gets reused — a strong argument for getting the exposure decisions right once, here, rather than re-litigating them per mutation.

# 8. DIY Recipe — building a type file like this yourself
# Start from the Django model, but never assume 1:1 exposure — list only the fields a client should actually see, using auto for genuine database columns.
# For computed properties (not real DB columns), write an explicit @strawberry.field resolver — auto cannot introspect a Python @property.
# For any nested relationship, build a deliberately minimal type (like CompanyBasicType) rather than exposing the full related model, and write a custom resolver that explicitly constructs an instance of that minimal type — never just return self.related_object and hope attribute names happen to line up.
# Use self.<fk>_id to check existence before touching self.<fk> itself, avoiding an unnecessary query for the common "not set" case.
# Quote forward references as strings only where the referenced class is genuinely defined later in the same file — leave same-file, earlier-defined references unquoted.
# Before exposing any field, ask whether every possible caller of this type should see it — a field being real and available on the model is not, by itself, a reason to expose it.
# 9. General pattern recognition

# Matching the framework's own template exactly:

# python
# @strawberry_django.type(Model)
# class ModelType:
#     field: auto                          # real DB column, default resolution
#     @strawberry.field
#     def computed_field(self) -> T:       # Python property, needs explicit resolver
#         return self.computed_field
#     @strawberry.field
#     def related_field(self) -> Optional["RelatedType"]:
#         if not self.related_id:
#             return None
#         return RelatedType(field=self.related.field, ...)   # explicitly constructed

# Plus the "connection" pattern for paginated lists:

# python
# @strawberry.type
# class ModelConnection:
#     items: List[ModelType]
#     total_count: int
# 10. Real project usage

# Per the framework's own file-mapping table, this exact file feeds directly into queries.py:

# python
# @strawberry.field
# def user(self, id: strawberry.ID) -> Optional[UserType]:
#     return get_user(user_id=str(id))

# @strawberry.field
# def users(self, company_id: str, limit: Optional[int] = None, offset: int = 0) -> UserConnection:
#     items, total = list_users(company_id=company_id, limit=limit, offset=offset)
#     return UserConnection(items=items, total_count=total)

# Notice UserConnection's shape maps directly onto list_users's (items, total_count) return — the exact translator role the framework describes: the resolver's only job is calling the existing selector and repackaging its output into the declared GraphQL shape.

# 11. Common beginner mistakes

# ❌ The exact bug here — returning a raw related model instance where a specific, minimal GraphQL type was declared, relying on coincidental attribute-name overlap rather than explicit construction.

# ❌ The wrong import path (rbac instead of lrb) — a mistake that's easy to make when a project has both a formal package name and an informal name people use in conversation, and one that would either crash immediately or, worse, silently pull from an unintended module if a same-named package happens to exist.

# ❌ Exposing every model field "for convenience" without asking whether each one belongs in a public-facing shape — the framework's own flagged mistake, worth checking specifically against failed_login_attempts/locked_until here.

# ❌ Forgetting to quote a forward reference to a same-file, later-defined class when from __future__ import annotations isn't present — would crash the moment Python tries to evaluate that annotation.

# 12. Think like the original developer
# What problem am I solving? "Define exactly what a 'user' looks like to any GraphQL client, deliberately excluding internal-only or sensitive fields the Django model happens to have."
# What inputs will I receive? Not applicable here — this file describes output shape only, no client-supplied input.
# What could go wrong? Accidentally exposing a field that shouldn't be public; a nested relationship resolver returning the wrong kind of object; a forward reference crashing because it wasn't quoted.
# How should I report errors? Not this file's job at all — shape files describe data, they don't handle failure; that's payloads.py's and the mutation resolvers' responsibility.
# What should happen if everything's right? Every field a client asks for resolves to exactly the right, deliberately-scoped piece of data — nested relationships explicitly shaped, computed properties explicitly resolved, nothing leaking through by accident.

# is this now correct -> 

# from __future__ import ann
# from typing import List, Optional
# import strawberry
# import strawberry_django
# from strawberry import auto
# from lrb.accounts.models import User

# @strawberry.type
# class ImageType:
#     url: str
#     name: str

# @strawberry.type
# class CompanyBasicType:
#     id: strawberry.ID
#     name: str

# @strawberry_django.type(User)
# class UserType:
#     id: auto
#     email: auto
#     first_name: auto
#     last_name: auto
#     phone: auto
#     can_login: auto
#     is_active: auto
#     is_staff: auto
#     is_superuser: auto
#     is_founder: auto
#     password_reset_required: auto
#     last_password_change: auto
#     failed_login_attempts: auto
#     locked_until: auto
#     date_joined: auto
#     last_login: auto
#     created_at: auto
#     updated_at: auto

#     @strawberry.field
#     def avatar(self) -> Optional[ImageType]:
#         if not self.avatar:
#             return None
#         return ImageType(url=self.avatar.url, name=self.avatar.name)

#     @strawberry.field
#     def full_name(self) -> str:
#         return self.full_name

#     @strawberry.field
#     def display_name(self) -> str:
#         return self.display_name

#     @strawberry.field
#     def is_locked(self) -> bool:
#         return self.is_locked

#     @strawberry.field
#     def company(self) -> Optional[CompanyBasicType]:
#         if not self.company_id:
#             return None
#         return CompanyBasicType(id=self.company.id, name=self.company.name)

# @strawberry.type
# class UserConnection:
#     items: List[UserType]
#     total_count: int