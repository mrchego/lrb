from lrb.core.exceptions import AppValidationError
from lrb.core.money.currencies import get_currency


def validate_currency_code(*, value: str) -> str:
    currency = get_currency(value)
    if currency is None:
        raise AppValidationError(
            message="Choose a valid currency, e.g. KES.", field="currency"
        )
    return currency.code
