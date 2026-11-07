from django.db import models

from lrb.core.money.currencies import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS


def MoneyField(**kwargs) -> models.DecimalField:
    """The one way to declare a money column: price = MoneyField().

    A factory, not a subclass, so migrations just see a plain DecimalField.
    The scale is 3 so every currency fits; which decimals are *allowed* is
    enforced per currency by validate_money_amount().
    """
    return models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, **kwargs
    )
