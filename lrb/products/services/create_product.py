from django.db import IntegrityError, transaction

from lrb.core.exceptions import (
    AppValidationError,
    BusinessRuleViolationError,
    ErrorCode,
)
from lrb.products.models import Product


@transaction.atomic
def create_product(*, company, name, sku, price, is_active=True):
    name = name.strip()
    sku = sku.strip()
    if len(name) < 2:
        raise AppValidationError(
            message="Product name must be at least 2 characters long.", field="name"
        )

    if not sku:
        raise AppValidationError(message="SKU is required.", field="sku")

    if price < 0:
        raise AppValidationError(message="Price cannot be negative.", field="price")

    try:
        return Product.objects.create(
            company=company, name=name, sku=sku, price=price, is_active=is_active
        )
    except IntegrityError as e:
        if "unique_product_sku_per_company" in str(e):
            raise BusinessRuleViolationError(
                message="A product with this SKU already exists.",
                code=ErrorCode.BUSINESS_RULE,
            )
        raise


# 1. Purpose

# create_product is a write service — the first "create" service you've seen outside the identity/auth feature. It validates input, creates a Product, and specifically handles the case where creation fails because of the unique_product_sku_per_company constraint you read in the model file. This file brings back a concept you first met in verify_code: the race condition between "check if something exists" and "create it" — except this time, the developer handled it correctly, using a different technique than select_for_update(). That's the most valuable thing to understand here.

# 2. New import: IntegrityError
# python
# from django.db import IntegrityError, transaction

# IntegrityError is Django's exception for when the database itself rejects a write because it violates a constraint — a unique constraint, a foreign key pointing to a row that doesn't exist, a NOT NULL column left empty, and so on. This is distinct from AppValidationError/BusinessRuleViolationError, which are your own application-level checks written in Python, running before anything touches the database. IntegrityError is what happens when the database's own rules (the ones you saw defined directly on the Product model — the UniqueConstraint) get violated, regardless of what your Python code checked beforehand.

# 3. Signature
# python
# @transaction.atomic
# def create_product(*, company, name, sku, price, is_active=True):

# @transaction.atomic — correctly applied, single write. * forces every parameter to be keyword-only, matching every service you've read today. No type hints on any parameter — worth noting as the most type-hint-sparse signature you've seen yet (contrast against authenticate_credentials, which had email: str, password: str). This isn't just cosmetic here — it has a real consequence, covered in section 5.

# 4. Body — step by step
# python
#     name = name.strip()
#     sku = sku.strip()
# .strip() — a string method that removes leading/trailing whitespace. This is a genuinely good, easy-to-miss detail: it runs before any validation below, which means a submitted name of " " (just spaces) gets normalized to "" before the length check ever sees it — so len(name) < 2 correctly catches "effectively empty" input, not just "literally zero characters as submitted." Same reasoning for sku.
# Reassigning name = name.strip() (same variable name) rather than introducing cleaned_name = ... is the same "read, transform, store back under the same name" pattern you've now seen with += and with queryset chaining (qs = qs.filter(...)) — a third variation of the same underlying idea.
# python
#     if len(name) < 2:
#         raise AppValidationError(message="Product name must be at least 2 characters long.", field="name")
#     if not sku:
#         raise AppValidationError(message="SKU is required.", field="sku")
#     if price < 0:
#         raise AppValidationError(message="Price cannot be negative.", field="price")

# Three validation checks, each raising AppValidationError with a specific field= — you've seen this exact shape repeatedly today (_set_new_password, verify_code). Nothing new syntactically.

# python
#     try:
#         return Product.objects.create(
#             company=company, name=name, sku=sku, price=price, is_active=is_active
#         )
#     except IntegrityError:
#         raise BusinessRuleViolationError(
#             message="A product with this SKU already exists.",
#             code=ErrorCode.BUSINESS_RULE,
#         )
# Product.objects.create(...) — same create-and-save-in-one-step method you saw in generate_verification_code.
# try/except IntegrityError — this is the interesting part. Notice this function never calls something like get_product_by_sku(...) first to check "does this SKU already exist?" before attempting the create. Instead, it just attempts the create, and catches the database's own rejection if it fails.
# raise BusinessRuleViolationError(...) — a new exception class you haven't seen before, distinct from AppValidationError. The distinction is meaningful: AppValidationError is for "the input itself is malformed" (empty SKU, negative price) — something wrong with what was submitted, checkable without touching the database at all. BusinessRuleViolationError is for "the input is individually valid, but conflicts with existing data/business rules" (this exact SKU is already taken by this company) — something that can only be known by actually consulting the database. Different category of failure, different exception class — the same instinct behind separating AppValidationError from ApplicationError in the first place.
# 5. The real issue: catching IntegrityError too broadly

