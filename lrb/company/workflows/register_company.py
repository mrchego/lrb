from django.db import transaction

from lrb.accounts.services.create_user import create_user
from lrb.company.services.create_company import create_company
from lrb.identity.services.send_email_verification_code import (
    send_email_verification_code,
)


@transaction.atomic
def register_company(
    *,
    company_name,
    company_email,
    company_phone,
    company_country,
    company_city,
    company_address,
    company_logo_light,
    company_logo_dark,
    admin_email,
    admin_password,
    admin_first_name,
    admin_last_name,
    request,
):
    company = create_company(
        name=company_name,
        email=company_email,
        phone=company_phone,
        country=company_country,
        city=company_city,
        address=company_address,
        logo_light=company_logo_light,
        logo_dark=company_logo_dark,
    )

    admin = create_user(
        email=admin_email,
        first_name=admin_first_name,
        last_name=admin_last_name,
        password=admin_password,
        company=company,
        can_login=True,
        is_active=True,
        is_staff=True,
        is_superuser=True,
        is_founder=True,
    )

    send_email_verification_code(user=admin)

    return company, admin
