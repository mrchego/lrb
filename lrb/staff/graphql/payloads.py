from typing import List, Optional

import strawberry

from lrb.accounts.graphql.types import UserType
from lrb.core.graphql.errors import MutationError
from lrb.core.graphql.payloads import BulkActionFailure
from lrb.staff.graphql.types import InvitationType


@strawberry.type
class InvitationMutationPayload:
    success: bool
    invitation: Optional[InvitationType] = None
    errors: Optional[List[MutationError]] = None

@strawberry.type
class AcceptInvitationPayload:
    success: bool
    invitation: Optional[UserType] = None
    errors: Optional[List[MutationError]] = None


@strawberry.type
class BulkInvitationActionPayload:
    success: bool
    succeeded_ids: List[strawberry.ID]
    failed: List[BulkActionFailure]