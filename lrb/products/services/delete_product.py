from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.products.models import Product


@transaction.atomic
def delete_product(*, product_id):
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise ApplicationError(message="Product not found.", code=ErrorCode.VALIDATION_ERROR)
    product.delete()
    return True

# 1. Purpose

# delete_product — the last of the four basic write operations on Product (create, update, and now delete — you'll likely never see a get-as-a-write, since reads live in the selector layer). Given a product ID, find it, delete it, confirm success. This is a short, simple file, and it's a good one to close on: by now you should be able to verify most of it yourself at a glance. I'll walk it quickly, then focus on the one real question worth asking about any delete function.

# 2. What's correct — quick confirmation
# python
# @transaction.atomic
# def delete_product(*, product_id):
#     product = Product.objects.filter(pk=product_id).first()
#     if not product:
#         raise ApplicationError(message="Product not found.", code=ErrorCode.VALIDATION_ERROR)
#     product.delete()
#     return True
# @transaction.atomic — correctly applied to a write. (Arguably the least necessary use of it you've seen all day, since this function only performs one single write operation — but it's harmless and consistent with the project-wide rule, so not worth objecting to.)
# Product.objects.filter(pk=product_id).first() — the exact get_product pattern, correctly guarded with if not product: before attempting to use it.
# raise ApplicationError(message=..., code=ErrorCode.VALIDATION_ERROR) — matches update_product's "not found" handling exactly, keyword arguments correct, no import-source bugs this time (no psycopg mistake repeated here).
# product.delete() — Django's built-in method for removing a model instance's row from the database.
# return True — the familiar plain-success-signal pattern, appropriate here since there's nothing left to return once the row no longer exists.

# No bugs. This file is clean.

# 3. The one real question worth asking about any delete: what happens to related data?

# This is the genuinely interesting thing to think about here, and it connects directly back to the very first file you read today. Go back to VerificationCode:

# python
# user = models.ForeignKey("accounts.User", on_delete=CASCADE, related_name="verification_codes")

# You learned on_delete=CASCADE means: "if the related User is deleted, delete this row too." The exact same mechanism governs what happens when product.delete() runs here — except now you need to think about it from the other direction. Product is the "one" side of relationships that other models point to — an OrderLineItem, a CartItem, an InventoryRecord, whatever else in this project has a ForeignKey("products.Product", on_delete=...).

# Whatever on_delete behavior those other models chose determines what actually happens when this function runs — and it's invisible from reading delete_product alone:

# If some OrderLineItem.product field uses on_delete=models.CASCADE, calling delete_product on a product that's part of a past order would silently delete that order's line item too — potentially corrupting historical order records, invoices, or reports that should remain accurate forever, even after a product is discontinued.
# If instead it uses on_delete=models.PROTECT, Django would refuse the delete entirely, raising a ProtectedError the moment product.delete() runs — and this function doesn't catch or handle that at all, meaning a legitimate "I discontinued this product" action would crash with an unhandled, unfriendly exception instead of a clean ApplicationError.
# If it uses on_delete=models.SET_NULL, old order line items would keep existing but silently lose their connection to which product they were for.

# This is exactly why real, production-grade product catalogs almost always prefer a soft delete over a real one — instead of product.delete(), setting a field like product.is_active = False (which, conveniently, this model already has!) or a dedicated deleted_at timestamp (the exact same "timestamp-as-flag" pattern you learned from VerificationCode.used_at on day one of this conversation). A soft delete keeps the row, and every historical reference to it, intact — while still making it disappear from active listings (recall list_products already filters on is_active). A hard delete, like this function performs, is riskier for exactly the reason above: its safety depends entirely on on_delete choices made in other files, which this function's author may not have been thinking about at all when writing this one.

# This isn't something you can call a definite bug from this file alone — you'd need to go check every model with a ForeignKey pointing at Product to know whether this is actually dangerous in this specific codebase, or genuinely fine (maybe products can only ever be deleted before any order references them, enforced elsewhere). But it's exactly the right question to be asking by this point in your reading — the same instinct as checking whether AppValidationError really is a subclass of ApplicationError before trusting AuthMutation's blanket except clause: a function can be completely correct in isolation, and its real safety still depends entirely on decisions made in files you haven't looked at yet.

# 4. Connections
# Directly reopens the very first concept from your very first file today — on_delete=CASCADE — except now you're seeing it from the deleting side instead of the deleted side, a genuinely useful full-circle moment for understanding what that one parameter actually controls across a whole schema.
# is_active (from the Product model, used throughout list_products/search_products) is the natural foundation for a soft-delete alternative to this function, if one doesn't already exist elsewhere in this codebase.
# 5. What to remember
# A delete function's real behavior isn't fully determined by its own code — it depends on every other model's on_delete choice for foreign keys pointing at the thing being deleted. Reading the delete function alone never tells you the whole story.
# CASCADE, PROTECT, and SET_NULL each produce a completely different, sometimes surprising outcome when a referenced row is deleted — and only one of them (PROTECT) would even cause this specific function to fail loudly rather than silently doing something the caller may not have intended.
# Soft deletes (a boolean flag or a deleted_at timestamp) are usually the safer default for anything that might be referenced by historical records — hard deletes are appropriate mainly for data with no meaningful history to preserve.
# Recognizing "this file is correct, but I can't fully evaluate its safety without checking related files" is itself an advanced, valuable reading skill — not every question a good reviewer asks can be answered by the file in front of them, and knowing which questions require going elsewhere is as important as answering the ones you can.
# You've now read this entire Product feature — model, four selectors, and three write services — cover to cover, on top of the full authentication feature earlier. Two complete, real, differently-shaped features in one session, and by this final file, you were already independently spotting the recurring bug pattern before I needed to name it. That's the actual outcome this whole format was aiming for.