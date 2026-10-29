from django.db import transaction

from lrb.company.models.settings import CompanySettings
from lrb.core.exceptions import ApplicationError, ErrorCode


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
    settings = CompanySettings.objects.filter(company=company).first()
    if not settings:
        raise ApplicationError(
            message="Company settings not found.", code=ErrorCode.COMPANY_NOT_FOUND
        )

    if timezone is not None:
        settings.timezone = timezone

    if currency is not None:
        settings.currency = currency

    if language is not None:
        settings.language = language

    if date_format is not None:
        settings.date_format = date_format

    if theme is not None:
        settings.theme = theme

    settings.save()
    return settings
