from typing import Optional

from django.db.models import Q

from lrb.products.models import Product


def search_products(*, company_id: str, query: str, is_active: Optional[bool] = None):
    qs = Product.objects.filter(company_id=company_id)
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs.order_by("name")


# 1. Purpose

# A fourth product selector — search by company, free-text query, and active status, no pagination. Before going line by line, look at this side by side with list_products from the last file. That comparison is actually the most important thing to notice about this file.

# 2. Direct comparison with list_products
# python
# # list_products
# def list_products(*, company_id, is_active=None, search=None, limit=None, offset=0):
#     qs = Product.objects.filter(company_id=company_id)
#     if is_active is not None:
#         qs = qs.filter(is_active=is_active)
#     if search:
#         from django.db.models import Q
#         qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
#     return paginate_queryset(qs.order_by("name"), limit=limit, offset=offset)

# # search_products
# def search_products(*, company_id, query, is_active=None):
#     qs = Product.objects.filter(company_id=company_id)
#     if query:
#         qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
#     if is_active is not None:
#         qs = qs.filter(is_active=is_active)
#     return qs.order_by("name")

# These two functions do almost exactly the same thing. search_products is essentially list_products with the search parameter renamed to query, the pagination step removed, and the two if blocks written in a different order (which has no actual effect — filtering by is_active first vs. search first produces identical results either way, since .filter() calls combine with AND regardless of sequence).

# This is worth naming directly: this looks like duplicate, competing code, not two intentionally different tools. Compare this to get_product vs. get_product_by_sku from a few files ago — those were genuinely different lookup strategies (by ID vs. by SKU+company) that happened to share a model. Here, search_products doesn't do anything list_products can't already do — calling list_products(company_id=..., search=..., is_active=...) with no limit/offset produces the same filtered, ordered queryset this function does, just via a path that already exists.

# Why does this matter, practically? Two functions doing the same job invite exactly the kind of drift you've spent all day catching. If a bug fix or a new filter (say, min_price) gets added to one of these later, there's a real risk it only gets added to whichever one the developer happened to be looking at, leaving the other silently out of date and behaving differently for what should be the same underlying "search products" concept. This is the selector-layer version of the near-duplicate send_password_reset_code/send_email_verification_code files you found earlier — except there, the duplication was deliberate and defensible (two genuinely different purposes sharing similar mechanics). Here, it looks more like redundant code that should probably be one function, not two.

# 3. What's new here, syntax-wise

# Only one small thing: from django.db.models import Q is imported at the top of the file here, rather than locally inside the function as it was in list_products. Neither is wrong on its own — but now that you're comparing the two files directly, this is one more small inconsistency worth noticing: the same tool (Q), used the same way, imported two different ways in two sibling files. Not a bug, but exactly the kind of thing a consistency pass would catch and standardize.

# Everything else — is_active is not None, Q(...) | Q(...), name__icontains/sku__icontains, .order_by("name") — you already fully understand from the previous file.

# 4. The missing piece, and a real design question
# python
# def search_products(*, company_id: str, query: str, is_active: Optional[bool] = None):

# Same missing return type hint as get_products_by_ids — the honest hint would again be QuerySet[Product], for the same reason: this returns an unexecuted, lazy queryset, not a realized list.

# A genuine design question worth asking yourself, not just accepting either answer to: should list_products and search_products be merged into one function? A reasonable case exists either way:

# Merge them: one function, one place to maintain, list_products(company_id=..., search=..., is_active=...) already covers everything search_products does.
# Keep them separate: if search_products is meant to power something fundamentally different from a paginated listing page — say, a lightweight autocomplete/typeahead endpoint that needs to stay fast and simple, deliberately without pagination overhead — then a separate, narrower function might be the right call, the same way get_product and get_product_by_sku stayed separate for good reason.

# The way to actually answer this isn't to guess — it's to go find every caller of both functions and see whether they're genuinely serving different UI needs, or whether one of them is dead code / an earlier draft that never got cleaned up after list_products absorbed its functionality. This is a real, common situation in growing codebases, and "go check who actually calls this" is the correct next step, not a judgment call to make from the selector file alone.

# 5. Connections
# Same model, same constraint (unique_product_sku_per_company), same is_active field, same category comment ("products") from PERMISSION_REGISTRY — you're now seeing the Product feature from nearly every angle: the table, single lookups, batch lookups, paginated listing, and this search variant.
# Likely caller, if kept: an autocomplete/search-as-you-type frontend component, distinct from whatever paginated table list_products feeds.
# 6. What to remember
# When two functions look nearly identical, the question isn't "is either one wrong" — it's "should both exist at all." This is a different, higher-level kind of issue than anything you've caught today: not a bug in behavior, but a maintainability risk from unnecessary duplication.
# The order of independent .filter() calls doesn't affect the result — is_active first vs. search first here produce identical querysets, since filtering is commutative when every condition is combined with AND.
# The same tool imported differently in two sibling files (top-level here, local in the other) is a small but real consistency signal worth flagging once you're comparing files side by side, even though neither choice is wrong in isolation.
# Resolving "should these be merged" requires going to find the actual call sites, not just staring at the two function bodies — this is a good habit for real refactoring work: duplication is a hypothesis until you've confirmed both functions are actually serving genuinely different needs.
# You've now built a complete mental model of the Product feature's selector layer — and, fittingly, the last thing you found wasn't a crash or a security hole, but the subtler, very common real-world problem of two functions quietly competing to do the same job.