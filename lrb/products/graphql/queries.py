from typing import Optional

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_permission
from lrb.products.graphql.inputs import ProductIdInput
from lrb.products.graphql.types import ProductConnection, ProductType
from lrb.products.selectors.get_product import get_product
from lrb.products.selectors.list_products import list_products


@strawberry.type
class ProductQuery:
    @strawberry.field
    @require_permission("products.view_product")
    def product(
        self, info: strawberry.Info, input: ProductIdInput
    ) -> Optional[ProductType]:
        current = get_current_user_or_raise(info)
        return get_product(
            product_id=input.product_id, company_id=str(current.company_id)
        )

    @strawberry.field
    @require_permission("products.view_product")
    def products(
        self,
        info: strawberry.Info,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> ProductConnection:
        current = get_current_user_or_raise(info)
        items, total_count = list_products(
            company_id=str(current.company_id),
            is_active=is_active,
            search=search,
            limit=limit,
            offset=offset,
        )
        return ProductConnection(items=items, total_count=total_count)
