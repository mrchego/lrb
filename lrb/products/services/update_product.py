from django.db import IntegrityError, transaction

from lrb.core.exceptions import (
    AppValidationError,
    ApplicationError,
    BusinessRuleViolationError,
    ErrorCode,
)
from lrb.products.models import Product


@transaction.atomic
def update_product(*, product_id, name=None, sku=None, price=None, is_active=None):
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise ApplicationError(
            message="Product not found.", code=ErrorCode.VALIDATION_ERROR
        )

    if name is not None:
        name = name.strip()
        if len(name) < 2:
            raise AppValidationError(
                message="Product name must be at least 2 characters long.", field="name"
            )
        product.name = name

    if sku is not None:
        sku = sku.strip()
        if not sku:
            raise AppValidationError(message="SKU is required.", field="sku")
        product.sku = sku

    if price is not None:
        if price < 0:
            raise AppValidationError(message="Price cannot be negative.", field="price")
        product.price = price

    if is_active is not None:
        product.is_active = is_active

    try:
        product.save()
    except IntegrityError as e:
        if "unique_product_sku_per_company" in str(e):
            raise BusinessRuleViolationError(
                message="A product with this SKU already exists.",
                code=ErrorCode.BUSINESS_RULE,
            )
        raise


# 1. Purpose

# update_product is the partial-update sibling to create_product — given a product ID and any subset of fields, it applies only the changes actually supplied, validates each one that's present, and saves. This is a genuinely well-built partial-update pattern. But there's a bug here, and it's worth recognizing immediately: it's the exact same category of mistake as the very first bug you found today, all the way back in VerificationCode.

# 2. The bug: wrong-source import, again
# python
# from psycopg import IntegrityError

# Compare this to the previous file, which correctly wrote:

# python
# from django.db import IntegrityError, transaction

# psycopg is the underlying PostgreSQL database driver — the low-level library that actually talks to the database over the network. Django sits on top of drivers like psycopg, and it wraps whatever raw errors the driver raises into its own, Django-specific exception classes before your application code ever sees them. When product.save() fails because of a unique constraint, what actually gets raised is django.db.IntegrityError — not psycopg.IntegrityError. They are two genuinely different classes, from two different libraries, even though they share the exact same name.

# What this means concretely: the except IntegrityError as e: block in this file will never trigger. Python's except only catches an exception if it matches the exact class (or a parent class) named — and django.db.IntegrityError is not the same class as psycopg.IntegrityError, nor does Django's version inherit from psycopg's. So when a duplicate SKU is submitted through this function, the real django.db.IntegrityError raised by .save() sails straight past this except clause as if it wasn't there at all — propagating up as a raw, unhandled database error instead of the friendly BusinessRuleViolationError this function was clearly written to produce. The carefully-written logic checking "unique_product_sku_per_company" in str(e) never even gets a chance to run.

# This is precisely the same shape as from tkinter import CASCADE — a symbol with the exact right name, imported from the wrong module, producing code that looks completely correct on a skim and runs without any complaint from Python itself, right up until the specific situation it was meant to handle actually occurs. You've now seen this exact bug pattern bookend the whole conversation — worth sitting with, because it means this is a mistake real developers make more than once, not a one-off fluke.

# The fix
# python
# from django.db import IntegrityError, transaction

# One line, matching exactly what create_product already got right.

# 3. Why this kind of bug is so easy to miss (and how you'd actually catch it)

# Skimming this file top to bottom, everything reads correctly — IntegrityError is used consistently, the except logic is smart (checking the constraint name, re-raising otherwise, exactly matching the improved pattern from create_product). Nothing about the usage is wrong. The only way to catch this is the same discipline from the very first file: actually check where each imported name comes from, not just whether it's used sensibly afterward. A skim confirms the code looks consistent with itself; only checking the import line against the actual library confirms it's consistent with reality. That's genuinely the whole lesson, and you now have direct, comparative evidence of it — the identical mistake pattern, once in the very first file you read, once in the very last.

