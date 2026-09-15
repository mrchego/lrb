from typing import List

from strawberry import auto
import strawberry
import strawberry_django

from lrb.accounts.graphql.types import UserType
from lrb.authorization.models.permission import Permission
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserPermissionOverride


@strawberry_django.type(Permission)
class PermissionType:
    id: auto
    codename: auto
    label: auto
    category: auto

@strawberry_django.type(Role)
class RoleType:
    id: auto
    name: auto
    is_default: auto
    created_at: auto
    updated_at: auto

    @strawberry.field
    def permissions(self) -> List[PermissionType]:
        return list(self.permissions.all())

    @strawberry.field
    def staff_count(self) -> int:
        return self.user_roles.count()

    @strawberry.field
    def assigned_users(self) -> List["UserType"]:
        return [ur.user for ur in self.user_roles.select_related("user").all()]

@strawberry_django.type(UserPermissionOverride)
class UserPermissionOverrideType:
    id: auto
    is_granted: auto

    @strawberry.field
    def permission(self) -> PermissionType:
        return self.permission

@strawberry.type
class EffectivePermissionType:
    user_id: strawberry.ID
    codenames: List[str]

# Teaching: GraphQL Types (PermissionType, RoleType, UserPermissionOverride, EffectivePermissionType)

# This file is a different kind of code again — not selectors/services/commands, but GraphQL type definitions: the layer that describes what shape of data your API exposes to the frontend, and how each field gets its value. New library (strawberry_django), new syntax (auto), and — importantly — a real, serious bug hiding in plain sight. Let's build this up piece by piece.

# 1. What is it?

# Four GraphQL type definitions that describe what a Permission, a Role, a UserPermissionOverride, and an "effective permissions" result look like when sent to the frontend — including some fields pulled directly from the database model, and some computed on the fly by custom Python methods.

# New pieces:

# from typing import List
# from strawberry import auto
# import strawberry_django
# @strawberry_django.type(Permission) — a different decorator from @strawberry.type
# id: auto, codename: auto — a new kind of type hint
# List[PermissionType], List["UserType"] — generic list types, including a string type hint
# strawberry.ID — a special GraphQL scalar type
# 2. How is it written?

# from typing import List
# Same typing module you met with Optional. List[X] means "a list containing items of type X" — e.g., List[str] is a list of strings, List[PermissionType] is a list of PermissionType objects. Purely a type hint — doesn't change runtime behavior.

# @strawberry_django.type(Permission)
# Compare this to @strawberry.type from your very first UserMutation file. strawberry.type (no arguments) just says "treat this class as a GraphQL type." strawberry_django.type(Permission) is a more powerful version from the strawberry-django integration library — it takes the actual Django model class (Permission) as an argument, and uses it to auto-generate GraphQL fields based on that model's real database columns, instead of you writing every field's type by hand.

# id: auto
# This is the payoff of passing Permission into the decorator above. auto (imported from strawberry) is a special placeholder meaning: "don't make me write the type here — look at the Django model's id field, and automatically figure out the correct GraphQL type for it." So codename: auto means "expose a GraphQL field called codename, and infer its type from Permission.codename's actual Django field type" (a CharField becomes GraphQL's String, for example). This saves you from manually re-declaring codename: str when Django already knows exactly what type that field is.

# @strawberry.field
# A different, more familiar decorator (plain strawberry, not strawberry_django) marking a method as a computed GraphQL field — one that isn't just a direct pass-through of a database column, but runs actual Python logic to produce its value. You'll see three of these in RoleType.

# def permissions(self) -> List[PermissionType]: return list(self.permissions.all())

# self — same as every method you've read; refers to the specific Role instance this field is being resolved for.
# self.permissions.all() — this is the actual Django ORM many-to-many relationship you learned about back in list_roles's prefetch_related("permissions") — accessing every Permission attached to this role.
# list(...) — force it into a real list (not a lazy queryset) before handing it to Strawberry, since GraphQL needs an actual, materialized list of items to serialize into the response.
# -> List[PermissionType] — tells Strawberry/GraphQL "this field returns a list of PermissionType objects" — and notice: PermissionType (defined just above, earlier in the same file) is referenced directly as a real class, no quotes needed, because it already exists by the time Python reaches this line.

