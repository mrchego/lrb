from typing import Optional

import strawberry


@strawberry.type
class SessionType:
    user_id: strawberry.ID
    active: bool
    created_at: Optional[str] = None


# 1. Purpose

# This is your first look at a GraphQL type definition, using strawberry — the GraphQL library your project uses (per your project notes: "Uses cookiecutter Django with... Strawberry GraphQL"). SessionType defines the shape of data the GraphQL API will expose for a session — what fields a client can ask for when querying, say, activeSession { userId active createdAt }.

# This is a different kind of code from everything you've read so far. Every previous file defined behavior (functions that do something) or storage (a Django model, a database table). This file defines neither — it defines a contract: "here's exactly what shape of data the outside world (your Next.js frontend) will receive." Nothing in this file touches a database or runs any logic.

# And there's a direct, satisfying connection here: remember the very first selector you read, get_active_session, which returned a hardcoded stub dict shaped like {"user_id": ..., "active": True, "created_at": None}? This class is the GraphQL type that stub function's return value was built to match. You're now seeing both ends of that same feature.

# 2. Imports — explained from scratch
# python
# from typing import Optional

# Same as before — Optional[X] means "an X, or None."

# python
# import strawberry
# Plain import strawberry (not from strawberry import X) brings in the whole module, accessed as strawberry.whatever. This is a stylistic choice: since you'll be using several different things from this library (@strawberry.type, strawberry.ID, and later probably strawberry.field, strawberry.mutation, etc.), importing the module itself keeps every usage clearly labeled as "this comes from strawberry" without needing a long list of individual imports at the top.
# What is Strawberry, conceptually? It's a Python library that lets you define a GraphQL API using ordinary Python classes and type hints, instead of writing GraphQL's own schema language by hand. You write a Python class; Strawberry reads it and generates the matching piece of GraphQL schema automatically.
# 3. Signature — piece by piece
# python
# @strawberry.type
# class SessionType:
# @strawberry.type — a decorator, the same concept as @property from the very first file, but doing something different here: instead of changing how one method behaves, it registers this entire class with Strawberry as a GraphQL object type. Without this decorator, SessionType would just be a plain, inert Python class — Strawberry wouldn't know it's supposed to become part of your GraphQL schema.
# class SessionType: — same class keyword you saw in VerificationCode, but notice: no parent class in parentheses this time. VerificationCode(BaseModel) inherited from something; SessionType: doesn't inherit from anything. That's fine — not every class needs a parent. This one is a plain new class, and its GraphQL-ness comes entirely from the decorator above it, not from inheritance.
# Naming convention: SessionType — ending a Strawberry type's name with Type is a common convention to visually distinguish "this is the GraphQL-facing shape" from, say, a Django model or a plain Python class used elsewhere with a similar name.
# 4. Body — step by step, a new syntax pattern
# python
#     user_id: strawberry.ID
#     active: bool
#     created_at: Optional[str] = None

# This is a syntax shape you haven't seen in a class body before — no = on the first two lines, just name: type. This is class-level type annotation without assignment — and it means something specific in this context.

# user_id: strawberry.ID — declares a field named user_id, typed as strawberry.ID. strawberry.ID is a special GraphQL scalar type representing a unique identifier — GraphQL treats IDs as a distinct type from a plain string, even though it's serialized as a string, because clients and tools can use that distinction (e.g., caching by ID, or knowing "this field is meant to identify something, not display text").
# active: bool — a field named active, typed as a plain Python boolean. Strawberry maps Python's bool directly to GraphQL's built-in Boolean scalar type.
# created_at: Optional[str] = None — this line does have an =, and that changes its meaning: this field is optional with a default value. In GraphQL terms, Optional[str] becomes a nullable String field, and = None means if nothing else sets this field when building a SessionType instance, it defaults to None (GraphQL null) automatically.
# Why do the first two lines have no = but the third does? Fields without a default (user_id, active) are required — you must supply a value every time you construct a SessionType(...). The field with a default (created_at) is optional at construction time — you can provide it, but if you don't, it falls back to None. This directly matches the pattern you'd expect from the stub get_active_session function you read earlier, which always set "created_at": None — this class is telling you that's a legitimate, expected value for that field, not a bug.

