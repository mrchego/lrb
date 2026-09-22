from celery import result
import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_permission
from lrb.core.exceptions import ApplicationError
from lrb.core.graphql.errors import format_application_error
from lrb.core.graphql.payloads import (
    SimpleMutationPayload,
    to_bulk_payload,
)
from lrb.products.graphql.inputs import (
    ActivateProductInput,
    BulkProductIdsInput,
    CreateProductInput,
    DeactivateProductInput,
    DeleteProductInput,
    UpdateProductInput,
)
from lrb.products.graphql.payloads import (
    BulkProductActionPayload,
    ProductMutationPayload,
)
from lrb.products.services.activate_product import (
    activate_product as activate_product_action,
)
from lrb.products.services.bulk_activate_products import (
    bulk_activate_products as bulk_activate_products_action,
)
from lrb.products.services.bulk_deactivate_product import (
    bulk_deactivate_product as bulk_deactivate_product_action,
)
from lrb.products.services.bulk_delete_product import (
    bulk_delete_product as bulk_delete_product_action,
)
from lrb.products.services.create_product import create_product as create_product_action
from lrb.products.services.deactivate_product import deactivate_product
from lrb.products.services.delete_product import delete_product as delete_product_action
from lrb.products.services.update_product import update_product as update_product_action


@strawberry.type
class ProductMutation:
    @strawberry.mutation
    @require_permission("products.add_product")
    def create_product(
        self, info: strawberry.Info, input: CreateProductInput
    ) -> ProductMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            product = create_product_action(
                company=current.company,
                name=input.name,
                sku=input.sku,
                price=input.price,
                is_active=input.is_active,
            )
            return ProductMutationPayload(success=True, product=product)
        except ApplicationError as e:
            return ProductMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_permission("products.change_product")
    def update_product(
        self, info: strawberry.Info, input: UpdateProductInput
    ) -> ProductMutationPayload:
        try:
            product = update_product_action(
                product_id=input.product_id,
                name=input.name,
                sku=input.sku,
                price=input.price,
                is_active=input.is_active,
            )
            return ProductMutationPayload(success=True, product=product)
        except ApplicationError as e:
            return ProductMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_permission("products.delete_product")
    def delete_product(
        self, info: strawberry.Info, input: DeleteProductInput
    ) -> SimpleMutationPayload:
        try:
            delete_product_action(product_id=input.product_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error[e]]
            )

    @strawberry.mutation
    @require_permission("activate_product")
    def activate_product(
        self, info: strawberry.Info, input: ActivateProductInput
    ) -> ProductMutationPayload:
        try:
            product = activate_product_action(product_id=input.product_id)
            return ProductMutationPayload(success=True, product=product)
        except ApplicationError as e:
            return ProductMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_permission("deactivate_product")
    def deactivate_product(
        self, info: strawberry.Info, input: DeactivateProductInput
    ) -> ProductMutationPayload:
        try:
            product = deactivate_product(product_id=input.product_id)
            return ProductMutationPayload(success=True, product=product)
        except ApplicationError as e:
            return ProductMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_permission("bulk_activate_products")
    def bulk_activate_products(
        self, info: strawberry.Info, input: BulkProductIdsInput
    ) -> BulkProductActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_activate_products_action(
            product_ids=input.product_ids, company_id=str(current.company_id)
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_permission("bulk_deactivate_products")
    def bulk_deactivate_products(
        self, info: strawberry.Info, input: BulkProductIdsInput
    ) -> BulkProductActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_deactivate_product_action(
            product_ids=input.product_ids, company_id=str(current.company_id)
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_permission("bulk_delete_product")
    def bulk_delete_product(
        self, info: strawberry.Info, input: BulkProductIdsInput
    ) -> BulkProductActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_delete_product_action(
            product_ids=input.product_ids, company_id=str(current.company_id)
        )
        return to_bulk_payload(result)
