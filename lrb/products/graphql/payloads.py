from typing import List, Optional

import strawberry

from lrb.core.graphql.errors import MutationError
from lrb.core.graphql.payloads import BulkActionFailure, BulkActionPayload
from lrb.products.graphql.types import ProductType


@strawberry.type
class ProductMutationPayload:
    success:bool
    product: Optional[ProductType] = None
    errors: Optional[List[MutationError]] = None


ProductBulkActionFailure = BulkActionFailure
BulkProductActionPayload = BulkActionPayload