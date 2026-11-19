from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.db import DataError, transaction

from lrb.core.exceptions import AppValidationError
from lrb.core.money.amounts import quantize_money
from lrb.core.money.usage import money_usages

logger = logging.getLogger(__name__)

MAX_RATE = Decimal("1000000000")
RATE_DECIMALS = 12


def validate_exchange_rate(*, value, field: str = "exchange_rate") -> Decimal:
    """Units of the NEW currency that 1 unit of the OLD currency is worth (amount x rate)."""
    if value is None or value == "":
        raise AppValidationError(
            message="Enter the exchange rate to convert your existing amounts.", field=field
        )
    try:
        rate = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AppValidationError(message="Enter a valid exchange rate.", field=field)
    if not rate.is_finite() or rate <= 0 or rate > MAX_RATE:
        raise AppValidationError(message="Enter a valid exchange rate.", field=field)
    if -rate.normalize().as_tuple().exponent > RATE_DECIMALS:  # type: ignore[operator]
        raise AppValidationError(
            message=f"The rate can have at most {RATE_DECIMALS} decimal places.", field=field
        )
    return rate


def convert_amount(amount: Decimal, *, rate: Decimal, to_currency: str) -> Decimal:
    """Pure helper for one value (tests, non-SQL converters). Half-up, like quantize_money."""
    return quantize_money(amount * rate, currency=to_currency)


def convert_company_money(*, company, rate: Decimal, to_currency: str) -> dict[str, int]:
    """Convert every registered app's amounts. Must run inside a transaction."""
    changed: dict[str, int] = {}
    for usage in money_usages():
        try:
            with transaction.atomic():  # savepoint: an overflow must not poison the outer transaction
                changed[usage.name] = usage.convert(
                    company=company, rate=rate, to_currency=to_currency
                )
        except DataError:
            logger.warning("Currency conversion overflow in %s for company %s", usage.name, company.pk)
            raise AppValidationError(
                message=f"This rate makes some {usage.name} amounts too large to store. Check the rate.",
                field="exchange_rate",
            )
    return changed