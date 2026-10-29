from django.db import transaction, IntegrityError
from lrb.company.models.company import Company
from lrb.core.exceptions import ApplicationError, BusinessRuleViolationError, ErrorCode
from lrb.core.validators.phone import validate_phone_number
from lrb.core.validators.validate_company_email_unique import (
    validate_company_email_unique,
)
from lrb.core.validators.email import validate_email
from lrb.core.validators.validate_company_name import validate_company_name


@transaction.atomic
def update_company(
    *,
    company_id,
    name=None,
    logo_light=None,
    logo_dark=None,
    email=None,
    phone=None,
    country=None,
    city=None,
    address=None,
    is_active=None,
):
    company = Company.objects.filter(pk=company_id).first()
    if not company:
        raise ApplicationError(
            message="Company not found.", code=ErrorCode.COMPANY_NOT_FOUND
        )

    if name is not None:
        validate_company_name(value=name)
        company.name = name

    if email is not None:
        validate_email(email)
        validate_company_email_unique(value=email, instance=company)
        company.email = email

    if phone is not None:
        validate_phone_number(phone)
        company.phone = phone

    if country is not None:
        company.country = country

    if city is not None:
        company.city = city

    if address is not None:
        company.address = address

    if logo_light is not None:
        company.logo_light = logo_light

    if logo_dark is not None:
        company.logo_dark = logo_dark

    if is_active is not None:
        company.is_active = is_active

    try:
        company.save()
    except IntegrityError:
        raise BusinessRuleViolationError(
            message="A company with this email already exists.",
            code=ErrorCode.COMPANY_ALREADY_EXISTS,
        )
    return company
