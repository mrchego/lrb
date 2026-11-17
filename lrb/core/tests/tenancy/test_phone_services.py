"""Phone numbers through the real services and GraphQL schema.

Lives next to the tenancy suite so it can use the `w` fixture (two real companies, each
with country "KE"). The pure rules are covered, without a database, in tests/phone/.
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser

from lrb.accounts.services.create_user import create_user
from lrb.accounts.services.update_user import update_user
from lrb.company.services.update_company import update_company
from lrb.core.exceptions import AppValidationError

from .conftest import PASSWORD, _uid


def _make_user(company, **kwargs):
    return create_user(
        email=f"{_uid('p')}@example.test",
        first_name="Phone",
        last_name="Tester",
        password=PASSWORD,
        company=company,
        **kwargs,
    )


# ------------------------------------------------------------------ users
def test_create_user_stores_the_e164_form(w):
    user = _make_user(w.a, phone="0712 345 678")  # national format, read under the company's KE
    assert user.phone == "+254712345678"


def test_create_user_without_a_phone_is_still_fine(w):
    assert _make_user(w.a).phone == ""


@pytest.mark.parametrize("bad", ["abc", "12345", "+254 7123", "999", "+1 800 FLOWERS"])
def test_create_user_rejects_a_bad_phone_on_the_phone_field(w, bad):
    with pytest.raises(AppValidationError) as exc:
        _make_user(w.a, phone=bad)
    assert exc.value.field == "phone"


def test_update_user_normalizes_and_blank_clears(w):
    user = _make_user(w.a)

    updated = update_user(user_id=str(user.id), company_id=str(w.a.id), phone="+254 712 345 678")
    assert updated.phone == "+254712345678"

    cleared = update_user(user_id=str(user.id), company_id=str(w.a.id), phone="")
    assert cleared.phone == ""


def test_update_user_rejects_a_bad_phone_and_keeps_the_old_one(w):
    user = _make_user(w.a, phone="+254712345678")
    with pytest.raises(AppValidationError) as exc:
        update_user(user_id=str(user.id), company_id=str(w.a.id), phone="nope")
    assert exc.value.field == "phone"
    user.refresh_from_db()
    assert user.phone == "+254712345678"


def test_resubmitting_a_legacy_national_number_upgrades_it_to_e164(w):
    user = _make_user(w.a)
    type(user).objects.filter(pk=user.pk).update(phone="0712345678")  # as stored before this change
    updated = update_user(user_id=str(user.id), company_id=str(w.a.id), phone="0712345678")
    assert updated.phone == "+254712345678"


# ------------------------------------------------------------------ companies
def test_update_company_normalizes_its_phone(w):
    company = update_company(company_id=w.a.id, phone="0712 345 678")
    assert company.phone == "+254712345678"


@pytest.mark.parametrize("bad", ["", "abc", "+254 7123"])
def test_update_company_rejects_a_bad_phone(w, bad):
    with pytest.raises(AppValidationError) as exc:
        update_company(company_id=w.a.id, phone=bad)
    assert exc.value.field == "phone"


# ------------------------------------------------------------------ GraphQL
INSPECT = """
query($phone: String!, $requirement: PhoneRequirement) {
  inspectPhone(phone: $phone, requirement: $requirement) {
    ok issue message
    info { e164 international countryCode regionCode numberType isValid location timeZones }
  }
}
"""


def test_inspect_phone_returns_the_full_picture(w):
    result = w.run(w.owner_a, INSPECT, {"phone": "0712 345 678", "requirement": "MOBILE"})
    assert result.errors is None
    data = result.data["inspectPhone"]
    assert data["ok"] is True
    assert data["info"]["e164"] == "+254712345678"
    assert data["info"]["international"] == "+254 712 345678"
    assert data["info"]["countryCode"] == 254
    assert data["info"]["regionCode"] == "KE"
    assert data["info"]["numberType"] == "MOBILE"
    assert data["info"]["timeZones"] == ["Africa/Nairobi"]


def test_inspect_phone_reports_rejections_as_data_not_errors(w):
    result = w.run(w.owner_a, INSPECT, {"phone": "+254202345678", "requirement": "MOBILE"})
    assert result.errors is None
    data = result.data["inspectPhone"]
    assert data["ok"] is False
    assert data["issue"] == "type_not_allowed"
    assert data["info"]["numberType"] == "FIXED_LINE"  # still described, so the UI can explain


def test_inspect_phone_needs_a_signed_in_user(w):
    result = w.run(AnonymousUser(), INSPECT, {"phone": "+254712345678"})
    assert result.errors
