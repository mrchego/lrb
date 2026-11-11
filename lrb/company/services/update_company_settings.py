from django.db import transaction

from lrb.company.models.settings import CompanySettings
from lrb.core.exceptions import ApplicationError, BusinessRuleViolationError, ErrorCode
from lrb.core.money.usage import company_has_money_data
from lrb.core.validators.currency_code import validate_currency_code
from lrb.core.validators.date_format import validate_date_format
from lrb.core.validators.timezone_name import validate_timezone_name


@transaction.atomic
def update_company_settings(
    *,
    company,
    timezone=None,
    currency=None,
    language=None,
    date_format=None,
    theme=None,
):
    settings = (
        CompanySettings.objects.select_for_update().filter(company=company).first()
    )
    if not settings:
        raise ApplicationError(
            message="Company settings not found.", code=ErrorCode.COMPANY_NOT_FOUND
        )

    if timezone is not None:
        settings.timezone = validate_timezone_name(value=timezone)
    if currency is not None:
        currency = validate_currency_code(value=currency)
        if currency != settings.currency and company_has_money_data(company=company):
            raise BusinessRuleViolationError(
                message="Currency can't change while the company has money data.",
                code=ErrorCode.BUSINESS_RULE,
            )
        settings.currency = currency

    if date_format is not None:
        settings.date_format = validate_date_format(value=date_format)

    if language is not None:
        settings.language = language

    if theme is not None:
        settings.theme = theme

    settings.save()
    return settings
