from typing import List

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.company.selectors.get_company import get_company
from lrb.core.money.company import get_company_currency
from lrb.core.money.currencies import currency_choices
from lrb.core.money.usage import company_has_money_data


@strawberry.type
class CurrencyType:
    code: str
    name: str
    decimals: int


@strawberry.type
class MoneyQuery:
    @strawberry.field
    def currency_choices(self, info: strawberry.Info) -> List[CurrencyType]:
        get_current_user_or_raise(info)
        return [CurrencyType(code=c.code, name=c.name, decimals=c.decimals) for c in currency_choices()]

    @strawberry.field
    def company_currency(self, info: strawberry.Info) -> CurrencyType:
        current = get_current_user_or_raise(info)
        c = get_company_currency(company_id=current.company_id)
        return CurrencyType(code=c.code, name=c.name, decimals=c.decimals)

    @strawberry.field
    def currency_locked(self, info: strawberry.Info) -> bool:
        current = get_current_user_or_raise(info)
        company = get_company(company_id=current.company_id)
        return company_has_money_data(company=company)