# This whole pattern — annotating a class attribute with just name: type and no assigned value — is called a class-level type annotation. Under the hood, Strawberry (and other libraries that work this way, like dataclasses and Pydantic, which you'll likely also encounter) reads these annotations at class-definition time to figure out what fields to generate, what types to expect, and which are required vs optional. This is different from a regular instance attribute you'd set inside __init__ — you're not writing any __init__ method here at all; Strawberry's decorator generates one for you behind the scenes, based on exactly these annotations.

# 5. Why this approach
# Declaring a schema through typed Python classes, instead of writing raw GraphQL schema text, means your API's shape lives in the same language as the rest of your backend, gets the same editor autocomplete and type-checking support, and can't drift out of sync with a separately-maintained .graphql schema file.
# Matching field names to what the underlying data actually looks like (user_id, not userId) — Strawberry, by convention, automatically converts Python's snake_case field names into GraphQL's conventional camelCase in the actual API (so user_id becomes userId to any client). You write natural Python; clients see natural GraphQL — you don't have to choose one style and sacrifice the other.
# Optional[str] = None for created_at specifically: if a session genuinely might not have a recorded creation time (or, more likely, the real backing data source doesn't always populate it), making this nullable in the type is what allows the resolver (whatever function actually produces a SessionType to send back) to legitimately return None here without violating the schema's contract.
# 6. Connections
# Directly matches the return shape of get_active_session — recall that function's stub body: {"user_id": user_id, "active": True, "created_at": None}. Once get_active_session is implemented for real, whatever calls it (likely a Strawberry resolver function, decorated with something like @strawberry.field) would take that dict (or a real session object) and construct a SessionType(user_id=..., active=..., created_at=...) to hand back through the GraphQL API.
# This is presumably one of several *Type classes across your project — you'd expect to find sibling files like UserType, VerificationCodeType, etc., following this exact same shape, each mirroring a Django model or service's output into a GraphQL-facing contract.
# Frontend connection: your project notes mention a Next.js/TypeScript frontend — Strawberry's schema-generation from this class is literally what lets that frontend's GraphQL queries know that activeSession { userId active createdAt } is a valid, typed query, with TypeScript types on the frontend side often auto-generated from this exact schema.
# 7. Advanced concepts

# Why GraphQL needs an explicit schema at all (unlike a normal REST JSON response): A REST endpoint can return any JSON shape it wants, and the client just has to know (from documentation, trial and error, or hope) what fields exist. GraphQL is different — the entire schema is queryable and enforced: a client can ask the API itself "what fields does SessionType have?" before ever running a real query, and the server will reject any query asking for a field that doesn't exist in a type like this one. This class isn't just documentation — it's the actual enforcement mechanism. If a resolver tried to return a SessionType missing a required field, Strawberry would raise an error rather than silently sending broken data.

# Type hints changing meaning based on context — worth naming explicitly, since you've now seen several variations: In a function signature (def f(x: str) -> bool:), a type hint is purely documentation — Python doesn't enforce it. Here, inside a @strawberry.type-decorated class, the same-looking name: type syntax is doing real structural work — it's read by Strawberry at class-definition time to actually build the GraphQL schema. Same syntax, very different amount of "power" behind it, depending entirely on what's processing the class. This is a good instinct to build generally: when you see an unfamiliar annotation-only pattern in a class body, check what decorator sits above the class — that decorator usually determines whether the annotations are inert documentation or something a library actively reads and acts on.

# 8. Small example
# python
# @strawberry.type
# class BookType:
#     title: str
#     author: str
#     pages: Optional[int] = None

# # Strawberry auto-generates a constructor from the annotations:
# b = BookType(title="Dune", author="Frank Herbert")
# print(b.pages)  # None — used the default, since we didn't supply it
# 9. What to remember
# @strawberry.type turns a plain Python class into a piece of your GraphQL schema — the decorator is what gives the annotations below it real meaning, not just documentation value.
# name: type with no = means a required field; adding = default makes it optional — this is true both here and in similar libraries (dataclasses, Pydantic) you'll likely meet later.
# The same name: type syntax means different things in different contexts — inert hint in a function signature, real schema-building instruction inside a @strawberry.type class. Always check what decorator or base class is processing it.
# GraphQL types are an enforced contract, not just documentation — a resolver can't return data that doesn't match the type's shape without Strawberry raising an error.
# This file is the schema-side half of a data flow you've already read the other half of — get_active_session's stub return dict and SessionType's fields describe the exact same data, from two different layers (Python data vs. GraphQL contract). Recognizing when two separate files are "the same concept, two layers" is a genuinely useful skill for navigating any GraphQL + backend codebase.
