from django.db import transaction

from lrb.company.models.settings import CompanySettings
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.core.money.usage import company_has_money_data
from lrb.core.validators.appearance import validate_appearance
from lrb.core.validators.brand_color import validate_brand_color
from lrb.core.validators.currency_code import validate_currency_code
from lrb.core.validators.date_format import validate_date_format
from lrb.core.validators.timezone_name import validate_timezone_name
from lrb.company.models.currency_conversion import CurrencyConversion
from lrb.core.money.conversion import convert_company_money, validate_exchange_rate

@transaction.atomic
def update_company_settings(
    *,
    company,
    timezone=None,
    currency=None,
    exchange_rate=None,
    language=None,
    date_format=None,
    theme=None,
    brand_color=None,
    appearance=None, 
    actor=None,
):
    settings = CompanySettings.objects.select_for_update().filter(company=company).first()
    if not settings:
        raise ApplicationError(
            message="Company settings not found.", code=ErrorCode.COMPANY_NOT_FOUND
        )

    if timezone is not None:
        settings.timezone = validate_timezone_name(value=timezone)
    if currency is not None:
        new_currency = validate_currency_code(value=currency)
        old_currency = settings.currency
        if new_currency != old_currency:
            if company_has_money_data(company=company):
                rate = validate_exchange_rate(value=exchange_rate)
                changed = convert_company_money(company=company, rate=rate, to_currency=new_currency)
                CurrencyConversion.objects.create(
                    company=company, from_currency=old_currency, to_currency=new_currency,
                    rate=rate, rows_converted=changed,
                    converted_by_id=getattr(actor, "pk", None),
                    converted_by_email=getattr(actor, "email", ""),
                )
            settings.currency = new_currency

    if date_format is not None:
        settings.date_format = validate_date_format(value=date_format)

    if language is not None:
        settings.language = language

    if theme is not None:
        settings.theme = theme

    if brand_color is not None:
        settings.brand_color = validate_brand_color(value=brand_color)

    if appearance is not None:   # {} resets to the default look
        settings.appearance = validate_appearance(value=appearance)

    settings.save()
    return settings
