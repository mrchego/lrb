from typing import List

from strawberry import auto
import strawberry
import strawberry_django

from lrb.accounts.graphql.types import UserType
from lrb.staff.models import Invitation


@strawberry_django.type(Invitation)
class InvitationType:
    id: auto
    email: auto
    used: auto
    expires_at: auto 
    accepted_at: auto
    created_at: auto

    @strawberry.field
    def role_name(self) -> str:
        return self.role.name if self.role else ""

    @strawberry.field
    def invited_by_email(self) -> str:
        return self.invited_by.email if self.invited_by else ""

    @strawberry.field
    def is_expired(self) -> bool:
        return self.is_expired

@strawberry.type
class InvitationConnection:
    items: List[InvitationType]
    total_count: int

@strawberry.type
class StaffMemberConnection:
    items: List[UserType]
    total_count: int