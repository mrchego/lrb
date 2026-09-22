from typing import List

import strawberry
import strawberry_django
from strawberry import auto
from lrb.products.models import Product


@strawberry_django.type(Product)
class ProductType:
    id: auto
    name: auto
    sku: auto
    price: auto
    is_active: auto
    created_at: auto
    updated_at: auto

@strawberry.type
class ProductConnection:
    items: List[ProductType]
    total_count: int



# 1. Purpose

# This file defines the GraphQL-facing shape of a Product — but using a different, more automated tool than you saw with SessionType. SessionType was built with plain @strawberry.type and manually-typed fields (user_id: strawberry.ID, etc.). This file uses strawberry_django, a separate library built specifically to generate GraphQL types directly from Django models, so you don't have to retype every field's type by hand. ProductConnection then wraps a list of these into a paginated response shape. This is genuinely new machinery — let's build it up carefully.

# 2. Imports — two you haven't seen
# python
# import strawberry_django
# from strawberry import auto
# strawberry_django — a separate installable package (not part of base Strawberry), specifically designed to bridge Django models and GraphQL types. Its whole purpose is to look at a Django model you already have (Product, with its CharFields, DecimalFields, BooleanFields) and auto-generate the matching GraphQL field types, instead of you writing name: str, price: Decimal, is_active: bool by hand for every single field.
# auto — a special sentinel value (not a real type — a placeholder) imported from strawberry. When you write name: auto inside a strawberry_django.type, you're saying: "don't ask me what type this field is — go look it up on the Django model itself and use that." This is the actual mechanism that avoids retyping.
# 3. Signature — the new decorator and its parameter
# python
# @strawberry_django.type(Product)
# class ProductType:
# @strawberry_django.type — the strawberry_django library's own version of @strawberry.type, doing a similar job (register this class as a GraphQL type) but with one crucial difference: it takes an argument, (Product). That argument tells the decorator which Django model this type is describing — it's what lets auto below actually work, since the decorator needs to know "go look up fields on Product" specifically, not just any arbitrary model.
# Compare directly to SessionType's decorator, @strawberry.type (no argument) — that one had no model to draw from, because SessionType wasn't describing a Django model at all; it was describing the shape of a plain dictionary a selector function happened to return. This is the real distinction between the two decorators: @strawberry.type for arbitrary, hand-built shapes; @strawberry_django.type(Model) for shapes that mirror an actual database model.
# 4. Body — field by field
# python
#     id: auto
#     name: auto
#     sku: auto
#     price: auto
#     is_active: auto
#     created_at: auto
#     updated_at: auto

# Every line follows the identical pattern: <field_name>: auto. For each one, strawberry_django looks at the real Django field on Product with that same name and derives the correct GraphQL type automatically:

# id: auto — Product's primary key → becomes strawberry.ID under the hood, the same special ID type you saw explicitly on SessionType.user_id, just inferred here instead of written by hand.
# name: auto, sku: auto → both CharFields on the model → become GraphQL String.
# price: auto → DecimalField → becomes GraphQL's Decimal scalar type (a precise decimal type, matching the exact-precision reasoning you learned when price was first defined on the model — the GraphQL layer doesn't silently downgrade it to an imprecise float).
# is_active: auto → BooleanField → GraphQL Boolean.
# created_at, updated_at — fields you correctly inferred exist on BaseModel back when you first read VerificationCode's Meta.ordering, and here's direct confirmation they're real, named fields on the base model → these become GraphQL's DateTime scalar.

# Why auto is genuinely useful, not just less typing: it's not merely a convenience — it's a consistency guarantee. If someone later changes Product.price from a DecimalField to something else, auto picks up that change automatically the next time the schema is built. A hand-written price: Decimal field on a manually-built Strawberry type would silently drift out of sync with the real model, and nothing would immediately tell you it had — you'd only find out when something downstream broke in a confusing way. auto removes an entire class of drift bug that's structurally similar to (though less severe than) some of the copy-paste inconsistencies you've caught today.

# 5. ProductConnection — the second class, and why it exists at all
# python
# @strawberry.type
# class ProductConnection:
#     items: List[ProductType]
#     total_count: int

