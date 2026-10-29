from typing import Optional

from lrb.company.models.company import Company
from lrb.company.models.settings import CompanySettings
from lrb.core.exceptions import ApplicationError, ErrorCode


def get_company_settings(*, company) -> Optional[Company]:
    settings = CompanySettings.objects.filter(company=company).first()
    if not settings:
        raise ApplicationError(
            message="Company settings not found.",
            code=ErrorCode.COMPANY_NOT_FOUND,
        )
    return settings
