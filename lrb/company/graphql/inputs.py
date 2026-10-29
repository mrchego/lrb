import strawberry
from typing import Optional
from strawberry.file_uploads import Upload


@strawberry.input
class CreateCompanyInput:
    name: str
    logo_light: Optional[Upload] = None
    logo_dark: Optional[Upload] = None
    email: str
    phone: str
    country: str
    city: str
    address: str


@strawberry.input
class UpdateCompanyInput:
    name: Optional[str] = None
    logo_light: Optional[Upload] = None
    logo_dark: Optional[Upload] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


@strawberry.input
class RegisterCompanyInput:
    name: str
    email: str
    phone: str
    country: str
    city: str
    address: str
    logo_light: Optional[Upload] = None
    logo_dark: Optional[Upload] = None
    admin_email: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str


@strawberry.input
class UpdateCompanySettingsInput:
    timezone: Optional[str] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    date_format: Optional[str] = None
    theme: Optional[str] = None
