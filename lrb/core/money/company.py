from __future__ import annotations

import logging

from lrb.core.money.currencies import DEFAULT_CURRENCY, Currency, get_currency

logger = logging.getLogger(__name__)


def get_company_currency(*, company_id) -> Currency:
    """The company's currency, read fresh from the database.

    Fails safe like the timezone lookup: a missing row or unknown code logs an
    error and falls back to the default instead of breaking the request.
    """
    from lrb.company.models.settings import CompanySettings  # lazy: avoid import cycle

    code = (
        CompanySettings.objects.filter(company_id=company_id)
        .values_list("currency", flat=True)
        .first()
    )
    currency = get_currency(code)
    if currency is None:
        logger.error("Unknown currency %r for company %s; using default", code, company_id)
        currency = get_currency(DEFAULT_CURRENCY)
    return currency  # type: ignore[return-value]
