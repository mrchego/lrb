"""Phone numbers, powered by Google's libphonenumber.

Import from here, never from `phonenumbers` directly:

    from lrb.core.phone import normalize_phone, MOBILE, resolve_region

    phone = normalize_phone(value=raw, region=resolve_region(company.country), policy=MOBILE)
"""
from lrb.core.phone.engine import (
    TYPE_NAMES,
    example_number,
    format_phone,
    inspect_phone,
    normalize_phone,
    resolve_region,
    supported_regions,
)
from lrb.core.phone.policies import BY_NAME as POLICIES_BY_NAME
from lrb.core.phone.policies import CONTACT, MOBILE, PhonePolicy
from lrb.core.phone.types import (
    PhoneInfo,
    PhoneInspection,
    PhoneIssue,
    PhoneValidationError,
)

__all__ = [
    "CONTACT",
    "MOBILE",
    "POLICIES_BY_NAME",
    "TYPE_NAMES",
    "PhoneInfo",
    "PhoneInspection",
    "PhoneIssue",
    "PhonePolicy",
    "PhoneValidationError",
    "example_number",
    "format_phone",
    "inspect_phone",
    "normalize_phone",
    "resolve_region",
    "supported_regions",
]
