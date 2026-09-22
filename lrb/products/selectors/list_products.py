from typing import Optional

from lrb.core.pagination import paginate_queryset
from lrb.products.models import Product


def list_products(
    *,
    company_id: str,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    qs = Product.objects.filter(company_id=company_id)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        from django.db.models import Q

        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    return paginate_queryset(qs.order_by("name"), limit=limit, offset=offset)

# 1. Purpose

# This is list_products — a search/filter/paginate selector, meaningfully more complex than anything you've read today. It builds a product listing for a company's storefront or admin panel: filter by active status, optionally search by name or SKU, then paginate the results. This is the kind of function that would sit behind a products(companyId, search, limit, offset) GraphQL query.

# This file introduces three genuinely new things: an import placed inside a function body, Django's Q objects for OR conditions, and a case-insensitive text search lookup. Let's take them one at a time.

# 2. Signature — five keyword-only parameters, three with defaults
# python
# def list_products(
#     *,
#     company_id: str,
#     is_active: Optional[bool] = None,
#     search: Optional[str] = None,
#     limit: Optional[int] = None,
#     offset: int = 0,
# ):
# company_id: str — required, no default. Every product listing has to belong to some company; there's no sensible "list all products everywhere" version of this function.
# is_active: Optional[bool] = None — optional. None here doesn't mean "false" — it means "no opinion, don't filter on this at all." This is an important, recurring three-state pattern worth naming explicitly: a plain bool can only be True or False, but Optional[bool] gives you a genuine third state — "not specified" — which is exactly what you need here, since "show me only active products," "show me only inactive products," and "show me everything regardless of status" are three meaningfully different requests, not two.
# search: Optional[str] = None — optional free-text search term; None/empty means no search filtering.
# limit: Optional[int] = None, offset: int = 0 — standard pagination parameters. limit (how many results to return) defaults to "no limit specified" (presumably paginate_queryset applies its own sensible default); offset (how many results to skip, for "page 2, 3, etc.") defaults to 0 — start from the beginning — and notably, offset is not Optional, just a plain int with a real default value, since "no offset" and "offset of zero" mean exactly the same thing, so there's no need for a separate None state the way there was for is_active.
# 3. Body — step by step
# python
#     qs = Product.objects.filter(company_id=company_id)

# Starting queryset — every product belonging to this company. Lazy, as you learned last file — no database hit yet.

# python
#     if is_active is not None:
#         qs = qs.filter(is_active=is_active)
# is is not None — the precise, explicit falsy-check you've seen recommended once before (in authenticate_credentials's discussion) but not actually used until now. Here it's not just stylistic — it's required for correctness. If this had been written as if is_active: instead, then a caller who explicitly asked for is_active=False (meaning: "show me only inactive products") would have that request silently ignored, because False itself is falsy — if is_active: would treat "show me inactive ones" identically to "no filter." is not None is the only check that correctly distinguishes all three real states: True (filter to active), False (filter to inactive), and None (don't filter at all). This is a great concrete example of why the falsy-check shortcut you've used comfortably all day (if not user:, if user:) isn't always the right tool — it depends entirely on whether False and "not provided" need to be treated differently.
# python
#     if search:
#         from django.db.models import Q

#         qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
# The import inside the function body — from django.db.models import Q sits inside if search:, not at the top of the file with the other imports. This is a deliberate technique called a local import, and it's done for a real reason here, not sloppiness: Q is only needed on this one line, reached only when a caller actually supplies a search term. Importing it locally means that cost (small as it is) is paid only when this specific branch actually runs, rather than on every single call to list_products, or even every time this module is loaded at all. This is a real, recognized Python pattern — used when an import is expensive, or (as is likely part of the reasoning here) to avoid a circular import between lrb.products.selectors and wherever else Q might indirectly connect back to. You won't need this often, but recognizing it as intentional — not a mistake — matters when you see it in real code.
# Q(...) — a Q object, Django's tool for building filter conditions that are more complex than simple "AND everything together" (which is all plain .filter(a=1, b=2) can express). Q(name__icontains=search) represents just the condition "name contains this search term" as a standalone, combinable object — not yet applied to anything.
# name__icontains=search — another double-underscore lookup: icontains means "insensitive contains" — a case-insensitive substring match. So Q(name__icontains="widget") matches "Blue Widget", "WIDGET Pro", and "widget-mini" all equally — capitalization doesn't matter. (Compare to plain contains, which would be case-sensitive and miss "WIDGET Pro".)
# | — the pipe operator, meaning OR, when used between two Q objects specifically (this is different from or, the plain Python boolean operator you used in handle_successful_login — | here is Q objects overriding what | means for their own type, a more advanced feature called operator overloading, worth knowing exists even without digging into how it's implemented). Q(name__icontains=search) | Q(sku__icontains=search) means: "match products where the name contains the search term, OR the SKU contains the search term" — either condition alone is enough for a row to match.
# Why is Q needed here at all, instead of just .filter(name__icontains=search, sku__icontains=search)? Because plain .filter(a=x, b=y) always means AND — "match a AND match b." There's no way to express OR using that keyword-argument shorthand alone. The moment you need "match this OR that," Q objects (and |) are the only way to build it.
# python
#     return paginate_queryset(qs.order_by("name"), limit=limit, offset=offset)
# .order_by("name") — applied last, right before handing off to pagination — makes sense: you want a stable, predictable order (alphabetical by name) before slicing out a particular page, otherwise "page 2" could show different or overlapping results each time depending on database internals.
# paginate_queryset(...) — your own project's helper (imported at the top), presumably applying limit/offset slicing to the queryset and probably returning some structured result (the page of results, plus maybe a total count or "has next page" flag — you'd need to open that file to know precisely).
# 4. Why this approach
# Optional[bool] for a filter flag, rather than plain bool, is the correct choice specifically because "don't filter" is a real, distinct, needed state — this is worth keeping as a rule of thumb: whenever a filter parameter needs a genuine "don't apply this filter at all" option, reach for Optional[bool] with an is not None check, not a plain bool.
# Building the queryset incrementally, one if block at a time, rather than one giant .filter(...) call with every condition crammed in, keeps each piece of filtering logic independently readable and independently optional — exactly mirroring the incremental if company_id: qs = qs.filter(...) pattern from get_products_by_ids, just extended to three conditions instead of one.
# Ordering applied last, right before pagination — a small but real correctness detail: pagination without a defined order is a subtle, easy-to-miss bug in many real codebases (databases don't guarantee row order without an explicit ORDER BY), so doing this in the right sequence here avoids that entirely.
# 5. Connections
# Directly builds on Product's model design — is_active is the exact field from the model file you read two files ago, and this selector is the reason that boolean field exists as a queryable flag rather than, say, a soft-delete timestamp.
# paginate_queryset is a shared, reusable utility — likely used by many other list_x selectors across the project (list_orders, list_users, etc.), the same way format_application_error was one shared translation helper used across every mutation in AuthMutation.
# Likely caller: a products GraphQL query, probably accepting a matching set of optional arguments (companyId, isActive, search, limit, offset) — you could now predict that query's signature confidently, having read both SessionQuery and this file.
# 6. Advanced concepts

# Local imports as a deliberate technique, not a mistake — how to tell the difference when reading unfamiliar code: the giveaway here is that Q is used on the very next line after being imported, inside a conditional branch that doesn't always run. If you ever see an import buried deep in a function for no apparent reason — used far from where it's imported, or in a branch that always runs anyway — that's more likely a genuine oversight or leftover from refactoring, not a deliberate choice. Here, the placement (immediately before its one and only use, inside a branch that's genuinely conditional) is a strong signal it's intentional.

# Q objects and the |/& operators generalize beyond just two conditions — you can chain Q(a=1) | Q(b=2) | Q(c=3) for "any of these three," or mix & (AND) and | (OR) with parentheses for real precedence, like (Q(a=1) | Q(b=2)) & Q(c=3). This function only needed the simplest two-way OR case, but it's worth knowing the same tool scales to much more complex conditions.

# 7. Small example
# python
# from django.db.models import Q

# def search_books(*, query: str):
#     return Book.objects.filter(Q(title__icontains=query) | Q(author__icontains=query))

# search_books(query="tolkien")  # matches books with "tolkien" in the title OR the author field
# 8. What to remember
# Optional[bool] with an is not None check is the correct pattern whenever a filter needs a genuine third "don't filter" state — a plain if flag: check would wrongly treat False the same as "not specified."
# Plain .filter(a=x, b=y) always means AND — use Q(...) | Q(...) whenever you need OR logic between separate conditions.
# field__icontains=value is a case-insensitive substring match — the right tool for free-text search boxes, as opposed to contains (case-sensitive) or exact/plain = (whole-value match).
# A local import (inside a function, not at the top of the file) is usually deliberate — check whether it's used immediately, in a branch that doesn't always run, before assuming it's a mistake.
# Order your queryset before paginating it — otherwise "page 2" isn't a reliable, stable concept, since databases don't guarantee consistent row ordering without an explicit ORDER BY.