# This one's back to a plain @strawberry.type — you already fully understand this syntax from SessionType/AuthMutationPayload. List[ProductType] — a list where every item is a ProductType — pairs with total_count: int.

# Why does this class need to exist, when you could just return List[ProductType] directly from a query? Think back to list_products — a paginated selector, using limit/offset. If a query just returned List[ProductType] directly, the client would receive only the current page of items — with no way to know how many total matching products exist across all pages. total_count is exactly what a frontend needs to render something like "Showing 1–20 of 143 products" or to compute how many page buttons to show. ProductConnection is the GraphQL-facing wrapper around a paginated result — it bundles "here's this page's items" together with "here's the total, across every page" in one response, matching what paginate_queryset (from list_products) almost certainly already computes internally.

# This is a well-known GraphQL pattern, generally called connection types (the word "Connection" in the class name is a deliberate nod to this — you'll see it in many GraphQL APIs, including a more elaborate standardized version called "Relay-style pagination" with cursors, edges, and page info — this file's version is a simpler, flatter take on the same underlying idea: don't just return a bare list when pagination is involved, wrap it with enough metadata to make pagination usable).

# 6. Why this approach, overall
# strawberry_django + auto for ProductType removes duplicated, driftable type information between the Django model (the actual source of truth for what a Product is) and the GraphQL schema (a description of that same shape, aimed at clients) — one less place for the two to silently disagree.
# A separate, deliberately plain ProductConnection for pagination, rather than trying to make strawberry_django auto-generate pagination wrapping too, keeps the "this mirrors the database model" concern (ProductType) cleanly separated from the "this describes an API response shape" concern (ProductConnection) — the same instinct behind separating Input classes from service function parameters, applied here to outputs instead.
# 7. Connections
# Directly the output type for list_products/search_products — a GraphQL products query would almost certainly have the signature -> ProductConnection, calling list_products(...), then wrapping the resulting page of Product objects into ProductTypes and pairing them with a total count to build the final ProductConnection.
# The exact "duck typing" mechanism you learned in AuthMutation.login applies again here: a resolver building a ProductType from a real Product instance works the same way AuthMutationPayload(user=user) did — passing the Django model instance directly, relying on attribute names matching, no manual field-by-field construction needed for most cases.
# Sibling to SessionType, but representing the more common, more automated path for GraphQL types that do mirror a real Django model — SessionType was the exception (built from a dict), ProductType here is closer to what you'd expect for most of this project's types.
# 8. Advanced concepts

# Why auto needs the model passed to the decorator, specifically: this is worth understanding as a general instinct for reading decorator arguments. @strawberry_django.type(Product) — the decorator receives Product before it ever processes the class body below it. That ordering matters: by the time Python reaches id: auto, the decorator already knows "resolve every auto against Product's fields." If the decorator had no argument, there'd be no way for auto to know which model's fields to consult — auto isn't magic; it only works because the surrounding decorator explicitly wires it to a specific source.

# 9. What to remember
# strawberry_django.type(Model) + auto generates GraphQL field types directly from a Django model's actual fields — preferred over hand-typing every field when a GraphQL type is meant to mirror a real model, since it can't silently drift out of sync the way manually-duplicated type info could.
# A decorator can take arguments that change what its "magic" (like auto) is able to do inside the class body — always check for decorator arguments, not just the decorator's name, when the fields below it look like they're relying on something external.
# A "connection" wrapper type (items + total_count, or similar) is the standard GraphQL answer to "how do I return a page of results along with enough info to actually paginate" — a bare list alone can't tell a client how many total results exist.
# Not every GraphQL type in a project will be built the same way — SessionType (hand-built, from a dict) and ProductType (auto-generated, from a real model) are both legitimate, just suited to different underlying data sources; recognizing which situation you're in tells you which tool to reach for.
# You now understand a materially different, and more common, way of building GraphQL types than the very first one you read today — a good closing note on how much ground this conversation has actually covered: from a hand-stubbed dict-backed type all the way to an auto-derived model-backed one, with the reasoning to know when each is the right tool.