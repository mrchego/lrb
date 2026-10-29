from typing import Optional

from lrb.company.models.company import Company
from lrb.core.exceptions import ApplicationError, ErrorCode


def get_company(*, company_id: str) -> Optional[Company]:
    company = Company.objects.filter(pk=company_id).first()
    if not company:
        raise ApplicationError(
            message="No company has been registered yet.",
            code=ErrorCode.COMPANY_NOT_FOUND,
        )
    return company