# def staff_count(self) -> int: return self.user_roles.count()
# .count() — the same efficient "how many rows match, without fetching them" method from your management-command file. Returns a plain integer — how many users are assigned this role.

# def assigned_users(self) -> List["UserType"]:
# Notice: "UserType" is in quotes here, unlike PermissionType above. This is a forward reference (string-based type hint) — the same underlying idea as TYPE_CHECKING from your very first file, but expressed differently. UserType is imported at the top (from lrb.accounts.graphql.types import UserType), so technically it is already available by this point in the file — so why the quotes? Most likely: to avoid or guard against a circular import between the authorization and accounts GraphQL type modules (if accounts's types file, somewhere down the chain, needs to reference RoleType back, you'd get the same import-loop problem you learned about with TYPE_CHECKING and User). Using a quoted string type hint tells Strawberry "resolve this type by name later, once everything's loaded" rather than needing the real class object available at the exact moment this line is read — even though, in this particular file, UserType was already successfully imported directly. This is a bit of defensive consistency, even if not strictly required given the plain import above.

# return [ur.user for ur in self.user_roles.select_related("user").all()]
# A list comprehension. Read right to left: self.user_roles.select_related("user").all() — get every UserRole assignment for this role, with the related User object pre-loaded via select_related (the exact same "one" relationship optimization you learned in list_user_overrides — each UserRole points to exactly one User, so a JOIN is the efficient choice here). Then ur.user for ur in ... — for each UserRole object (ur), pull out its .user field, producing a plain list of User objects (not UserRole objects) — exactly what -> List["UserType"] promises.

# strawberry.ID
# A special GraphQL scalar type, distinct from a plain Python str. GraphQL has its own built-in type called ID, specifically meant for identifiers (primary keys, etc.) — it behaves like a string on the wire, but semantically tells API consumers "this is an identifier, not free-form text," which some GraphQL tooling treats specially (e.g., caching by ID). strawberry.ID is Strawberry's Python representation of that GraphQL concept.

# 3. Classes — from scratch, four of them

# PermissionType — a thin, direct reflection of the Permission model: id, codename, label, category, all auto-typed from the database fields, no custom logic.

# RoleType — reflects Role's own fields (id, name, is_default, created_at, updated_at) directly via auto, plus three computed fields (permissions, staff_count, assigned_users) that don't correspond to plain database columns — they're relationships and aggregates, resolved by running actual queries when a client asks for them.

# UserPermissionOverride (the GraphQL type class) — this is the file's real problem, explained fully in the next section.

# EffectivePermissionType — a plain @strawberry.type (not strawberry_django, no model passed in) — meaning this type doesn't map to any single database model at all; it's a custom, computed shape: a user's ID paired with a flat list of permission codename strings. This is almost certainly what a service (perhaps something not yet shown, like get_effective_permissions) would build and return — combining role-based permissions and per-user overrides into one simple, flattened structure for the frontend, without needing to expose the underlying Role/UserPermissionOverride complexity at all.

# 4. The bug — a genuine, serious naming collision

# Look at the top of the file:

# python
# from lrb.authorization.models.user_role import UserPermissionOverride

# This imports the actual Django model class named UserPermissionOverride.

# Then, later in the same file:

# python
# @strawberry_django.type(UserPermissionOverride)
# class UserPermissionOverride:
#     ...

# This defines a brand-new class, also named UserPermissionOverride, in the exact same module/namespace.

