from typing import Iterable

from django.db import transaction

from lrb.core.services.bulk_result import BulkActionResult
from lrb.products.selectors.get_products_by_ids import get_products_by_ids


def bulk_activate_products(*, product_ids: Iterable[str], company_id: str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(pid) for pid in product_ids]
    products = list(get_products_by_ids(product_ids=normalized_ids, company_id=company_id))
    found_ids = {str(p.id) for p in products}

    for product in products:
        pid = str(product.id)

        if product.is_active:
            result.add_failure(item_id=pid, reason="Product already active")
            continue

        try:
            with transaction.atomic():
                product.is_active = True
                product.save(update_fields = ["is_active"])
            result.add_success(item_id=pid)
        except Exception as e:
            result.add_failure(item_id=pid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(item_id=missing, reason="Product not found in company")

    return result