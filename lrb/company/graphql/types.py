from typing import Optional

from strawberry import auto
import strawberry
import strawberry_django

from lrb.accounts.graphql.types import ImageType
from lrb.company.models.company import Company
from lrb.company.models.settings import CompanySettings


@strawberry_django.type(Company)
class CompanyType:
    id: auto
    name: auto
    email: auto
    phone: auto
    country: auto
    city: auto
    address: auto
    is_active: auto
    created_at: auto
    updated_at: auto

    @strawberry.field
    def logo_light(self) -> Optional[ImageType]:
        if not self.logo_light:
            return None
        return ImageType(url=self.logo_light.url, name=self.logo_light.name)

    @strawberry.field
    def logo_dark(self) -> Optional[ImageType]:
        if not self.logo_dark:
            return None
        return ImageType(url=self.logo_dark.url, name=self.logo_dark.name)


@strawberry_django.type(CompanySettings)
class CompanySettingsType:
    id: auto
    timezone: auto
    currency: auto
    language: auto
    date_format: auto
    theme: auto
