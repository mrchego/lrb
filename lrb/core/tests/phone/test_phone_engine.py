"""Pure unit tests for lrb.core.phone - no database, no GraphQL.

The numbers used come from libphonenumber's own metadata (example numbers) wherever a
test needs a particular *kind* of number, so these tests survive its regular metadata
updates. Location/carrier assertions are deliberately loose for the same reason.
"""
from __future__ import annotations

import phonenumbers
import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from phonenumbers import PhoneNumberType as Kind

from lrb.core.exceptions import AppValidationError, ErrorCode
from lrb.core.phone import (
    CONTACT,
    MOBILE,
    PhoneIssue,
    PhoneValidationError,
    example_number,
    format_phone,
    inspect_phone,
    normalize_phone,
    resolve_region,
    supported_regions,
)
from lrb.core.validators.phone import validate_phone_number

KE_MOBILE = "+254712345678"
KE_LANDLINE = "+254202345678"


def _example_e164(region: str, kind: int) -> str:
    number = phonenumbers.example_number_for_type(region, kind)
    assert number is not None, f"no example for {region}/{kind}"
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


# --------------------------------------------------------------------- normalization
@pytest.mark.parametrize(
    "raw",
    [
        "+254712345678",
        "+254 712 345 678",
        "+254-712-345-678",
        "(+254) 712 345 678",
        "0712345678",
        "0712 345 678",
        "(0712) 345-678",
        "254712345678",
        "  +254712345678  ",
        "+٢٥٤٧١٢٣٤٥٦٧٨",  # Arabic-Indic digits: libphonenumber converts them
    ],
)
def test_many_spellings_normalize_to_one_e164(raw):
    assert normalize_phone(value=raw, region="KE") == KE_MOBILE


def test_normalize_is_idempotent():
    once = normalize_phone(value="0712 345 678", region="KE")
    assert normalize_phone(value=once) == once


def test_a_plus_number_ignores_the_region():
    assert normalize_phone(value=KE_MOBILE, region="US") == KE_MOBILE


def test_national_format_is_read_under_the_given_region():
    assert inspect_phone(value="0712345678", region="KE").ok
    assert not inspect_phone(value="0712345678", region="US").ok


def test_fixtures_used_by_the_existing_test_suite_are_valid():
    assert normalize_phone(value="+254700000000") == "+254700000000"
    assert normalize_phone(value="+254700000001") == "+254700000001"


# --------------------------------------------------------------------- rejections
@pytest.mark.parametrize(
    "raw, issue",
    [
        ("", PhoneIssue.EMPTY),
        ("    ", PhoneIssue.EMPTY),
        (None, PhoneIssue.EMPTY),
        (254712345678, PhoneIssue.EMPTY),  # not a string
        ("abc", PhoneIssue.BAD_CHARACTERS),
        ("+1 800 FLOWERS", PhoneIssue.BAD_CHARACTERS),  # vanity: valid to the library, not to us
        ("+254 712 345 678 ext 5", PhoneIssue.BAD_CHARACTERS),  # E.164 would drop the extension
        ("+254712345678;ext=5", PhoneIssue.BAD_CHARACTERS),
        ("tel:+254712345678", PhoneIssue.BAD_CHARACTERS),
        ("+254712345678" + "0" * 60, PhoneIssue.BAD_CHARACTERS),  # over the input cap
        ("+", PhoneIssue.NOT_A_NUMBER),
        ("()", PhoneIssue.NOT_A_NUMBER),
        ("+999 123456", PhoneIssue.UNKNOWN_COUNTRY_CODE),
        ("999", PhoneIssue.SHORT_OR_EMERGENCY),
        ("112", PhoneIssue.SHORT_OR_EMERGENCY),
    ],
)
def test_rejections_carry_a_stable_issue_code(raw, issue):
    result = inspect_phone(value=raw, region="KE")
    assert not result.ok
    assert result.issue == issue
    assert result.message


def test_too_short_and_too_long_are_told_apart():
    assert inspect_phone(value="+254 7123").issue == PhoneIssue.TOO_SHORT
    assert inspect_phone(value="+254 712345678901234").issue == PhoneIssue.TOO_LONG


def test_right_length_but_not_a_real_number_is_invalid_for_country():
    # Kenyan numbers don't start 254 3xx 3xx xxx - plausible length, no such prefix.
    result = inspect_phone(value="+254 300 000 000")
    assert not result.ok
    assert result.issue in (PhoneIssue.INVALID_FOR_COUNTRY, PhoneIssue.INVALID_LENGTH)


def test_rejection_messages_include_a_sample_number_when_it_helps():
    msg = inspect_phone(value="+254 7123").message
    assert "For example:" in msg
    assert "+254" in msg
    # ...and not when it wouldn't help
    assert "For example:" not in inspect_phone(value="abc").message


def test_rejected_numbers_still_expose_what_was_parsed():
    result = inspect_phone(value="+254 7123")
    assert result.info is not None
    assert result.info.country_code == 254
    assert result.info.is_valid is False
    assert result.e164 is None  # e164 only for accepted numbers


# --------------------------------------------------------------------- policies
def test_contact_accepts_landlines_but_mobile_policy_does_not():
    assert inspect_phone(value=KE_LANDLINE, policy=CONTACT).ok
    result = inspect_phone(value=KE_LANDLINE, policy=MOBILE)
    assert not result.ok
    assert result.issue == PhoneIssue.TYPE_NOT_ALLOWED
    assert result.message == "Enter a mobile phone number."


def test_mobile_policy_accepts_fixed_line_or_mobile_countries():
    us = _example_e164("US", Kind.FIXED_LINE_OR_MOBILE)
    result = inspect_phone(value=us, policy=MOBILE)
    assert result.ok
    assert result.info.number_type == "FIXED_LINE_OR_MOBILE"


