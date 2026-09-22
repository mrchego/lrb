from django.db import transaction

from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.products.models import Product


@transaction.atomic
def activate_product(*, product_id):
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise ApplicationError(message="Product not found.", code=ErrorCode.VALIDATION_ERROR)
    product.is_active = True
    product.save(update_fields=["is_active"])
    return product