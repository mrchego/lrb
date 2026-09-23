from typing import List, Optional

import strawberry


@strawberry.input
class InviteStaffInput:
    email: str
    first_name: str
    last_name: str
    can_login: bool = True
    role_id: Optional[strawberry.ID] = None

@strawberry.input
class RevokeInvitationInput:
    invitation_id: strawberry.ID

@strawberry.input
class AcceptInvitationInput:
    token: str
    new_password: str

@strawberry.input
class SetStaffLoginAccessInput:
    user_id: strawberry.ID
    can_login: bool

@strawberry.input
class PromoteStaffToLoginInput:
    user_id: strawberry.ID
    role_id: strawberry.ID

@strawberry.input
class ResendInvitationInput:
    invitation_id: strawberry.ID

@strawberry.input
class BulkRevokeInvitationsInput:
    invitation_ids: List[strawberry.ID]

@strawberry.input
class DemoteStaffFromLoginInput:
    user_id: strawberry.ID