"""The currency table every app shares. Pure data + lookups, no database."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from lrb.core.money.currency_data import CURRENCY_ROWS

DEFAULT_CURRENCY = "KES"

# Storage shape for every money column (see lrb.core.models.fields.MoneyField).
# 3 decimal places is the most any currency in the table needs (KWD, BHD, ...).
MONEY_MAX_DIGITS = 14
MONEY_DECIMAL_PLACES = 3


@dataclass(frozen=True)
class Currency:
    code: str
    name: str
    decimals: int


@lru_cache(maxsize=1)
def _table() -> dict[str, Currency]:
    return {code: Currency(code, name, dec) for code, name, dec in CURRENCY_ROWS}


def get_currency(code: Optional[str]) -> Optional[Currency]:
    return _table().get((code or "").strip().upper())


def currency_choices() -> list[Currency]:
    return sorted(_table().values(), key=lambda c: c.code)