# This is the most important thing to understand in this file. except IntegrityError: catches any integrity violation from that .create() call — not specifically "the SKU constraint was violated." Look at what else could realistically cause an IntegrityError here:

# company could be an invalid or already-deleted company reference — a foreign key violation, not a SKU conflict.
# If price were None (remember: no type hint enforces it can't be), and the database column doesn't allow NULL — that's a NOT NULL violation, not a SKU conflict.
# Any other future constraint added to Product down the line would also funnel through this same except IntegrityError block.

# All of these would incorrectly be reported to the user as "A product with this SKU already exists." — a genuinely misleading error message for problems that have nothing to do with the SKU. This is a real design flaw: the exception handler is broader than the specific failure it's meant to describe.

# The more precise fix would check which constraint actually failed — Django's IntegrityError often carries enough detail in its message to distinguish this (or, more robustly, check for the conflict explicitly beforehand within the same transaction, or inspect e.__cause__/the database driver's error code):

# python
#     except IntegrityError as e:
#         if "unique_product_sku_per_company" in str(e):
#             raise BusinessRuleViolationError(
#                 message="A product with this SKU already exists.",
#                 code=ErrorCode.BUSINESS_RULE,
#             )
#         raise

# raise with no argument, inside an except block, re-raises the exact exception currently being handled — a way of saying "I checked, this isn't the specific case I know how to handle nicely, let it propagate as a genuine unexpected error" rather than mislabeling it.

# 6. But the overall pattern here — catch-after-attempt — is actually the correct one

# It's worth explicitly praising what this file gets right, especially since you now have the context to appreciate it: relying on the database's own unique constraint, and catching the resulting IntegrityError, is a more robust way to prevent duplicate SKUs than checking first and creating second — exactly the kind of race condition you identified as a real (if narrow) gap in verify_code. If this function instead did:

# python
# # The weaker, race-prone alternative:
# if get_product_by_sku(sku=sku, company_id=company.id):
#     raise BusinessRuleViolationError(...)
# return Product.objects.create(...)

# two near-simultaneous requests to create the same SKU could both pass the "does it exist?" check before either has actually created the row — the exact TOCTOU (time-of-check to time-of-use) race you learned about earlier. By instead just attempting the create and letting the database's own constraint be the final word, this function is safe against that race by construction — the database physically cannot allow two rows violating the same unique constraint to both commit, no matter how close together the two requests arrive. This is actually a cleaner solution to the same category of problem than select_for_update() would have been here, because there's no existing row to lock in advance — you're protecting against a duplicate being created, not protecting an existing row from concurrent modification.

# 7. Connections
# Directly enforces the constraint you read in the Product model file — this function is the reason that UniqueConstraint exists as a safety net here, catching what could otherwise slip through if validation were checked only in Python.
# Sibling to the selector layer you just finished (get_product, get_product_by_sku, list_products) — this is the "write" counterpart living in the same feature, following the exact service/selector split from your project's core architecture.
# 8. What to remember
# IntegrityError is the database's own rejection of a write — distinct from your application's own pre-database validation errors, and it can be triggered by any violated constraint, not just the one you're expecting.
# Catching an exception type and assuming it means one specific thing is a common, easy mistake — except IntegrityError here silently mislabels unrelated failures (a bad foreign key, a null field) as "duplicate SKU." Check which constraint actually failed before choosing the error message, when more than one constraint could plausibly trigger the same exception type.
# Attempt-then-catch is often a better way to prevent duplicates than check-then-create — it closes the exact race condition that a "check first" approach is vulnerable to, by letting the database's own atomic guarantee be the actual enforcement mechanism, rather than trying to coordinate it yourself in application code.
# raise with no argument inside an except block re-raises the current exception unchanged — the correct way to say "I looked, this isn't the specific case I handle, let it propagate."
# Missing type hints aren't always just a documentation gap — here, the absence of a price: Decimal (or similar) hint means nothing stops a caller from passing None, which would crash price < 0 with a TypeError before ever reaching the friendlier validation error you might expect.