def test_premium_rate_is_blocked_by_every_policy():
    premium = _example_e164("GB", Kind.PREMIUM_RATE)
    for policy in (CONTACT, MOBILE):
        result = inspect_phone(value=premium, policy=policy)
        assert not result.ok
        assert result.issue == PhoneIssue.TYPE_NOT_ALLOWED


def test_toll_free_is_fine_as_a_contact_number_but_not_a_mobile():
    toll_free = _example_e164("US", Kind.TOLL_FREE)
    assert inspect_phone(value=toll_free, policy=CONTACT).ok
    assert not inspect_phone(value=toll_free, policy=MOBILE).ok


# --------------------------------------------------------------------- info
def test_info_for_a_kenyan_mobile():
    info = inspect_phone(value=KE_MOBILE).info
    assert info.e164 == KE_MOBILE
    assert info.international == "+254 712 345678"
    assert info.national == "0712 345678"
    assert info.rfc3966 == "tel:+254-712-345678"
    assert info.country_code == 254
    assert info.national_number == "712345678"
    assert info.region_code == "KE"
    assert info.number_type == "MOBILE"
    assert info.is_possible and info.is_valid
    assert info.is_geographical is False
    assert info.can_be_dialled_internationally is True
    assert info.location == "Kenya"
    assert info.time_zones == ("Africa/Nairobi",)
    assert isinstance(info.original_carrier, str) and info.original_carrier  # name is data-driven


def test_landlines_are_geographical_and_shared_calling_codes_are_listed():
    assert inspect_phone(value=KE_LANDLINE).info.is_geographical is True
    us = inspect_phone(value=_example_e164("US", Kind.FIXED_LINE_OR_MOBILE)).info
    assert us.country_code == 1
    assert {"US", "CA"} <= set(us.regions_for_calling_code)


def test_bad_lang_falls_back_to_english_instead_of_erroring():
    for lang in ("", "../../etc", "english", None):
        assert inspect_phone(value=KE_MOBILE, lang=lang).info.location == "Kenya"


# --------------------------------------------------------------------- regions
def test_resolve_region_accepts_codes_in_any_case_and_skips_everything_else(settings):
    settings.PHONE_DEFAULT_REGION = "KE"
    assert resolve_region("ug") == "UG"
    assert resolve_region(" us ") == "US"
    assert resolve_region("Kenya") == "KE"  # free text -> default
    assert resolve_region(None, "ZZ", "Uganda", "TZ") == "TZ"  # first *real* candidate
    assert resolve_region() == "KE"


def test_resolve_region_fails_loudly_on_a_bad_setting(settings):
    settings.PHONE_DEFAULT_REGION = "NOPE"
    with pytest.raises(ImproperlyConfigured):
        resolve_region()


def test_supported_regions_lists_calling_codes():
    regions = dict(supported_regions())
    assert regions["KE"] == 254
    assert regions["US"] == 1
    assert list(regions) == sorted(regions)


def test_every_regions_example_numbers_are_valid_and_round_trip():
    """Whole-metadata sanity check: our parser agrees with libphonenumber's own examples."""
    checked = 0
    for region, _code in supported_regions():
        for kind in (Kind.MOBILE, Kind.FIXED_LINE):
            number = phonenumbers.example_number_for_type(region, kind)
            if number is None:
                continue
            e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
            info = inspect_phone(value=e164).info
            assert info is not None and info.is_valid, (region, e164)
            assert info.e164 == e164
            checked += 1
    assert checked > 300


# --------------------------------------------------------------------- formatting
def test_format_styles():
    assert format_phone(value="0712345678", region="KE", style="e164") == KE_MOBILE
    assert format_phone(value=KE_MOBILE) == "+254 712 345678"
    assert format_phone(value=KE_MOBILE, style="national") == "0712 345678"
    assert format_phone(value=KE_MOBILE, style="rfc3966") == "tel:+254-712-345678"
    assert format_phone(value=KE_MOBILE, style="out_of_country", from_region="US") == (
        "011 254 712 345678"
    )
    assert format_phone(value=KE_MOBILE, style="mobile_dialing", from_region="KE") == "0712345678"


def test_format_never_raises_and_returns_unparsable_text_as_is():
    assert format_phone(value="not a number") == "not a number"
    assert format_phone(value="") == ""
    assert format_phone(value=None) == ""


def test_example_number():
    sample = example_number(region="KE")
    assert sample and sample.startswith("+254")
    assert normalize_phone(value=sample)  # the sample itself must pass our own rules
    assert example_number(region="KE", kind="fixed_line")
    assert example_number(region="ZZ") is None
    assert example_number(region="KE", kind="nonsense") is None


# --------------------------------------------------------------------- errors & validator
def test_normalize_raises_the_projects_validation_error_with_issue_and_field():
    with pytest.raises(PhoneValidationError) as exc:
        normalize_phone(value="abc")
    assert isinstance(exc.value, AppValidationError)  # existing handlers keep working
    assert exc.value.code == ErrorCode.VALIDATION_ERROR
    assert exc.value.field == "phone"
    assert exc.value.issue == PhoneIssue.BAD_CHARACTERS

    with pytest.raises(PhoneValidationError) as exc:
        normalize_phone(value="abc", field="company_phone")
    assert exc.value.field == "company_phone"


def test_django_validator_for_model_fields():
    assert validate_phone_number("+254712345678") == "+254712345678"
    assert validate_phone_number("0712345678") == "0712345678"  # legacy national format
    assert validate_phone_number("") == ""  # blank fields stay optional
    assert validate_phone_number(None) is None
    with pytest.raises(ValidationError) as exc:
        validate_phone_number("12345")
    assert exc.value.code == "invalid_phone"
