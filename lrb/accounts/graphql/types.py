from __future__ import annotations
from typing import List, Optional
import strawberry
import strawberry_django
from strawberry import auto
from lrb.accounts.models import User

@strawberry.type
class ImageType:
    url: str
    name: str

@strawberry.type
class CompanyBasicType:
    id: strawberry.ID
    name: str

@strawberry_django.type(User)
class UserType:
    id: auto
    email: auto
    first_name: auto
    last_name: auto
    phone: auto
    can_login: auto
    is_active: auto
    is_staff: auto
    is_superuser: auto
    is_founder: auto
    password_reset_required: auto
    last_password_change: auto
    failed_login_attempts: auto
    locked_until: auto
    date_joined: auto
    last_login: auto
    created_at: auto
    updated_at: auto

    @strawberry.field
    def avatar(self) -> Optional[ImageType]:
        if not self.avatar:
            return None
        return ImageType(url=self.avatar.url, name=self.avatar.name)

    @strawberry.field
    def full_name(self) -> str:
        return self.full_name

    @strawberry.field
    def display_name(self) -> str:
        return self.display_name

    @strawberry.field
    def is_locked(self) -> bool:
        return self.is_locked

    @strawberry.field
    def company(self) -> Optional[CompanyBasicType]:
        if not self.company_id:
            return None
        return CompanyBasicType(id=self.company.id, name=self.company.name)

@strawberry.type
class UserConnection:
    items: List[UserType]
    total_count: int 