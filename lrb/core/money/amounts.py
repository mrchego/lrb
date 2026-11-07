"""Rounding and validation for money amounts. Pure functions, keyword-only."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from lrb.core.exceptions import AppValidationError
from lrb.core.money.currencies import (
    DEFAULT_CURRENCY,
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    get_currency,
)

_MAX_ABS = Decimal(10) ** (MONEY_MAX_DIGITS - MONEY_DECIMAL_PLACES)  # exclusive


def _decimals(currency: str) -> int:
    cur = get_currency(currency) or get_currency(DEFAULT_CURRENCY)
    return cur.decimals  # type: ignore[union-attr]


def quantize_money(amount: Decimal, *, currency: str) -> Decimal:
    """Round half-up to the currency's decimal places (2.675 USD -> 2.68).

    Python's float and banker's rounding would give 2.67 / 2.68 inconsistently;
    shops and tax authorities expect half-up.
    """
    exp = Decimal(1).scaleb(-_decimals(currency))
    return amount.quantize(exp, rounding=ROUND_HALF_UP)


def validate_money_amount(
    *,
    amount,
    currency: str,
    field: str = "amount",
    allow_negative: bool = False,
) -> Decimal:
    """Clean client input into an exact Decimal, or raise AppValidationError.

    Rejects what a plain `amount < 0` check lets through or crashes on:
    NaN and Infinity (comparing NaN raises InvalidOperation -> HTTP 500),
    absurdly large values, and more decimal places than the currency has
    (we refuse 10.555 USD instead of silently rounding someone's price).
    """
    try:
        value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise AppValidationError(message="Enter a valid amount.", field=field)

    if not value.is_finite():
        raise AppValidationError(message="Enter a valid amount.", field=field)
    if value < 0 and not allow_negative:
        raise AppValidationError(message="Amount cannot be negative.", field=field)
    if abs(value) >= _MAX_ABS:
        raise AppValidationError(message="Amount is too large.", field=field)

    allowed = _decimals(currency)
    fractional = max(0, -value.normalize().as_tuple().exponent)  # type: ignore[operator]
    if fractional > allowed:
        code = (currency or DEFAULT_CURRENCY).upper()
        places = "no decimal places" if allowed == 0 else f"at most {allowed} decimal place{'s' if allowed != 1 else ''}"
        raise AppValidationError(message=f"{code} allows {places}.", field=field)

    return quantize_money(value, currency=currency)


def to_minor_units(amount: Decimal, *, currency: str) -> int:
    """Decimal amount -> integer smallest unit (cents). For payment gateways."""
    return int(quantize_money(amount, currency=currency).scaleb(_decimals(currency)))


def from_minor_units(minor: int, *, currency: str) -> Decimal:
    return Decimal(minor).scaleb(-_decimals(currency))
