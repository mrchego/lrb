from django.db import models

from lrb.core.models.base import BaseModel


class Product(BaseModel):
    company = models.ForeignKey(
        "company.Company", on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "sku"], name="unique_product_sku_per_company"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"


# 1. Purpose

# This is a new model, Product, and it's a good one to compare against VerificationCode from your very first file today — same base structure (BaseModel, a Meta class), applied to a completely different domain. It represents a product belonging to a company, with a name, SKU, price, and active flag.

# There's a real, structural bug here — and it's not a typo in a name like tkinter.CASCADE was. It's a bug in indentation and nesting — a different category of mistake entirely, worth learning to spot on its own.

# 2. What's correct — including the very thing that was wrong last time
# python
#     company = models.ForeignKey(
#         "company.Company", on_delete=models.CASCADE, related_name="products"
#     )

# This time, on_delete=models.CASCADE is written correctly — models was imported properly at the top (from django.db import models), and CASCADE is accessed as models.CASCADE, the real Django function. No import shadowing, no wrong module. Good instinct to double-check this against the earlier bug, but this one's clean.

# python
#     name = models.CharField(max_length=255)
#     sku = models.CharField(max_length=100)
#     price = models.DecimalField(max_digits=12, decimal_places=2)
#     is_active = models.BooleanField(default=True)
# name, sku — CharFields you already fully understand from VerificationCode.
# price = models.DecimalField(max_digits=12, decimal_places=2) — new field type, worth explaining: DecimalField stores exact decimal numbers, as opposed to Python's float, which uses binary floating-point and can introduce tiny rounding errors (0.1 + 0.2 famously doesn't equal 0.3 exactly in floating-point math). For money, that imprecision is unacceptable — a price needs to be exactly $19.99, not $19.989999999998. max_digits=12 is the total number of digits allowed (before and after the decimal point combined); decimal_places=2 says exactly 2 of those digits go after the decimal point — so this field can hold values up to 9,999,999,999.99.
# is_active = models.BooleanField(default=True) — a true/false field. default=True means: if you create a Product without explicitly setting is_active, Django fills it in as True automatically. This is a new pattern you haven't seen a field-level default on before today (contrast with used_at = models.DateTimeField(null=True, blank=True), which had no default value, just permission to be empty) — default= supplies an actual starting value; null=True/blank=True just permit emptiness. Different tools for different needs.
# python
#     class Meta:
#         ordering = ["name"]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["company", "sku"], name="unique_product_sku_per_company"
#             )
#         ]
# ordering = ["name"] — same pattern as VerificationCode's ordering = ["-created_at"], just no - prefix here, meaning ascending order (A→Z) instead of descending.
# models.UniqueConstraint(fields=[...], name=...) — a new concept: a database-level rule that no two rows can have the same combination of values across the listed fields. fields=["company", "sku"] means: two different companies can both have a product with SKU "ABC123" — but the same company can never have two products sharing that SKU. This is enforced by the actual database, not just application code — meaning even a rogue script or a bug elsewhere that skips your Python validation still can't create a duplicate; the database itself will reject the second row.
# name="unique_product_sku_per_company" — a human-readable identifier for this specific constraint, which Django uses in error messages and migration files. Naming constraints explicitly (rather than letting Django auto-generate a name) makes database errors and migration history much easier to read later.
# 3. The bug: __str__ is nested inside Meta, not inside Product
# python
#         constraints = [
#             models.UniqueConstraint(...)
#         ]

#         def __str__(self):
#             return f"{self.name} ({self.sku})"

# Look at the indentation carefully. def __str__(self): is indented at the same level as ordering and constraints — meaning it's defined inside class Meta:, not inside class Product(BaseModel):. Compare this to VerificationCode, where __str__ sat at the outer indentation level, as a direct sibling of the field definitions and the Meta class itself — not nested inside Meta.

# What actually happens because of this: Python doesn't error out — this is syntactically valid Python. Meta becomes a class that just happens to also have a method called __str__ defined on it, which nothing will ever call the normal way. Meanwhile, Product itself has no __str__ method at all — Django's default Model.__str__ kicks in instead, which typically prints something unhelpful like Product object (17) (the class name and primary key) anywhere a Product is displayed — in Django admin lists, in print(some_product), in shell debugging, in error messages. The intended readable output — "Widget (SKU123)" — never actually shows up anywhere.

# This is a silent, "everything still runs" bug — very different from the crashes you found earlier. Nothing here throws an exception or fails a migration. It just quietly doesn't do what it was clearly meant to do. This is arguably a harder category of bug to catch than a TypeError, precisely because the code runs without complaint.

# The fix — move __str__ out to the correct indentation level
# python
# class Product(BaseModel):
#     company = models.ForeignKey(
#         "company.Company", on_delete=models.CASCADE, related_name="products"
#     )
#     name = models.CharField(max_length=255)
#     sku = models.CharField(max_length=100)
#     price = models.DecimalField(max_digits=12, decimal_places=2)
#     is_active = models.BooleanField(default=True)

#     class Meta:
#         ordering = ["name"]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["company", "sku"], name="unique_product_sku_per_company"
#             )
#         ]

#     def __str__(self):
#         return f"{self.name} ({self.sku})"

# Notice: def __str__(self): now lines up with company =, name =, and class Meta: — all siblings, all direct members of Product, none of them nested inside another.

# 4. Why this class of bug is worth training your eye for specifically

# You've now seen two categories of "looks right but isn't" bugs today:

# Wrong reference, right-looking name — from tkinter import CASCADE (right word, wrong source).
# Wrong nesting level, right-looking indentation — __str__ under Meta instead of under Product.

# Both are invisible if you're only skimming for keywords rather than actually tracing structure. The second category — indentation/nesting mistakes — is actually Python-specific in a meaningful way: in many other languages, curly braces {} make nesting visually unambiguous even if indentation is sloppy; in Python, indentation is the nesting — there's no redundant visual signal to catch a mistake like this at a glance. This is exactly why, when reading Python class bodies, it pays to explicitly ask "what indentation level is this line at, and what does that make it a member of?" rather than just reading top-to-bottom and assuming a method belongs to whatever class started the file.

# 5. Connections
# Django admin: this is the most common place this bug would actually be noticed by a developer — opening the Django admin's product list and seeing a column full of Product object (1), Product object (2), instead of readable names, is the classic symptom of a missing or misplaced __str__.
# Debugging/logging: anywhere a Product gets printed or logged (error messages, shell sessions, Celery task logs) would show the unhelpful default instead of the intended readable string.
# Compare directly against VerificationCode, which got this right — a good instinct going forward: when you see a new model, briefly check its __str__'s indentation against a model you already know is correct, rather than assuming it's fine just because the method exists somewhere in the file.
# 6. What to remember
# A method's indentation level is its class membership in Python — there's no other signal. A method indented one level too deep silently becomes part of the wrong class instead of raising an error.
# Meta classes hold configuration, not behavior — if you ever see a def inside a class Meta: block, that's almost always a misplaced method, not intentional Meta behavior.
# DecimalField, not FloatField, for money — exact decimal storage avoids the rounding errors inherent to binary floating-point.
# UniqueConstraint(fields=[...]) enforces a combination uniqueness rule at the database level — stronger and more reliable than checking for duplicates in application code alone, since it can't be bypassed by a bug elsewhere.
# Not every bug crashes — some just silently fail to do what they were clearly meant to do. These are often harder to catch than a TypeError, precisely because nothing complains — which makes deliberately checking structure (not just running the code and seeing if it errors) a genuinely necessary reading skill, not an optional extra step.