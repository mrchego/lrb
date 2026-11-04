import io

from django.conf import settings
from django.core.management import call_command
from django_tenants.utils import tenant_context
from django.db import transaction, IntegrityError
from lrb.company.models.company import Company
from lrb.company.models.settings import CompanySettings
from lrb.company.models.domain import Domain
from lrb.core.exceptions import AppValidationError, BusinessRuleViolationError, ErrorCode
from lrb.core.tenancy import require_public_schema
from lrb.core.validators.phone import validate_phone_number
from lrb.core.validators.validate_company_email_unique import (
    validate_company_email_unique,
)
from lrb.core.validators.validate_company_name import validate_company_name
from lrb.core.validators.tenant_slug import schema_name_for, validate_tenant_slug

@transaction.atomic
def create_company(
    *, name, slug, email, phone, country, city, address, logo_light=None, logo_dark=None
):
    require_public_schema()
    validate_company_name(value=name)
    validate_phone_number(phone)
    validate_company_email_unique(value=email)
    slug = validate_tenant_slug(value=slug)
    if Company.objects.filter(slug=slug).exists():
        raise AppValidationError(message="This workspace address is taken.", field="slug")

    try:
        company = Company.objects.create(
            schema_name=schema_name_for(slug=slug), slug=slug, name=name,
            logo_light=logo_light, logo_dark=logo_dark, email=email, phone=phone,
            country=country, city=city, address=address, is_active=True,
        )
    except IntegrityError:
        raise BusinessRuleViolationError(
            message="A company with this email or address already exists.",
            code=ErrorCode.COMPANY_ALREADY_EXISTS,
        )

    CompanySettings.objects.create(company=company)
    Domain.objects.create(
        tenant=company, domain=f"{slug}.{settings.TENANT_BASE_DOMAIN}", is_primary=True
    )
    company.create_schema(check_if_exists=True)  # CREATE SCHEMA + tenant migrations
    with tenant_context(company):
        call_command("sync_permissions", stdout=io.StringIO())  # this schema's catalogue
    return company

    # if Company.objects.exists():
    #     raise BusinessRuleViolationError(
    #         message="There can only be one company.",
    #         code=ErrorCode.COMPANY_ALREADY_EXISTS,
    #     )