from __future__ import annotations

from enum import Enum
from typing import List, Optional

import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.core.phone import CONTACT, MOBILE, PhoneInfo, resolve_region
from lrb.core.phone import inspect_phone as _inspect_phone


@strawberry.enum
class PhoneRequirement(Enum):
    """Which kinds of number the field being edited accepts (see lrb.core.phone.policies)."""

    CONTACT = "contact"  # landline, mobile, toll-free, VoIP... (not premium-rate etc.)
    MOBILE = "mobile"    # must be able to receive SMS / WhatsApp


_POLICY = {PhoneRequirement.CONTACT: CONTACT, PhoneRequirement.MOBILE: MOBILE}


@strawberry.type
class PhoneInfoType:
    e164: str
    international: str
    national: str
    rfc3966: str
    country_code: int
    national_number: str
    region_code: Optional[str]
    regions_for_calling_code: List[str]
    number_type: str
    is_possible: bool
    is_valid: bool
    is_geographical: bool
    can_be_dialled_internationally: bool
    location: str
    # Who the number range was ORIGINALLY allocated to. Not a live lookup: if the person
    # ported their number to another network, this still names the first one.
    original_carrier: str
    time_zones: List[str]


@strawberry.type
class PhoneInspectionType:
    ok: bool
    issue: Optional[str]
    message: Optional[str]
    info: Optional[PhoneInfoType]


def _info_type(info: PhoneInfo) -> PhoneInfoType:
    return PhoneInfoType(
        e164=info.e164,
        international=info.international,
        national=info.national,
        rfc3966=info.rfc3966,
        country_code=info.country_code,
        national_number=info.national_number,
        region_code=info.region_code,
        regions_for_calling_code=list(info.regions_for_calling_code),
        number_type=info.number_type,
        is_possible=info.is_possible,
        is_valid=info.is_valid,
        is_geographical=info.is_geographical,
        can_be_dialled_internationally=info.can_be_dialled_internationally,
        location=info.location,
        original_carrier=info.original_carrier,
        time_zones=list(info.time_zones),
    )


@strawberry.type
class PhoneQuery:
    @strawberry.field
    def inspect_phone(
        self,
        info: strawberry.Info,
        phone: str,
        region: Optional[str] = None,
        requirement: PhoneRequirement = PhoneRequirement.CONTACT,
        language: str = "en",
    ) -> PhoneInspectionType:
        """Everything libphonenumber knows about `phone`, plus whether our rules accept it.

        Read-only and stateless: nothing is stored. Signed-in users only (no anonymous
        use of the carrier/geocoder data). `region` only matters for numbers typed
        without a leading "+"; it defaults to the caller's company country.
        """
        current = get_current_user_or_raise(info)
        result = _inspect_phone(
            value=phone,
            region=resolve_region(region, current.company.country),
            policy=_POLICY[requirement],
            lang=language,
        )
        return PhoneInspectionType(
            ok=result.ok,
            issue=result.issue.value if result.issue else None,
            message=result.message,
            info=_info_type(result.info) if result.info else None,
        )
