# lrb/company/graphql/platform.py
import strawberry

from lrb.company.graphql.inputs import RegisterCompanyInput
from lrb.company.graphql.payloads import CompanyMutationPayload
from lrb.company.selectors.is_slug_available import is_slug_available
from lrb.company.workflows.register_company import (
    register_company as register_company_workflow,
)
from lrb.core.exceptions import ApplicationError
from lrb.core.graphql.errors import format_application_error


@strawberry.type
class PlatformQuery:
    @strawberry.field
    def workspace_available(self, slug: str) -> bool:
        return is_slug_available(slug=slug)


@strawberry.type
class PlatformMutation:
    @strawberry.mutation
    def register_company(
        self, info: strawberry.Info, input: RegisterCompanyInput
    ) -> CompanyMutationPayload:
        try:
            company, _admin = register_company_workflow(
                company_name=input.name,
                slug=input.slug,
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
