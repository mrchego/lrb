from __future__ import annotations

from typing import Optional

from lrb.core.phone import CONTACT, normalize_phone, resolve_region


def normalize_user_phone(*, phone: Optional[str], company=None) -> str:
    """The one place that decides how a *user's* phone is validated and stored.

    - Empty / blank -> "" (a user's phone is optional, and sending "" clears it).
    - Anything else -> E.164, or AppValidationError(field="phone").

    The company's country is only used to read numbers typed without a "+"
    (0712 345 678); a number that starts with "+" never depends on it.

    Policy is CONTACT (any real number except premium-rate/pager/etc.). When the
    WhatsApp/SMS verification step lands, switch this one line to `policy=MOBILE`
    - but first decide what happens to users who already have a landline stored,
    because the profile form re-submits the stored phone on every save.
    """
    if phone is None or not phone.strip():
        return ""
    return normalize_phone(
        value=phone,
        region=resolve_region(getattr(company, "country", None)),
        policy=CONTACT,
        field="phone",
    )
