import strawberry
from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.company.graphql.inputs import (
    RegisterCompanyInput,
    UpdateCompanyInput,
    UpdateCompanySettingsInput,
)
from lrb.company.graphql.payloads import (
    CompanyMutationPayload,
    CompanySettingsMutationPayload,
)
from lrb.company.selectors.get_company import get_company
from lrb.company.services.update_company import update_company as update_action
from lrb.company.services.update_company_settings import (
    update_company_settings as update_settings_action,
)
from lrb.company.workflows.register_company import (
    register_company as register_company_workflow,
)
from lrb.authorization.decorators import require_owner
from lrb.core.exceptions import ApplicationError
from lrb.core.graphql.errors import format_application_error


@strawberry.type
class CompanyMutation:
    @strawberry.mutation
    def register_company(
        self, info: strawberry.Info, input: RegisterCompanyInput
    ) -> CompanyMutationPayload:
        # No auth check — this is the bootstrap step, before any user exists.
        # create_company already refuses if a company has already been registered.
        try:
            company, admin = register_company_workflow(
                company_name=input.name,
                company_email=input.email,
                company_phone=input.phone,
                company_country=input.country,
                company_city=input.city,
                company_address=input.address,
                company_logo_light=input.logo_light,
                company_logo_dark=input.logo_dark,
                admin_email=input.admin_email,
                admin_password=input.admin_password,
                admin_first_name=input.admin_first_name,
                admin_last_name=input.admin_last_name,
                request=info.context.request,
            )
            return CompanyMutationPayload(success=True, company=company)
        except ApplicationError as e:
            return CompanyMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def update_company(
        self, info: strawberry.Info, input: UpdateCompanyInput
    ) -> CompanyMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            company = update_action(
                company_id=current.company_id,
                name=input.name,
                logo_light=input.logo_light,
                logo_dark=input.logo_dark,
                email=input.email,
                phone=input.phone,
                country=input.country,
                city=input.city,
                address=input.address,
                is_active=input.is_active,
            )
            return CompanyMutationPayload(success=True, company=company)
        except ApplicationError as e:
            return CompanyMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def update_company_settings(
        self, info: strawberry.Info, input: UpdateCompanySettingsInput
    ) -> CompanySettingsMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            company = get_company(company_id=current.company_id)
            settings = update_settings_action(
                company=company,
                timezone=input.timezone,
                currency=input.currency,
                language=input.language,
                date_format=input.date_format,
                theme=input.theme,
            )
            return CompanySettingsMutationPayload(success=True, settings=settings)
        except ApplicationError as e:
            return CompanySettingsMutationPayload(
                success=False, errors=[format_application_error(e)]
            )
