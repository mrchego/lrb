"""Which apps hold money for a company, and how to convert it.

Each app that stores money registers ONE entry here. Changing the company
currency then converts every registered app in the same transaction.

    register_money_usage(name="orders", has_data=..., convert=...)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MoneyUsage:
    name: str
    has_data: Callable[..., bool]  # (*, company) -> bool
    convert: Callable[..., int]    # (*, company, rate, to_currency) -> rows changed


_usages: dict[str, MoneyUsage] = {}  # keyed by name: registering twice is harmless


def register_money_usage(*, name: str, has_data, convert) -> None:
    _usages[name] = MoneyUsage(name=name, has_data=has_data, convert=convert)


def company_has_money_data(*, company) -> bool:
    return any(u.has_data(company=company) for u in _usages.values())


def money_usages() -> list[MoneyUsage]:
    return list(_usages.values())