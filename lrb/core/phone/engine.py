"""The one place that talks to Google's libphonenumber (the `phonenumbers` package).

Rule of the house: nothing else in lrb imports `phonenumbers`. Everything else calls:

    inspect_phone(...)    never raises on bad input; returns PhoneInspection (for UIs, APIs)
    normalize_phone(...)  raises PhoneValidationError, returns the E.164 string to store
    format_phone(...)     display formatting; never raises, falls back to the raw text
    example_number(...)   a realistic sample number for a country (placeholders, hints)
    supported_regions()   every region libphonenumber knows, with its calling code

Pure functions, keyword-only arguments, no database access.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal, Optional

import phonenumbers
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from phonenumbers import NumberParseException, ValidationResult
from phonenumbers import PhoneNumberFormat as Fmt
from phonenumbers import PhoneNumberType as Kind
from phonenumbers import carrier as _carrier
from phonenumbers import geocoder as _geocoder
from phonenumbers import shortnumberinfo as _short
from phonenumbers import timezone as _timezone

from lrb.core.phone.policies import CONTACT, PhonePolicy
from lrb.core.phone.types import (
    MESSAGES,
    PhoneInfo,
    PhoneInspection,
    PhoneIssue,
    PhoneValidationError,
)

# A phone number typed by a human is short. The library caps input at 250 characters;
# we stop far earlier so a huge string never reaches the parser.
MAX_INPUT_LENGTH = 40

# Digits (any script: the library converts them), whitespace and ( ) - . with at most one
# "+", which must come first (after any "(" or spaces, so "(+254) 712 345 678" works).
# Deliberately NOT allowed:
#   letters  -> "+1 800 FLOWERS" is "valid" to libphonenumber (vanity numbers)
#   "ext 5"  -> extensions are silently dropped by E.164, which would change the number
_ALLOWED_INPUT = re.compile(r"^[\s(]*\+?[\d\s().\-]*$")

TYPE_NAMES: dict[int, str] = {
    Kind.FIXED_LINE: "FIXED_LINE",
    Kind.MOBILE: "MOBILE",
    Kind.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
    Kind.TOLL_FREE: "TOLL_FREE",
    Kind.PREMIUM_RATE: "PREMIUM_RATE",
    Kind.SHARED_COST: "SHARED_COST",
    Kind.VOIP: "VOIP",
    Kind.PERSONAL_NUMBER: "PERSONAL_NUMBER",
    Kind.PAGER: "PAGER",
    Kind.UAN: "UAN",
    Kind.VOICEMAIL: "VOICEMAIL",
    Kind.UNKNOWN: "UNKNOWN",
}
_KIND_BY_NAME: dict[str, int] = {name.lower(): const for const, name in TYPE_NAMES.items()}

_PARSE_ISSUES = {
    NumberParseException.INVALID_COUNTRY_CODE: PhoneIssue.UNKNOWN_COUNTRY_CODE,
    NumberParseException.NOT_A_NUMBER: PhoneIssue.NOT_A_NUMBER,
    NumberParseException.TOO_SHORT_AFTER_IDD: PhoneIssue.TOO_SHORT,
    NumberParseException.TOO_SHORT_NSN: PhoneIssue.TOO_SHORT,
    NumberParseException.TOO_LONG: PhoneIssue.TOO_LONG,
}

# is_possible_number_with_reason(): anything not listed here (IS_POSSIBLE) passes.
_POSSIBLE_ISSUES = {
    ValidationResult.INVALID_COUNTRY_CODE: PhoneIssue.UNKNOWN_COUNTRY_CODE,
    ValidationResult.TOO_SHORT: PhoneIssue.TOO_SHORT,
    ValidationResult.TOO_LONG: PhoneIssue.TOO_LONG,
    ValidationResult.INVALID_LENGTH: PhoneIssue.INVALID_LENGTH,
    ValidationResult.IS_POSSIBLE_LOCAL_ONLY: PhoneIssue.LOCAL_ONLY,
}

# Rejections where showing a sample number actually helps the person fix their input.
_HINTED_ISSUES = frozenset(
    {
        PhoneIssue.TOO_SHORT,
        PhoneIssue.TOO_LONG,
        PhoneIssue.INVALID_LENGTH,
        PhoneIssue.LOCAL_ONLY,
        PhoneIssue.INVALID_FOR_COUNTRY,
    }
)

FormatStyle = Literal[
    "e164", "international", "national", "rfc3966", "out_of_country", "mobile_dialing"
]


# --------------------------------------------------------------------------- regions
def resolve_region(*candidates: object) -> str:
    """First candidate that is a real ISO 3166-1 alpha-2 region, else PHONE_DEFAULT_REGION.

    The region only matters for numbers typed WITHOUT a leading "+" (e.g. 0712 345678):
    it says which country's rules to read them under. A free-text country such as
    "Kenya" is not an alpha-2 code, so it is skipped and the default is used.
    """
    for candidate in candidates:
        if isinstance(candidate, str):
            code = candidate.strip().upper()
            if code in phonenumbers.SUPPORTED_REGIONS:
                return code
    default = str(getattr(settings, "PHONE_DEFAULT_REGION", "KE")).strip().upper()
    if default not in phonenumbers.SUPPORTED_REGIONS:
        raise ImproperlyConfigured(
            f"PHONE_DEFAULT_REGION={default!r} is not a region libphonenumber supports."
        )
    return default


@lru_cache(maxsize=1)
def supported_regions() -> tuple[tuple[str, int], ...]:
    """Every supported (region_code, calling_code), sorted by region code."""
    return tuple(
        (region, phonenumbers.country_code_for_region(region))
        for region in sorted(phonenumbers.SUPPORTED_REGIONS)
    )


@lru_cache(maxsize=512)
def example_number(*, region: str, kind: str = "mobile") -> Optional[str]:
    """A realistic (not real) sample number, e.g. '+254 712 123456', or None."""
    const = _KIND_BY_NAME.get(kind.lower())
    if const is None or region not in phonenumbers.SUPPORTED_REGIONS:
        return None
    example = phonenumbers.example_number_for_type(region, const)
    return phonenumbers.format_number(example, Fmt.INTERNATIONAL) if example else None


# --------------------------------------------------------------------------- inspect
def inspect_phone(
    *,
    value: object,
    region: Optional[str] = None,
    policy: PhonePolicy = CONTACT,
    lang: str = "en",
) -> PhoneInspection:
    """Run every libphonenumber check on `value`. Never raises on bad user input.

    Order matters: each step turns a vague "invalid" into the most useful message.
      1. empty / forbidden characters / length cap   (our own guard before the parser)
      2. parse                                        (can the text be read as a number?)
      3. short & emergency numbers                    (999 is "possible" locally; not a contact)
      4. possible?                                    (length plausible -> too short/long)
      5. valid?                                       (prefix + length match the plan)
      6. type allowed by `policy`?                    (mobile / fixed line / premium...)
    """
    default_region = resolve_region(region)
    raw = value.strip() if isinstance(value, str) else ""

    if not raw:
        return _reject(PhoneIssue.EMPTY)
    if len(raw) > MAX_INPUT_LENGTH or not _ALLOWED_INPUT.match(raw):
        return _reject(PhoneIssue.BAD_CHARACTERS)

    has_plus = "+" in raw  # the regex above guarantees it is a leading "+" if present
    try:
        number = phonenumbers.parse(raw, default_region)
    except NumberParseException as exc:
        issue = _PARSE_ISSUES.get(exc.error_type, PhoneIssue.NOT_A_NUMBER)
        # Without a "+" we know which country the person meant, so a sample can help.
        return _reject(issue, hint_region=None if has_plus else default_region)

    kind = phonenumbers.number_type(number)
    info = _build_info(number, kind, _safe_lang(lang))
    hint_region = phonenumbers.region_code_for_country_code(number.country_code)

    if not has_plus and _is_short_or_emergency(raw, number, default_region):
        return _reject(PhoneIssue.SHORT_OR_EMERGENCY, info=info)

    possible_issue = _POSSIBLE_ISSUES.get(phonenumbers.is_possible_number_with_reason(number))
    if possible_issue is not None:
        return _reject(possible_issue, info=info, hint_region=hint_region)

    if not info.is_valid:
        return _reject(PhoneIssue.INVALID_FOR_COUNTRY, info=info, hint_region=hint_region)

    if not policy.allows(kind):
        return _reject(
            PhoneIssue.TYPE_NOT_ALLOWED, info=info, message=policy.rejection_message
        )

    return PhoneInspection(ok=True, info=info)


def normalize_phone(
    *,
    value: object,
    region: Optional[str] = None,
    policy: PhonePolicy = CONTACT,
    field: str = "phone",
) -> str:
    """Validate `value` and return it as E.164 (e.g. '+254712345678') - the form we store.

    Idempotent: normalizing an already-normalized number returns it unchanged.
    """
    result = inspect_phone(value=value, region=region, policy=policy)
    if not result.ok or result.info is None:
        raise PhoneValidationError(
            result.issue or PhoneIssue.NOT_A_NUMBER,
            message=result.message or MESSAGES[PhoneIssue.NOT_A_NUMBER],
            field=field,
        )
    return result.info.e164


# --------------------------------------------------------------------------- format
def format_phone(
    *,
    value: object,
    style: FormatStyle = "international",
    region: Optional[str] = None,
    from_region: Optional[str] = None,
) -> str:
    """Format for display. Never raises: text that can't be parsed is returned as-is.

    e164            +254712345678
    international   +254 712 345678
    national        0712 345678
    rfc3966         tel:+254-712-345678            (for href="tel:...")
    out_of_country  how to dial it FROM `from_region` (adds that country's exit prefix)
    mobile_dialing  what to dial from a mobile in `from_region`, digits only
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        number = phonenumbers.parse(value.strip(), resolve_region(region))
    except NumberParseException:
        return value.strip()

    if style == "e164":
        return phonenumbers.format_number(number, Fmt.E164)
    if style == "national":
        return phonenumbers.format_number(number, Fmt.NATIONAL)
    if style == "rfc3966":
        return phonenumbers.format_number(number, Fmt.RFC3966)
    if style == "out_of_country":
        return phonenumbers.format_out_of_country_calling_number(
            number, resolve_region(from_region)
        )
    if style == "mobile_dialing":
        return phonenumbers.format_number_for_mobile_dialing(
            number, resolve_region(from_region), False
        )
    return phonenumbers.format_number(number, Fmt.INTERNATIONAL)


# --------------------------------------------------------------------------- internals
def _build_info(number: phonenumbers.PhoneNumber, kind: int, lang: str) -> PhoneInfo:
    is_valid = phonenumbers.is_valid_number(number)
    location = original_carrier = ""
    zones: tuple[str, ...] = ()
    if is_valid:
        location = _geocoder.description_for_valid_number(number, lang) or ""
        original_carrier = _carrier.name_for_valid_number(number, lang) or ""
        zones = tuple(
            z for z in _timezone.time_zones_for_number(number) if z != _timezone.UNKNOWN_TIMEZONE
        )
    return PhoneInfo(
        e164=phonenumbers.format_number(number, Fmt.E164),
        international=phonenumbers.format_number(number, Fmt.INTERNATIONAL),
        national=phonenumbers.format_number(number, Fmt.NATIONAL),
        rfc3966=phonenumbers.format_number(number, Fmt.RFC3966),
        country_code=number.country_code,
        national_number=str(number.national_number),
        region_code=phonenumbers.region_code_for_number(number),
        regions_for_calling_code=tuple(
            phonenumbers.region_codes_for_country_code(number.country_code)
        ),
        number_type=TYPE_NAMES.get(kind, "UNKNOWN"),
        is_possible=(
            phonenumbers.is_possible_number_with_reason(number) == ValidationResult.IS_POSSIBLE
        ),
        is_valid=is_valid,
        is_geographical=phonenumbers.is_number_geographical(number),
        can_be_dialled_internationally=phonenumbers.can_be_internationally_dialled(number),
        location=location,
        original_carrier=original_carrier,
        time_zones=zones,
    )


def _is_short_or_emergency(raw: str, number: phonenumbers.PhoneNumber, region: str) -> bool:
    digits = phonenumbers.normalize_digits_only(raw)
    return _short.is_emergency_number(digits, region) or _short.is_valid_short_number_for_region(
        number, region
    )


def _safe_lang(lang: str) -> str:
    return lang if isinstance(lang, str) and re.fullmatch(r"[a-z]{2}", lang) else "en"


def _reject(
    issue: PhoneIssue,
    *,
    info: Optional[PhoneInfo] = None,
    message: Optional[str] = None,
    hint_region: Optional[str] = None,
) -> PhoneInspection:
    text = message or MESSAGES[issue]
    if issue in _HINTED_ISSUES and hint_region and hint_region != phonenumbers.UNKNOWN_REGION:
        sample = example_number(region=hint_region)
        if sample:
            text = f"{text} For example: {sample}."
    return PhoneInspection(ok=False, issue=issue, message=text, info=info)
