from django.db import transaction, IntegrityError

from lrb.company.models.company import Company
from lrb.company.models.settings import CompanySettings
from lrb.core.exceptions import BusinessRuleViolationError, ErrorCode
from lrb.core.validators.phone import validate_phone_number
from lrb.core.validators.validate_company_email_unique import (
    validate_company_email_unique,
)
from lrb.core.validators.validate_company_name import validate_company_name


@transaction.atomic
def create_company(
    *, name, email, phone, country, city, address, logo_light=None, logo_dark=None
):
    # if Company.objects.exists():
    #     raise BusinessRuleViolationError(
    #         message="There can only be one company.",
    #         code=ErrorCode.COMPANY_ALREADY_EXISTS,
    #     )

    validate_company_name(value=name)
    validate_phone_number(phone)
    validate_company_email_unique(value=email)

    try:
        company = Company.objects.create(
            name=name,
            logo_light=logo_light,
            logo_dark=logo_dark,
            email=email,
            phone=phone,
            country=country,
            city=city,
            address=address,
            is_active=True,
        )
        CompanySettings.objects.create(company=company)
        return company
    except IntegrityError:
        raise BusinessRuleViolationError(
            message="A company with this email already exists.",
            code=ErrorCode.COMPANY_ALREADY_EXISTS,
        )
