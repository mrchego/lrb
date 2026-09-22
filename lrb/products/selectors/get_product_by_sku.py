from typing import Optional

from lrb.products.models import Product


def get_product_by_sku(*, sku: str, company_id:str) -> Optional[Product]:
    return Product.objects.filter(sku=sku, company_id=company_id).first()

# 1. Purpose

# This is a selector — same category as get_user_by_email, get_active_session, get_current_user. Given a SKU and a company ID, it looks up a matching Product. This is a genuinely simple, correct file — the SKU/company combination is exactly what last file's UniqueConstraint(fields=["company", "sku"]) was built to guarantee is unambiguous: this lookup can never accidentally match more than one row.

# No bugs. Given how much ground you've covered today, this is a good one to move through quickly — confirming what you already know rather than teaching it fresh.

# 2. Signature
# python
# def get_product_by_sku(*, sku: str, company_id:str) -> Optional[Product]:

# Everything here is a pattern you've now seen repeatedly: * for keyword-only, type hints on both parameters (with the same missing-space cosmetic slip on company_id:str you've spotted a few times now), and -> Optional[Product] — correctly signaling "this might return nothing," matching what the body actually does.

# One thing worth naming since it's new: Product itself is the return type here — not dict, not a primitive. You're type-hinting a return value as an actual Django model class, the same way VerificationCode, User, and Product all work as types in their own right, not just as things you query.

# 3. Body
# python
#     return Product.objects.filter(sku=sku, company_id=company_id).first()
# .filter(sku=sku, company_id=company_id) — two conditions, both required (an implicit AND between keyword arguments in .filter(), same as you saw in verify_code's .filter(user=user, purpose=purpose, used_at__isnull=True)).
# company_id=company_id — worth noting explicitly: company is the actual field name on Product (company = models.ForeignKey(...)), but Django automatically also exposes company_id as the raw underlying column — the same relationship you learned about back on VerificationCode.user, where the field is user but the real database column is user_id. Filtering by company_id=... directly, rather than company=some_company_instance, is a small efficiency choice: it avoids ever needing to load a full Company object just to filter by its ID — you already have the ID as a string, so you hand it straight to the query.
# .first() — same method you saw in verify_code: runs the query, returns the first match or None if there are none, matching Optional[Product].

# Because sku and company_id together are protected by a unique constraint, .first() here is really more of a defensive habit than a strict necessity — there should never be more than one match — but it's the right, safe choice regardless (and correctly mirrors how verify_code used .first() for a case where duplicates genuinely could occur).

# 4. Connections
# Directly validates the design of the Product model's constraint you just read — this function is the natural reason that constraint exists: fast, unambiguous lookup by SKU within a company.
# Likely caller: a product GraphQL query (the sibling of SessionQuery), or an internal check before creating an order line item — "does this SKU actually exist for this company before we let someone order it?"
# 5. What to remember
# Filtering by <field>_id instead of <field>=<instance> avoids an unnecessary extra database fetch when you already have the ID and don't need the related object itself.
# A unique constraint at the model level often has a matching selector at the code level — designed together, so the guarantee the database enforces is exactly the guarantee the lookup relies on.
# Not every file you read will have a bug — recognizing a clean, correct file confidently is just as important a skill as catching a broken one. You should be able to look at this and know, quickly and surely, that it's fine — not out of habit, but because you actually checked the signature, the filter, and the return type against each other.