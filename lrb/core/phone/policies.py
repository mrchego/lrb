"""Which *kinds* of number a given field accepts.

libphonenumber classifies every valid number (mobile, fixed line, premium rate...).
A policy is just the set of kinds a field allows, plus the message shown otherwise.
Pick one per field in the service layer; to change a rule, change it here once.
"""
from __future__ import annotations

from dataclasses import dataclass

from phonenumbers import PhoneNumberType as Kind


@dataclass(frozen=True)
class PhonePolicy:
    name: str
    allowed: frozenset[int]
    rejection_message: str

    def allows(self, number_type: int) -> bool:
        return number_type in self.allowed


# A person or business you might ring. Blocks the kinds that cost the caller extra or
# that are not really "a phone": premium-rate (toll-fraud / SMS-pumping vector),
# shared-cost, pagers and voicemail access numbers.
# UNKNOWN stays allowed: some countries' metadata can't classify a number that is
# otherwise perfectly valid.
CONTACT = PhonePolicy(
    name="contact",
    allowed=frozenset(
        {
            Kind.FIXED_LINE,
            Kind.MOBILE,
            Kind.FIXED_LINE_OR_MOBILE,
            Kind.TOLL_FREE,
            Kind.VOIP,
            Kind.PERSONAL_NUMBER,
            Kind.UAN,
            Kind.UNKNOWN,
        }
    ),
    rejection_message=(
        "Premium-rate, shared-cost, pager and voicemail numbers can't be used here."
    ),
)

# Must be able to receive an SMS / WhatsApp message (the planned verification step).
# FIXED_LINE_OR_MOBILE is how libphonenumber labels countries (like the US) where the
# two can't be told apart from the number alone. VoIP is excluded: most messaging
# platforms don't deliver to it.
MOBILE = PhonePolicy(
    name="mobile",
    allowed=frozenset({Kind.MOBILE, Kind.FIXED_LINE_OR_MOBILE, Kind.UNKNOWN}),
    rejection_message="Enter a mobile phone number.",
)

BY_NAME: dict[str, PhonePolicy] = {p.name: p for p in (CONTACT, MOBILE)}
