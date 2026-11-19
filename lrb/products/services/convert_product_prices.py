from django.db.models import DecimalField, F, Value
from django.db.models.functions import Now, Round

from lrb.core.money.currencies import get_currency
from lrb.products.models import Product


def convert_product_prices(*, company, rate, to_currency) -> int:
    decimals = get_currency(to_currency).decimals  # already validated by the caller
    factor = Value(rate, output_field=DecimalField(max_digits=30, decimal_places=12))
    # One UPDATE, exact numeric math in Postgres. ROUND is half-away-from-zero, which equals
    # the half-up of quantize_money for non-negative prices. update() skips auto_now, hence Now().
    return Product.objects.filter(company=company).update(
        price=Round(F("price") * factor, decimals),
        updated_at=Now(),
    )