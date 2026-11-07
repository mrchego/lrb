"""Which apps hold money amounts for a company.

Amounts are stored as bare numbers, so changing the company currency would
silently relabel them (1,000 KES would become 1,000 USD, no conversion). Any
app that stores money registers a check here; while one says "yes", the
currency is locked.

Register from the app's AppConfig.ready():

    register_money_usage_check(lambda *, company: Invoice.objects.filter(company=company).exists())
"""
from __future__ import annotations

from typing import Callable

MoneyUsageCheck = Callable[..., bool]
_checks: list[MoneyUsageCheck] = []


def register_money_usage_check(check: MoneyUsageCheck) -> None:
    _checks.append(check)


def company_has_money_data(*, company) -> bool:
    return any(check(company=company) for check in _checks)
