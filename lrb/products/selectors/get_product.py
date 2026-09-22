from typing import Optional

from lrb.products.models import Product


def get_product(*, product_id: str) -> Optional[Product]:
    return Product.objects.filter(pk=product_id).first()

# 1. Purpose

# A second, near-identical selector — look up a single Product, this time by its own ID rather than by SKU+company. Same category as the last file: a clean, correct lookup function. Since you've now seen this exact shape several times, I'll go through it briefly and spend more time on the one detail that's actually new: pk.

# 2. Signature and body — what's familiar
# python
# def get_product(*, product_id: str) -> Optional[Product]:
#     return Product.objects.filter(pk=product_id).first()

# * for keyword-only, product_id: str type-hinted correctly (space included, this time), -> Optional[Product] matching a .filter().first() that can legitimately return None. All patterns you already know cold.

# 3. The new detail: pk
# python
#     return Product.objects.filter(pk=product_id).first()

# pk stands for primary key — it's a special, built-in Django shortcut that always refers to whatever field is actually configured as a model's primary key, regardless of what that field is literally named. If Product's primary key column is called id (the default, likely inherited from BaseModel — remember, that's where created_at came from too), pk=product_id and id=product_id would do the exact same thing here.

# Why use pk instead of just writing id=product_id directly? Because pk is name-independent — it works no matter what the actual primary key field is called. If BaseModel (or some future model) ever used a differently-named primary key — say, uuid, or something project-specific — code written with pk= keeps working unchanged, while code written with id= would silently stop matching anything (Django wouldn't error; it would just create a new, unrelated field called id to filter against, or fail if no such field exists at all). Using pk is a small piece of future-proofing: this selector doesn't need to know or care what the primary key is actually named, only that every model has one, and pk always finds it.

# 4. Comparing this file to the last one

# Put side by side:

# python
# def get_product_by_sku(*, sku: str, company_id: str) -> Optional[Product]:
#     return Product.objects.filter(sku=sku, company_id=company_id).first()

# def get_product(*, product_id: str) -> Optional[Product]:
#     return Product.objects.filter(pk=product_id).first()

# Two different lookup strategies for the same model, living as two separate, narrowly-named functions rather than one combined get_product(*, sku=None, company_id=None, product_id=None) that branches internally. This is a design choice worth naming explicitly, since it's a pattern you'll see constantly in well-organized selector layers: prefer several small, precisely-named functions over one flexible function with optional parameters and internal branching. The benefit: every caller's intent is obvious from the function name alone (get_product vs get_product_by_sku), there's no risk of a caller accidentally passing the wrong combination of optional arguments, and each function stays trivially simple to read — exactly what you're looking at here.

# 5. Connections
# get_product (by ID) is the far more common lookup pattern you'd expect — anywhere a GraphQL query receives a productId argument (the most natural way a frontend would reference "this specific product" after an initial list/search), this is the function it calls. get_product_by_sku is more specialized — useful specifically when an external system (an order import, a barcode scanner integration) only has a SKU to work with, not an internal database ID.
# Sibling to get_user_by_email, get_current_user — same selector shape, same file-per-lookup-strategy pattern, just applied to a different model.
# 6. What to remember
# pk= is Django's name-independent way to filter by whatever field is actually the primary key — prefer it over id= unless you specifically need to reference the id field by that exact name for some other reason.
# When a model needs to be looked up multiple distinct ways, prefer separate, clearly-named selector functions over one function with several optional parameters — clarity at the call site beats flexibility inside the function.
# Reading two similar files back to back is a fast way to notice what's actually different between them — here, the interesting difference wasn't a bug, it was a legitimate, well-reasoned design choice (pk vs named fields) worth understanding on its own terms.