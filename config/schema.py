import strawberry

from lrb.accounts.graphql.mutations import UserMutation
from lrb.accounts.graphql.queries import UserQuery
from lrb.authorization.graphql.mutations import RoleMutation
from lrb.authorization.graphql.queries import RoleQuery
from lrb.company.graphql.mutations import CompanyMutation
from lrb.company.graphql.queries import CompanyQuery
from lrb.dashboard.graphql.queries import DashboardQuery
from lrb.identity.graphql.mutations import AuthMutation
from lrb.identity.graphql.queries import SessionQuery
from lrb.products.graphql.mutations import ProductMutation
from lrb.products.graphql.queries import ProductQuery
from lrb.staff.graphql.mutations import StaffMutation
from lrb.staff.graphql.queries import StaffQuery


@strawberry.type
class Query(
    UserQuery,
    RoleQuery,
    DashboardQuery,
    CompanyQuery,
    SessionQuery,
    StaffQuery,
    ProductQuery
):
    pass

@strawberry.type
class Mutation(
    UserMutation,
    RoleMutation,
    CompanyMutation,
    AuthMutation,
    StaffMutation,
    ProductMutation
):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)

# Good breakdown to start from — you've got the shape right, but one piece of terminology is off in a way worth fixing carefully, because it changes what's actually happening here. Let's rebuild this precisely.

# Correcting the key misunderstanding: those aren't "parameters" — they're base classes (multiple inheritance)
# python
# class Mutation(
#     UserMutation,
#     RoleMutation,
#     CompanyMutation,
#     AuthMutation,
#     StaffMutation,
#     ProductMutation
# ):
#     pass

# The parentheses after class Mutation are not a function call, and this is not passing arguments — this is the exact same syntax you saw all the way back in your very first file today: class VerificationCode(BaseModel):. There, (BaseModel) meant "VerificationCode is a BaseModel, plus whatever I add below." Here, Mutation(UserMutation, RoleMutation, CompanyMutation, AuthMutation, StaffMutation, ProductMutation) means exactly the same thing, just with six base classes instead of one — this is called multiple inheritance: Mutation is a UserMutation and a RoleMutation and a CompanyMutation and an AuthMutation and a StaffMutation and a ProductMutation, all at once.

# This is genuinely new — every class you've read today (VerificationCode(BaseModel), Product(BaseModel)) inherited from exactly one parent. This is the first time you're seeing a class inherit from several parents simultaneously.

# What that actually gives Mutation

# Think back to AuthMutation — a class you fully read, containing methods like login, logout, forgot_password, reset_password, change_password, verify_email_code, request_email_verification. Each of those was decorated @strawberry.mutation, making it a real, callable GraphQL mutation.

# When Mutation inherits from AuthMutation (along with the other five), every single one of those methods becomes available on Mutation too — not copied, not redefined, just inherited, the exact same mechanism that let VerificationCode use BaseModel's created_at/updated_at fields without redefining them itself. UserMutation presumably has its own methods (create user, update user, etc.), ProductMutation has create_product/update_product/bulk_activate_products/etc. wired up as resolvers, and so on for each of the six.

# Mutation, after this inheritance, effectively has all of those methods combined into one class — every mutation from every feature area of your entire project, gathered into a single class.

# Why pass — and this part you already had right
# python
# class Mutation(...):
#     pass

# pass is Python's "do nothing, this block intentionally has no body" placeholder — a class definition can't have a completely empty body syntactically, so pass satisfies that requirement. It's correct here because Mutation doesn't need to define anything new — every method it needs already arrived via inheritance from the six parent classes. This class exists purely to combine its parents into one — its entire job is the inheritance list itself, not any code written inside it.

# Query follows the identical pattern, just combining UserQuery, RoleQuery, DashboardQuery, CompanyQuery, SessionQuery, StaffQuery, ProductQuery instead — every @strawberry.field method from every query class in the project, gathered the same way.

