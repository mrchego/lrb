from __future__ import annotations

import logging

from lrb.core.money.currencies import DEFAULT_CURRENCY, Currency, get_currency

logger = logging.getLogger(__name__)


def get_company_currency(*, company_id, lock: bool = False) -> Currency:
    """...
    lock=True takes a row lock on the settings row until the caller's transaction ends,
    so a currency change can't slip in between validating an amount and saving it.
    Only use it inside transaction.atomic.
    """
    from lrb.company.models.settings import CompanySettings

    qs = CompanySettings.objects.filter(company_id=company_id)
    if lock:
        qs = qs.select_for_update()
    code = qs.values_list("currency", flat=True).first()
    currency = get_currency(code)
    if currency is None:
        logger.error("Unknown currency %r for company %s; using default", code, company_id)
        currency = get_currency(DEFAULT_CURRENCY)
    return currency  # type: ignore[return-value]
