import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.company.graphql.types import CompanyType, CompanySettingsType
from lrb.company.selectors.get_company import get_company
from lrb.company.selectors.get_company_settings import get_company_settings


@strawberry.type
class CompanyQuery:
    @strawberry.field
    def company(self, info: strawberry.Info) -> CompanyType:
        current = get_current_user_or_raise(info)
        return get_company(company_id=current.company_id)

    @strawberry.field
    def company_settings(self, info: strawberry.Info) -> CompanySettingsType:
        current = get_current_user_or_raise(info)
        company = get_company(company_id=current.company_id)
        return get_company_settings(company=company)