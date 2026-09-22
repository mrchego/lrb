from typing import Iterable, Optional

from lrb.products.models import Product


def get_products_by_ids(*, product_ids:Iterable[str], company_id: Optional[str] = None ):
    qs = Product.objects.filter(pk__in=product_ids)
    if company_id:
        qs = qs.filter(company_id=company_id)
    return qs

# 1. Purpose

# A third selector, and the first one in this batch that returns multiple products instead of one. Given a list of product IDs, it fetches all matching products — optionally narrowed down to just one company's products, if a company_id is supplied. This looks small, but it introduces two genuinely new concepts: a new typing tool (Iterable) and a new Django query lookup (__in), plus one real thing worth questioning about its return type.

# 2. New import: Iterable
# python
# from typing import Iterable, Optional
# Iterable[str] — a type hint meaning "anything you can loop over with for x in ..., where each item is a str." This is deliberately broader than List[str]. A list, a tuple, a set, or even a generator all count as Iterable — the type hint is saying "I don't care what specific container you hand me, only that I can iterate over it and each item is a string." Compare this to List[MutationError] from the AuthMutationPayload file — that one specifically committed to "a list," because the payload needed an actual, concrete list Strawberry could serialize. Here, the function only ever loops through product_ids once (implicitly, inside the database query it builds) — it never needs list-specific behavior like indexing or len() — so Iterable is the more honest, more permissive hint: accept the loosest type that still lets the function do its job.
# 3. New query pattern: __in
# python
#     qs = Product.objects.filter(pk__in=product_ids)
# pk__in=product_ids — another double-underscore lookup, like used_at__isnull from verify_code. __in means: "match rows where this field's value is any one of the values in this collection." This single line generates SQL roughly equivalent to WHERE id IN (id1, id2, id3, ...) — fetching every matching product in one query, rather than looping through product_ids in Python and running a separate .filter(pk=...).first() for each one (which would mean, say, 50 separate database round-trips for 50 IDs, instead of one).
# 4. The rest of the body
# python
#     if company_id:
#         qs = qs.filter(company_id=company_id)
#     return qs
# qs = qs.filter(company_id=company_id) — queryset chaining. This is worth understanding precisely: .filter(...) doesn't modify qs in place — it returns a new queryset with the additional condition applied, which is then reassigned back to the same variable name qs. This is the same pattern conceptually as user.failed_login_attempts += 1 from earlier (read the old value, compute something new, store it back under the same name) — except here, what's being "recomputed" is a query, not a number.
# if company_id: — only adds the company filter when one was actually provided, since company_id: Optional[str] = None means callers can omit it entirely.
# return qs — returns the queryset itself, not a realized list of Product objects.
# 5. The interesting thing worth questioning: no return type hint, and what's actually being returned
# python
# def get_products_by_ids(*, product_ids:Iterable[str], company_id: Optional[str] = None ):

# This function has no -> at all — not even the recurring "missing return hint" pattern you've flagged as a minor gap elsewhere, since even a missing hint on those functions still had you able to infer the real return type easily (Optional[Product], bool). Here, it's worth actually asking: what type would you even write here if you were fixing this?

# The honest answer is QuerySet[Product] — because Product.objects.filter(...) doesn't return a list, or a Product, or an Optional[Product] — it returns a Django QuerySet, which is a special, lazy object. This is a real, important Django concept worth slowing down for.

# A QuerySet doesn't run any database query the moment you build it. Product.objects.filter(pk__in=product_ids) on its own doesn't touch the database at all — it just builds up a description of a query, step by step, as you chain .filter() calls onto it. Django only actually executes SQL and fetches rows when the queryset is evaluated — which happens the first time something tries to actually use the results: looping over it (for p in qs:), converting it to a list (list(qs)), calling len(qs), or accessing it in a template.

# Why does this matter for this specific function? Because it means get_products_by_ids doesn't actually fetch anything from the database by itself — it hands back an unexecuted, still-lazy query, and the caller decides when (and whether) to actually run it. This is genuinely useful: a caller could take the returned qs and chain even more filtering onto it (get_products_by_ids(product_ids=[...]).filter(is_active=True)), or call .count() on it to just get a number without ever loading full rows, or pass it straight into a paginated GraphQL response that only evaluates a page at a time — all without this selector needing to anticipate any of those specific needs in advance.

# Contrast this directly against get_product_by_sku and get_product, which both called .first() before returning — .first() is one of the operations that forces immediate evaluation (it has to actually run the query to know what the first row is). Those two selectors hand back a real, already-fetched Product object (or None). This one hands back a still-unexecuted QuerySet — a meaningfully different kind of return value, even though all three "return products" in some loose sense.

# The correct type hint, then, would be:

# python
# from django.db.models import QuerySet

# def get_products_by_ids(*, product_ids: Iterable[str], company_id: Optional[str] = None) -> QuerySet[Product]:

# Leaving it off isn't a crash bug — but it does hide a genuinely important fact about how this function behaves from anyone just reading its signature.

# 6. Why this approach
# Batch-fetching with pk__in instead of looping and calling get_product repeatedly avoids the classic "N+1 queries" performance problem — a single round-trip to the database instead of one per ID, which matters enormously once you're fetching dozens or hundreds of products (a shopping cart, an order's line items, a bulk import).
# Returning the lazy QuerySet instead of forcing it into a list — gives the caller maximum flexibility (further filtering, ordering, pagination, or just a .count()) without this selector needing to guess in advance what the caller actually wants to do with the results.
# Optional[str] = None for company_id — makes this one function serve two related needs (all matching products globally, or scoped to one company) without duplicating the whole function body the way get_product_by_sku/get_product chose to stay separate — a reasonable call here specifically because the "extra" logic is a single, cheap, optional if, not a fundamentally different lookup strategy.
# 7. Connections
# Likely caller: something that already has a list of product IDs and needs the actual product data — a shopping cart resolver, an order-confirmation screen showing several line items at once, or a bulk "check these SKUs are all valid" admin action.
# Sibling to get_product/get_product_by_sku, but representing the "many" side of the same lookup family — worth remembering as a general selector-layer pattern: a model often gets a small family of get_x, get_x_by_y, and get_xs_by_ids functions, each suited to a different calling situation.
# 8. Small example
# python
# def get_users_by_ids(*, user_ids: Iterable[str]) -> QuerySet[User]:
#     return User.objects.filter(pk__in=user_ids)

# # caller decides what to do with it:
# active_count = get_users_by_ids(user_ids=[1, 2, 3]).filter(is_active=True).count()
# 9. What to remember
# Iterable[X] is a looser, more honest type hint than List[X] when a function only ever loops through its input once — accept the broadest type your function actually needs, not the narrowest one that happens to work.
# field__in=collection matches "any of these values" in a single query — reach for it whenever you'd otherwise be tempted to loop and query once per item.
# A Django QuerySet is lazy — it doesn't hit the database until something forces evaluation (iterating, list(), .first(), .count(), etc.). Recognizing which selector functions return a live Product/None versus an unexecuted QuerySet is a real, meaningful distinction, not just a documentation nicety.
# A missing return type hint isn't always a small cosmetic gap — sometimes, as here, correctly filling it in (QuerySet[Product]) would have actively taught you something true and important about how the function behaves, not just repeated something you could already guess.
# Reassigning a queryset back to the same variable after chaining a filter (qs = qs.filter(...)) is the same "read, transform, store back" pattern you've now seen with plain numbers (+=) and with query chains — recognizing that one underlying pattern across very different-looking code is a genuinely transferable reading skill.