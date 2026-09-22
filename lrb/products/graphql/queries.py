from typing import Optional

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_permission
from lrb.products.graphql.inputs import ProductIdInput
from lrb.products.graphql.types import ProductConnection, ProductType
from lrb.products.selectors.get_product import get_product
from lrb.products.selectors.list_products import list_products


@strawberry.type
class ProductQuery:
    @strawberry.field
    @require_permission("products.view_product")
    def product(
        self, info: strawberry.Info, input: ProductIdInput
    ) -> Optional[ProductType]:
        current = get_current_user_or_raise(info)
        product = get_product(product_id=input.product_id)
        if not product or str(product.company_id) != str(current.company_id):
            return None
        return product

    @strawberry.field
    @require_permission("products.view_product")
    def products(
        self,
        info: strawberry.Info,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> ProductConnection:
        current = get_current_user_or_raise(info)
        items, total_count = list_products(
            company_id=str(current.company_id),
            is_active=is_active,
            search=search,
            limit=limit,
            offset=offset,
        )
        return ProductConnection(items=items, total_count=total_count)

# 1. Purpose

# This is the read side of the GraphQL products feature — ProductQuery, holding two @strawberry.field resolvers: product (fetch one) and products (paginated list/search). It also introduces your first look at require_permission actually being used as a decorator, matching the exact codenames you saw defined in PERMISSION_REGISTRY two files ago ("products.view_product").

# There's a real, serious bug here — a cross-tenant data leak — and it's worth catching before anything else in this file.

# 2. The bug: product never checks which company owns the product
# python
#     @strawberry.field
#     @require_permission("products.view_product")
#     def product(
#         self, info: strawberry.Info, input: ProductIdInput
#     ) -> Optional[ProductType]:
#         return get_product(product_id=input.product_id)

# Compare this directly against products, right below it:

# python
#     @strawberry.field
#     @require_permission("products.view_product")
#     def products(self, info, is_active=None, search=None, limit=None, offset=0) -> ProductConnection:
#         current = get_current_user_or_raise(info)
#         items, total_count = list_products(
#             company_id=str(current.company_id),
#             ...
#         )

# products correctly fetches the current user, then scopes every result to current.company_id — nobody can list a different company's products. product, right above it, does nothing of the sort. Go back and check what get_product actually does:

# python
# def get_product(*, product_id: str) -> Optional[Product]:
#     return Product.objects.filter(pk=product_id).first()

# No company filter at all. get_product was written to look up any product by ID, anywhere in the entire database — that was fine when it was just a selector, a building block meant to be used carefully by its caller. But this resolver uses it directly, unfiltered, as the entire implementation of a query any authenticated user (with the products.view_product permission — which, remember, is a delegable staff permission, not a superuser-only check) can call with an arbitrary product_id.

# The consequence: any user from Company A, who legitimately has permission to view their own company's products, can fetch any other company's product — pricing, SKU, active status — just by guessing or enumerating product IDs. This is the exact same shape of bug as login's account-status check running before the password check — a check that exists correctly in one place, but is missing at a different entry point into the same data. It's arguably more serious here, since it's not just "which error message leaks" — it's the actual private business data of a completely unrelated company.

# The fix

# get_product itself is fine as a general-purpose selector — the fix belongs in the resolver, matching what products already does correctly:

# python
#     @strawberry.field
#     @require_permission("products.view_product")
#     def product(
#         self, info: strawberry.Info, input: ProductIdInput
#     ) -> Optional[ProductType]:
#         current = get_current_user_or_raise(info)
#         product = get_product(product_id=input.product_id)
#         if not product or str(product.company_id) != str(current.company_id):
#             return None
#         return product

# Returning None (rather than raising) when the product exists but belongs to a different company is the deliberate choice here — it makes "this product doesn't exist" and "this product exists, but you're not allowed to see it" indistinguishable from the outside, which is exactly the enumeration-symmetry principle you already applied to forgot_password and reset_password — the same lesson, showing up again in a third, different shape (authorization scoping this time, not existence-checking).

# 3. New concept: @require_permission(...) — and why the decorator order matters
# python
#     @strawberry.field
#     @require_permission("products.view_product")
#     def product(self, info, input) -> Optional[ProductType]:

# require_permission is a decorator factory — require_permission("products.view_product") is a function call that returns a decorator, which is then applied to product. (You've actually already seen this exact shape today, without me naming it: @transaction.atomic is always used bare, but @strawberry.mutation and @strawberry_django.type(Product) both take arguments the same way — the parentheses mean "call this first to configure the decorator, then apply the result.")

# The stacking order here is correct, and it's worth understanding exactly why, since getting it backwards would be a subtle, easy-to-miss mistake. Decorators apply bottom-up — the one closest to def wraps the raw function first:

# require_permission("products.view_product") wraps product first, producing a new function that checks the permission, then calls the original product if it passes.
# strawberry.field then wraps that already-permission-checked function, registering it as a GraphQL resolver.

# If the order were reversed —

# python
# @require_permission("products.view_product")
# @strawberry.field
# def product(...): ...

# — strawberry.field would run first, turning product into a Strawberry-specific field descriptor object (not a plain callable anymore), and require_permission would then be trying to wrap that — which likely wouldn't behave as intended, since it's no longer wrapping the actual resolver logic in the way GraphQL execution expects. The rule of thumb: framework-registration decorators (@strawberry.field, @strawberry.mutation) almost always belong on the outside (written first/topmost); your own cross-cutting checks (permissions, logging) belong closer to the function itself. This file gets that right in both resolvers.

# 4. Everything else — quick confirmation
# python
#         current = get_current_user_or_raise(info)
#         items, total_count = list_products(
#             company_id=str(current.company_id),
#             is_active=is_active,
#             search=search,
#             limit=limit,
#             offset=offset,
#         )
#         return ProductConnection(items=items, total_count=total_count)
# get_current_user_or_raise(info) — called with just info here, versus get_current_user_or_raise(info, message="Authentication required.") in AuthMutation.change_password. Not necessarily a bug (the message parameter is very plausibly optional with a sensible default) — but it's the same "different call site, worth checking the real signature" flag you've now learned to raise reflexively rather than assume either way.
# items, total_count = list_products(...) — tuple unpacking: this only works if list_products (via paginate_queryset) actually returns something with exactly two parts, in that order. You've read list_products's source — it just does return paginate_queryset(qs.order_by("name"), limit=limit, offset=offset) — so whether this line is correct depends entirely on paginate_queryset's own return shape, a file you haven't seen. Given how directly this matches ProductConnection's items/total_count fields, it's very likely intentional and correct — but it's one more example of a resolver's correctness depending on a file that isn't in front of you.
# str(current.company_id) — same defensive ID-to-string conversion pattern you saw in SessionQuery.
# 5. Connections
# This is the query-side counterpart to AuthMutation — same overall shape (thin resolver, calling a service/selector, wrapping the result), but for reads instead of writes, and introducing authorization checks you hadn't seen applied at this layer before.
# require_permission("products.view_product") is the exact codename from PERMISSION_REGISTRY, closing that loop — you can now see, concretely, how a registry entry becomes an actual enforced check on a real query.
# The bug you just found is the direct real-world reason multi-tenant systems need every single data-access path audited individually — list_products being scoped correctly doesn't protect get_product's direct usage here; each entry point needs its own explicit check, and this file is proof that even a project with clearly good conventions can miss one.
# 6. What to remember
# A selector being "safe" (scoped, careful) doesn't make every caller of it safe — get_product itself is a perfectly reasonable, general-purpose lookup; the missing scoping check belongs, and was missing, in the resolver that used it directly for authorization-sensitive data.
# When two sibling resolvers handle similar data and only one of them applies a scoping check, that's a strong, specific signal to compare them line by line — you now have direct, hands-on practice with exactly this comparison technique, applied to a genuinely serious bug.
# Decorator order matters, and the rule of thumb is: framework registration decorators go outermost, your own cross-cutting logic goes closer to the function — getting this backwards can silently break the wrapping rather than raising an obvious error.
# Returning None for "exists but you can't see it" (rather than raising, or returning it anyway) is the same enumeration-symmetry principle from forgot_password/reset_password, now applied to authorization scoping — the same underlying discipline shows up in a third distinct context.
# In a multi-tenant system, every single query and mutation touching tenant-scoped data needs its own explicit scoping check — there's no way to enforce this once, globally; it has to be verified resolver by resolver, exactly the way you just did here.
