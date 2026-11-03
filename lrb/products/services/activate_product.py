from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.products.selectors.get_product import get_product


@transaction.atomic
def activate_product(*, product_id: str, company_id: str):
    product = get_product(product_id=product_id, company_id=company_id, for_update=True)
    if not product:
        raise ApplicationError(
            message="Product not found.", code=ErrorCode.VALIDATION_ERROR
        )
    product.is_active = True
    product.save(update_fields=["is_active"])
    return product