# What actually happens when Python reads this file top to bottom: the class UserPermissionOverride: statement creates a new class object and binds the name UserPermissionOverride to it — overwriting the name that used to point to the imported Django model. From this point onward in the file (and for anything else that imports UserPermissionOverride from this GraphQL types module), the name UserPermissionOverride refers only to the new GraphQL type — the original Django model is still passed correctly into the decorator (@strawberry_django.type(UserPermissionOverride) — evaluated before the reassignment happens, since decorator arguments are evaluated first), so the type definition itself is built correctly. But immediately after that line finishes executing, any later code in this file that tries to reference UserPermissionOverride expecting the Django model would actually get the GraphQL type instead.

# Where this becomes a real problem: look at the permission field's body:

# python
# @strawberry.field
# def permission(self) -> PermissionType:
#     return self.permission

# This particular line is actually fine on its own — self here refers to an instance of the GraphQL type at runtime (since strawberry_django types typically wrap the underlying model instance and proxy attribute access), so self.permission still reaches the real Permission object through the underlying model relationship. The danger isn't in this exact line — it's that the class name UserPermissionOverride is no longer safely reusable elsewhere in this file, or by anything importing from this module, to mean "the Django model." If any future code added to this same file wrote something like:

# python
# def some_other_field(self) -> UserPermissionOverride:   # meant the Django model!

# it would silently resolve to the GraphQL type, not the model — a confusing, hard-to-diagnose bug, especially since both classes share fields with the same names (id, is_granted), so a mix-up might not even cause an obvious crash, just quietly wrong behavior or type-checking confusion.

# Why this is easy to miss: Python doesn't warn you about this. Reassigning a name that already points to an import is completely legal syntax — there's no error, no exception, nothing at runtime that flags it. This is purely a naming discipline issue, and it's exactly the kind of thing worth training your eye to catch: whenever you see class X: immediately after from somewhere import X, stop and check whether that's intentional (it almost never is).

# The fix is simple — rename the GraphQL type to something that doesn't collide, following the same naming convention every other type in this file uses (PermissionType, RoleType — the model name plus Type):

# python
# @strawberry_django.type(UserPermissionOverride)
# class UserPermissionOverrideType:
#     id: auto
#     is_granted: auto

#     @strawberry.field
#     def permission(self) -> PermissionType:
#         return self.permission
# 5. Why?

# Why use strawberry_django.type(Model) + auto instead of manually declaring every field's type, like EffectivePermissionType does?
# Because for PermissionType and most of RoleType, the GraphQL shape is meant to directly mirror real database columns — writing codename: str by hand would just be duplicating information Django already has (the model already declares codename as a CharField). auto lets Strawberry read that information directly from the model, keeping the GraphQL type automatically in sync if the underlying field type ever changes, and reducing repeated, error-prone manual type declarations. EffectivePermissionType, by contrast, doesn't correspond to any single model at all — it's a custom computed shape, so there's nothing for strawberry_django to introspect, and plain strawberry.type with manual fields is the right (in fact, only) choice there.

# Why does RoleType need custom @strawberry.field methods for permissions, staff_count, and assigned_users, instead of just listing them as auto fields like the other four?
# Because these aren't plain database columns — they're relationships and aggregates that require an actual query to compute (a many-to-many list, a count, a mapped list of related users). auto only works for direct, simple field-to-column mappings; anything requiring custom logic, filtering, or transformation needs an explicit method with real code in its body — this is the same reasoning that led every .prefetch_related/.select_related decision in your selectors to exist in the first place, just now applied at the API-serialization layer instead of the selector layer.

# Why is assigned_users's return type wrapped in quotes ("UserType") but permissions's isn't (PermissionType)?
# As explained above — almost certainly defensive circular-import protection, given UserType comes from a different app (accounts) than this file (authorization), while PermissionType is defined locally, in the same file, with no cross-app import risk at all.

# 6. Connections