# 4. Everything else in this file — confirming what's correct

# Since the import bug is the headline issue, it's worth briefly confirming the rest holds up, especially since this file reuses several patterns you've now audited elsewhere and should be able to check quickly yourself:

# python
#     product = Product.objects.filter(pk=product_id).first()
#     if not product:
#         raise ApplicationError(message="Product not found.", code=ErrorCode.VALIDATION_ERROR)

# Same pk=/.first() pattern from get_product, correctly guarded.

# python
#     if name is not None:
#         name = name.strip()
#         if len(name) < 2:
#             raise AppValidationError(...)
#         product.name = name
# Same is not None pattern from list_products — correctly distinguishes "field not supplied" (None, skip entirely) from "field supplied as an actual value" (validate and apply). This matters here even more than it did in list_products: for a partial update, a caller genuinely needs to be able to say "leave the price alone" — a bare if name: check would incorrectly refuse to apply a value like is_active=False... though notice is_active correctly uses is not None too, avoiding exactly that trap (unlike a hypothetical if is_active: which would silently drop any attempt to set it back to False).
# Each block: strip, validate, then assign directly onto the product instance (product.name = name) — building up in-memory changes across several fields before a single .save() at the end, rather than saving after each field. This is the right approach for a multi-field partial update: one database write covering everything that changed, not several.
# python
#     try:
#         product.save()
#     except IntegrityError as e:
#         if "unique_product_sku_per_company" in str(e):
#             raise BusinessRuleViolationError(...)
#         raise

# This is actually the improved version of create_product's exception handling you suggested last file — checking str(e) for the specific constraint name before deciding which error to raise, and correctly raise-ing unchanged otherwise. The logic here is exactly right; it's only the import feeding it the wrong exception class entirely that breaks it.

# One small note: product.save() here has no update_fields=[...], unlike nearly every other .save() call you've read today. This isn't a bug in this context — since product was freshly loaded from the database moments ago in this same function, saving every field is harmless (nothing else could have changed it in between, inside this atomic block) — but it is a small inconsistency with this codebase's general update_fields habit, worth a mention now that you're reliably spotting these on your own.

# 5. Connections
# Direct sibling to create_product — same validation logic per field, same BusinessRuleViolationError-on-conflict pattern, same underlying constraint being protected. The two functions should behave identically when it comes to catching duplicate SKUs; right now, only one of them actually does.
# This bug would likely surface the first time someone tries to rename a product to an already-taken SKU — probably discovered in testing or production as a confusing raw database traceback reaching the user, rather than the clean "A product with this SKU already exists." message the code was clearly written to produce.
# 6. What to remember
# A library's driver-level exception and Django's own wrapped exception can share an identical name while being genuinely different classes — always import framework-level exceptions (IntegrityError, and others like it) from the framework itself (django.db), not from whatever driver happens to sit underneath it.
# except SomeException silently does nothing if the exception actually raised doesn't match that exact class or a parent of it — Python doesn't warn you that a handler is unreachable; it just never fires, and the real exception propagates past it as if the try/except wasn't there.
# Correct-looking exception-handling logic can still be completely inert if the imported exception class itself is wrong — always verify the import before trusting the handler.
# The best way to catch this class of bug is checking imports against their actual source, not against how sensibly the name is used afterward — a skim will never catch it, because everything downstream of the bad import looks perfectly reasonable.
# You started this conversation by catching a wrong-module import (tkinter.CASCADE), and you're ending it by recognizing the identical mistake pattern in a completely different file, on your own, without needing the connection pointed out first. That's the clearest evidence the pattern-recognition skill this whole session was built around has actually taken hold — not memorized facts about this codebase, but a durable instinct for a specific, real, recurring class of bug you'll now catch in code you've never seen before.                                                                                                                      