"""Plain data shapes for the phone package.

Nothing here imports the `phonenumbers` metadata, so GraphQL, services and tests can
import these cheaply. The rules live in engine.py; the policies in policies.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from lrb.core.exceptions import AppValidationError


class PhoneIssue(StrEnum):
    """Why a number was rejected. Stable codes: tests, logs and the UI can rely on them."""

    EMPTY = "empty"
    BAD_CHARACTERS = "bad_characters"
    UNKNOWN_COUNTRY_CODE = "unknown_country_code"
    NOT_A_NUMBER = "not_a_number"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    INVALID_LENGTH = "invalid_length"
    LOCAL_ONLY = "local_only"
    INVALID_FOR_COUNTRY = "invalid_for_country"
    SHORT_OR_EMERGENCY = "short_or_emergency"
    TYPE_NOT_ALLOWED = "type_not_allowed"


# TYPE_NOT_ALLOWED has no entry on purpose: its text comes from the policy that rejected it.
MESSAGES: dict[PhoneIssue, str] = {
    PhoneIssue.EMPTY: "Enter a phone number.",
    PhoneIssue.BAD_CHARACTERS: (
        "Phone numbers can only contain digits, spaces and the characters + ( ) - ."
    ),
    PhoneIssue.UNKNOWN_COUNTRY_CODE: (
        "The country code isn't recognised. Start with + and a valid country code."
    ),
    PhoneIssue.NOT_A_NUMBER: "This doesn't look like a phone number.",
    PhoneIssue.TOO_SHORT: "This phone number is too short.",
    PhoneIssue.TOO_LONG: "This phone number is too long.",
    PhoneIssue.INVALID_LENGTH: "This phone number has the wrong number of digits.",
    PhoneIssue.LOCAL_ONLY: "Include the area code, or use the full international format.",
    PhoneIssue.INVALID_FOR_COUNTRY: "This isn't a valid phone number for its country.",
    PhoneIssue.SHORT_OR_EMERGENCY: "Emergency and short service numbers can't be used here.",
}


class PhoneValidationError(AppValidationError):
    """An AppValidationError that also says *which* rule failed (`.issue`)."""

    def __init__(self, issue: PhoneIssue, *, message: str, field: str = "phone"):
        super().__init__(message, field=field)
        self.issue = issue


@dataclass(frozen=True)
class PhoneInfo:
    """Everything libphonenumber can tell us about one parsed number.

    Built for any number that *parses*, valid or not: check `is_valid`. The location,
    carrier and time-zone fields are only filled for valid numbers.
    """

    e164: str                          # +254712345678  <- the form we store
    international: str                 # +254 712 345678
    national: str                      # 0712 345678
    rfc3966: str                       # tel:+254-712-345678
    country_code: int                  # 254
    national_number: str               # 712345678 (string: leading zeros can matter)
    region_code: Optional[str]         # "KE"; None for non-geographic codes (+800, +882...)
    regions_for_calling_code: tuple[str, ...]  # +1 -> ("US", "CA", ...)
    number_type: str                   # MOBILE, FIXED_LINE, VOIP, ... (see engine.TYPE_NAMES)
    is_possible: bool                  # length plausible for the country
    is_valid: bool                     # prefix + length match a real numbering plan
    is_geographical: bool              # tied to a place (landlines), not a mobile/free number
    can_be_dialled_internationally: bool
    location: str                      # "Kenya" / "London" (geocoder; may be "")
    original_carrier: str              # "Safaricom" - prefix allocation, NOT live portability
    time_zones: tuple[str, ...]        # ("Africa/Nairobi",)


@dataclass(frozen=True)
class PhoneInspection:
    """The result of inspecting user input. Never raises on bad input: read `ok`."""

    ok: bool
    issue: Optional[PhoneIssue] = None
    message: Optional[str] = None
    info: Optional[PhoneInfo] = None   # present whenever the text parsed, even if rejected

    @property
    def e164(self) -> Optional[str]:
        return self.info.e164 if self.ok and self.info else None
