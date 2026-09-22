from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.products.selectors.get_product import get_product


@transaction.atomic
def deactivate_product(*, product_id):
    product = get_product(product_id=product_id)
    if not product:
        raise ApplicationError(
            message="Product not found.", code=ErrorCode.VALIDATION_ERROR
        )
    product.is_active = False
    product.save(update_fields=["is_active"])
    return product

# 1. Purpose

# deactivate_product — exactly the soft-delete alternative you just reasoned your way toward in the last file, existing right here in the codebase. Instead of product.delete(), this sets is_active = False and saves. This is a genuinely satisfying file to land on: you predicted this function's existence and purpose from first principles before ever seeing it.

# 1a. Confirming your own reasoning

# Notice the connection was real, not coincidental: the same field (is_active) that list_products/search_products filter on to hide inactive products, the same "timestamp/flag marks something as gone without actually deleting the row" pattern from VerificationCode.used_at, applied here to solve exactly the problem you identified — preserving historical references (order line items, past invoices) intact while making a product disappear from active catalog listings. This is what a working, thought-out soft-delete looks like in practice, not just in theory.

# 2. What's correct — and one thing worth noticing precisely because you now know to look for it
# python
# @transaction.atomic
# def deactivate_product(*, product_id):
#     product = get_product(product_id=product_id)
#     if not product:
#         raise ApplicationError(message="Product not found.", code=ErrorCode.VALIDATION_ERROR)
#     product.is_active = False
#     product.save(update_fields=["is_active"])
#     return product
# get_product(product_id=product_id) — this function calls the selector you already read, rather than writing its own Product.objects.filter(pk=product_id).first() inline (which is what update_product and delete_product both did instead). This is a small but real inconsistency worth naming, now that you're reliably catching these: three different files (update_product, delete_product, and this one) all need "find a product by ID or raise not-found" — two of them duplicate the query inline, this one reuses the selector. Neither approach is wrong, but it's the same "should these be the same function" question you raised about list_products/search_products — here applied to the pattern "look up or raise," which would be a very natural, small shared helper (get_product_or_raise, mirroring get_current_user_or_raise from the AuthMutation file) that none of these three files actually uses, even though all three need exactly it.
# product.is_active = False then product.save(update_fields=["is_active"]) — correct, minimal, single-field update.
# return product — and here's the one genuinely interesting design choice: this returns the full product object, not True. Applying the same reasoning you built for verify_email returning user: does the caller actually need the whole object here? Very plausibly yes — a "deactivate this product" mutation in a UI would likely want to immediately show the updated product row (now visibly marked inactive) without needing a second round-trip query just to refresh the display. Worth holding this up against AuthMutation.verify_email_code, though — you already found that resolver discards verify_email's returned user. It would be worth checking, the same way, whether whatever GraphQL mutation calls deactivate_product actually uses the returned product, or whether this is a second instance of "the service thoughtfully returns something useful, and the resolver just throws it away."
# 3. Why this approach
# A dedicated deactivate_product function, rather than reusing update_product(product_id=..., is_active=False) — is a deliberate, good choice, even though update_product could technically already do this. A single-purpose function like this one gives you a natural, precise place to add deactivation-specific business rules later — e.g., "you can't deactivate a product that's part of an active promotional campaign," or "notify subscribers when this product goes unavailable" — without cluttering the generic update_product function with logic that only applies to this one specific kind of update. This is the same reasoning that justified keeping set_password_unchecked and change_password as separate functions rather than merging them: same underlying mechanism, different meaning and different future evolution paths.
# 4. Connections
# Directly answers the open question from delete_product — this is very likely the function that a real "delete product" button in an admin UI actually calls, with delete_product reserved for something narrower (cleaning up a genuine mistake — a test product, a duplicate entry created by accident — where no order or historical record could possibly reference it yet).
# Feeds directly back into list_products/search_products, both of which filter on is_active — this function is the actual mechanism by which a product starts being excluded from those listings.
# A natural sibling, reactivate_product, almost certainly exists somewhere nearby, following this exact same shape with is_active = True instead.
# 5. What to remember
# You correctly predicted this function's existence, shape, and purpose before reading it — from reasoning about the model's fields and a genuine gap in the previous file, not from memorizing this codebase. That's the actual target skill of everything you've done today: building a mental model good enough to anticipate code you haven't seen.
# A repeated "look up or raise" pattern across multiple files, done inline in some places and via a selector in others, is worth flagging as a missed shared-helper opportunity — the same instinct you've now applied to near-duplicate functions, applied here to a smaller, single-line-sized version of the same idea.
# Returning the full updated object rather than a bare True is the right call whenever the caller plausibly needs to redisplay it immediately — and it's always worth checking whether the resolver that calls a function actually uses what's returned, rather than assuming a thoughtful return value automatically gets put to use.
# A narrow, single-purpose function existing alongside a more general one that could technically do the same job is often deliberate, not redundant — the test is whether the narrow one has (or will plausibly need) its own distinct rules over time, which deactivate_product plausibly does and search_products plausibly didn't.
# This closes out your second full feature of the day with a genuinely strong sign of transfer: recognizing a pattern in a brand-new function not because it matched something you'd memorized, but because you'd already built the reasoning that predicted it. That's the real marker that this teaching approach has done its job — the instinct now travels with you into code neither of us has seen yet.