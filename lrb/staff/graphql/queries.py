from typing import Optional

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_owner
from lrb.staff.graphql.types import InvitationConnection, StaffMemberConnection
from lrb.staff.selectors.count_pending_invitations import count_pending_invitations
from lrb.staff.selectors.list_invitations import list_invitations
from lrb.staff.selectors.list_staff_members import list_staff_members


@strawberry.type
class StaffQuery:
    @strawberry.field
    @require_owner()
    def invitations(
        self,
        info: strawberry.Info,
        used: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> InvitationConnection:
        current = get_current_user_or_raise(info)
        items, total_count = list_invitations(
            company_id=str(current.company_id), used=used, limit=limit, offset=offset
        )
        return InvitationConnection(items=items, total_count=total_count)

    @strawberry.field
    @require_owner()
    def pending_invitations_count(self, info: strawberry.Info) -> int:
        current = get_current_user_or_raise(info)
        return count_pending_invitations(company_id=str(current.company_id))

    @strawberry.field
    @require_owner()
    def staff_members(
        self,
        info: strawberry.Info,
        can_login: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> StaffMemberConnection:
        current = get_current_user_or_raise(info)
        items, total_count = list_staff_members(
            company_id=str(current.company_id),
            can_login=can_login,
            limit=limit,
            offset=offset,
        )
        return StaffMemberConnection(items=items, total_count=total_count)