# Now, @strawberry.type — refining your "output data" description
# python
# @strawberry.type
# class Query(...): pass

# @strawberry.type
# class Mutation(...): pass

# You already understand @strawberry.type correctly from earlier files — it registers a class as a real piece of the GraphQL schema. What's worth adding here: Query and Mutation are the two special root types in any GraphQL schema — literally named "Query" and "Mutation" by GraphQL convention (this isn't a name you or Strawberry chose arbitrarily; every GraphQL API in existence has a root type that plays this exact role). Every single field a client can ever ask for, and every mutation a client can ever call, has to be reachable by starting from one of these two root types. That's precisely why this file exists: it's the one place in your whole project where every scattered *Query/*Mutation class from every app (accounts, authorization, company, identity, products, staff, dashboard) gets assembled into these two required root types.

# The final line — actually building the schema object
# python
# schema = strawberry.Schema(query=Query, mutation=Mutation)
# strawberry.Schema(...) — a class instantiation, not a decorator or inheritance this time — this builds one real Schema object, the thing that actually represents your complete, queryable/mutable GraphQL API.
# query=Query — tells the schema "here's the root type holding every readable field."
# mutation=Mutation — "here's the root type holding every callable action."
# The resulting schema variable is the exact object you saw passed into GraphQLView.as_view(schema=schema, ...) in the URL routing file you just read — this is the direct connection: this one line produces the object that file's schema=schema argument refers to.
# The full picture, traced end to end
# Query(UserQuery, RoleQuery, ..., ProductQuery)       — combines every read operation
# Mutation(UserMutation, RoleMutation, ..., ProductMutation)  — combines every write operation
#         ↓
# schema = strawberry.Schema(query=Query, mutation=Mutation)  — one object representing the whole API
#         ↓
# GraphQLView.as_view(schema=schema, ...)              — the view that executes requests against it
#         ↓
# path("graphql/", csrf_exempt(...))                   — the one URL that reaches that view

# Every single resolver you've read today — login, products, bulkActivateUsers, session, all of it — is reachable specifically because its containing class (AuthMutation, ProductQuery, SessionQuery, etc.) was named in one of these two inheritance lists. If a developer built a brand-new InventoryQuery class tomorrow but forgot to add it to this file's Query(...) list, every method on it would be fully correct, fully tested, and completely unreachable — no client could ever call it, because nothing connects it to the schema. This file is the literal wiring diagram connecting every feature you've studied today into one usable API.

# Small example, to lock in the multiple-inheritance mechanic on its own
# python
# class Dog:
#     def bark(self): return "Woof"

# class Cat:
#     def meow(self): return "Meow"

# class Chimera(Dog, Cat):
#     pass

# c = Chimera()
# print(c.bark())  # "Woof" — inherited from Dog
# print(c.meow())  # "Meow" — inherited from Cat

# Chimera defines nothing itself — every bit of behavior it has came from its two parents, exactly the same shape as Query/Mutation combining six or seven parent classes each.

# What to remember
# class X(A, B, C): is multiple inheritance — X gets every method and attribute from A, B, and C combined — not a function call, not parameters, the same base-class mechanism you already knew from single inheritance (VerificationCode(BaseModel)), just extended to more than one parent at once.
# pass is correct and expected when a class's entire purpose is combining its parents — there's nothing new to define, so the body is intentionally empty.
# Query and Mutation are GraphQL's required root types — every reachable field or mutation in an entire API has to trace back to one of these two, which is exactly why every feature-specific *Query/*Mutation class in your project gets listed here.
# This file is the single wiring point between every feature you've built and the one live API a client actually talks to — a perfectly correct resolver, defined anywhere else in the project, does nothing until its class is named in one of these two inheritance lists.
# strawberry.Schema(query=Query, mutation=Mutation) produces the actual object that flows directly into GraphQLView.as_view(schema=schema, ...) — you can now trace, by name, the exact same schema variable moving from this file into the URL-routing file you read just before it.