# What comes in: these types don't take input — they describe output shapes, resolved from Django model instances passed to them by GraphQL's execution engine.
# What goes out: these are exactly what a GraphQL query response is built from — a query asking for role { name, permissions { codename }, staffCount, assignedUsers { name } } would resolve field by field using exactly the logic defined here.
# Connects to selectors: RoleType.permissions and assigned_users do the same kind of relationship access you saw explicitly optimized in list_roles's prefetch_related("permissions", "user_roles__user") — but notice these type methods call .all()/.select_related() fresh, independently, without any guarantee that prefetching happened upstream. If a resolver returns a Role fetched via plain Role.objects.get(...) (no prefetch) and the GraphQL query asks for permissions, staffCount, and assignedUsers, that's three separate extra database queries per role — the exact N+1 problem list_roles was built to prevent, reintroduced here if the type's data source doesn't already have it prefetched. Worth keeping in mind as a real, connected performance consideration: the selector's optimizations only help if the data actually reaches these type resolvers already prefetched.

# 7. Advanced concepts

# A) Name shadowing — a distinct concept from the TYPE_CHECKING/circular-import pattern you learned earlier
# You've now seen two different ways a class name can cause confusion:

# TYPE_CHECKING (your very first file) — a deliberate, controlled technique to avoid a real circular import, only "importing" for type-checkers.
# This file's UserPermissionOverride collision — an accidental, undesired overwrite of a real import by a same-named class defined later in the same file. Same underlying Python mechanic (later assignment overwrites earlier one) but opposite intent — one is a careful tool, the other is a naming mistake.

# B) Decorator arguments are evaluated before the class body runs
# This is why the bug doesn't break the PermissionType decoration itself: @strawberry_django.type(UserPermissionOverride) evaluates UserPermissionOverride (getting the real, still-correctly-imported Django model at that exact moment) before Python proceeds to execute the class UserPermissionOverride: line that would reassign the name. The decorator captures the right object at the right time; it's only after that the name gets shadowed for anything coming later.

# C) strawberry_django.type(Model) vs plain strawberry.type
# A good general rule to take away: reach for strawberry_django.type(Model) + auto whenever a GraphQL type is meant to be a fairly direct reflection of one Django model's fields (reducing duplication); reach for plain strawberry.type with fully manual field declarations whenever the shape is custom-computed and doesn't map one-to-one to any single model — EffectivePermissionType is the clean example of the latter.

# 8. Small example (demonstrating the shadowing bug in isolation)
# python
# class Widget:
#     def __init__(self, size):
#         self.size = size

# real_widget = Widget(size=10)
# print(type(real_widget))   # <class '__main__.Widget'>

# class Widget:               # accidentally reusing the same name
#     def __init__(self, color):
#         self.color = color

# # From here on, "Widget" means the NEW class, not the original
# new_thing = Widget(color="red")
# print(type(new_thing))      # <class '__main__.Widget'> — looks identical in output!
# print(hasattr(new_thing, "size"))   # False — it's a completely different class now

# Same class name, same-looking output, completely different underlying class — exactly the trap in the real file.

# 9. What you should remember
# strawberry_django.type(Model) + auto auto-generates GraphQL field types directly from a Django model's real columns — use it to avoid duplicating type information Django already knows; reach for plain strawberry.type with manual fields when the shape is custom/computed and doesn't map to one model.
# @strawberry.field marks a method as a computed field, run fresh whenever that field is requested — this is where relationship traversal, aggregation, or any custom logic belongs, distinct from auto fields that pass a column straight through.
# class X: immediately after from somewhere import X silently shadows the import — Python raises no error or warning. Train your eye to catch this pattern specifically: it's one of the easiest, most consequence-free-looking mistakes to make, and one of the hardest to notice without deliberately checking for it.
# A quoted forward-reference type hint ("UserType") versus a plain one (PermissionType) often signals "this type comes from a different module/app, with a circular-import risk" — even when, as here, a direct import already technically succeeded, quoting is a defensive habit some codebases apply consistently for cross-app references.
# GraphQL type-layer relationship access (self.permissions.all(), self.user_roles.select_related(...)) can reintroduce the exact N+1 problem your selectors were built to prevent, if the underlying data wasn't already prefetched before reaching this layer — the optimization only holds end-to-end if every layer between the database and the API response cooperates.