"""Pure unit tests: no database."""
from decimal import Decimal

import pytest

from lrb.core.exceptions import AppValidationError
from lrb.core.money import (
    DEFAULT_CURRENCY, currency_choices, from_minor_units, get_currency,
    quantize_money, to_minor_units, validate_money_amount,
)
from lrb.core.money.currencies import MONEY_DECIMAL_PLACES
from lrb.core.money.usage import _checks, company_has_money_data, register_money_usage_check
from lrb.core.validators.currency_code import validate_currency_code


def test_default_currency_exists():
    assert get_currency(DEFAULT_CURRENCY).decimals == 2


@pytest.mark.parametrize("code,decimals", [
    ("KES", 2), ("USD", 2), ("EUR", 2), ("GBP", 2), ("NGN", 2),
    ("JPY", 0), ("UGX", 0), ("RWF", 0), ("XOF", 0), ("KWD", 3), ("BHD", 3),
    ("COP", 2), ("HUF", 2),
])
def test_known_decimals(code, decimals):
    assert get_currency(code).decimals == decimals


def test_withdrawn_and_special_codes_are_absent():
    for code in ["BGN", "HRK", "ZWL", "SLL", "XAU", "XDR", "XTS", "XXX", "CLF"]:
        assert get_currency(code) is None


def test_table_invariants():
    rows = currency_choices()
    assert len(rows) > 140
    assert len({c.code for c in rows}) == len(rows)
    assert all(len(c.code) == 3 and c.code.isupper() and c.name for c in rows)
    assert max(c.decimals for c in rows) <= MONEY_DECIMAL_PLACES  # storage can hold them all


def test_lookup_is_case_and_space_insensitive():
    assert get_currency(" kes ").code == "KES"
    assert get_currency(None) is None


def test_validate_currency_code():
    assert validate_currency_code(value="usd") == "USD"
    for bad in ["", "ABC", "KE", "US$", "XXX"]:
        with pytest.raises(AppValidationError):
            validate_currency_code(value=bad)


def test_half_up_rounding_not_float_or_bankers():
    assert quantize_money(Decimal("2.675"), currency="USD") == Decimal("2.68")
    assert quantize_money(Decimal("2.665"), currency="USD") == Decimal("2.67")
    assert quantize_money(Decimal("0.5"), currency="JPY") == Decimal("1")


@pytest.mark.parametrize("raw,cur,expected", [
    ("10.5", "KES", "10.50"), ("10", "KES", "10.00"), (Decimal("10.50"), "USD", "10.50"),
    ("1000", "JPY", "1000"), ("1.234", "KWD", "1.234"), (5, "KES", "5.00"),
    ("1E+2", "KES", "100.00"), ("99999999999.99", "USD", "99999999999.99"),
])
def test_valid_amounts(raw, cur, expected):
    assert validate_money_amount(amount=raw, currency=cur) == Decimal(expected)


@pytest.mark.parametrize("raw,cur", [
    ("NaN", "KES"), ("Infinity", "KES"), ("-Infinity", "KES"), ("abc", "KES"),
    ("", "KES"), (None, "KES"), ("-0.01", "KES"),
    ("10.555", "USD"), ("10.5", "JPY"), ("1.2345", "KWD"),
    ("100000000000.00", "USD"), ("100000000000", "KES"),
])
def test_invalid_amounts(raw, cur):
    with pytest.raises(AppValidationError):
        validate_money_amount(amount=raw, currency=cur)


def test_negative_allowed_when_asked():
    assert validate_money_amount(amount="-5", currency="KES", allow_negative=True) == Decimal("-5.00")


def test_error_message_names_the_currency_rule():
    with pytest.raises(AppValidationError) as e:
        validate_money_amount(amount="10.5", currency="JPY", field="price")
    assert "JPY" in e.value.message and e.value.field == "price"


def test_minor_units_round_trip():
    assert to_minor_units(Decimal("12.34"), currency="KES") == 1234
    assert to_minor_units(Decimal("500"), currency="JPY") == 500
    assert to_minor_units(Decimal("1.234"), currency="KWD") == 1234
    assert from_minor_units(1234, currency="KES") == Decimal("12.34")
    assert from_minor_units(500, currency="JPY") == Decimal("500")


def test_usage_registry():
    before = list(_checks)
    try:
        _checks.clear()
        assert company_has_money_data(company=object()) is False
        register_money_usage_check(lambda *, company: False)
        assert company_has_money_data(company=object()) is False
        register_money_usage_check(lambda *, company: True)
        assert company_has_money_data(company=object()) is True
    finally:
        _checks[:] = before
