"""The only place rate-limit Redis keys are built (same rules as lrb.core.cache.keys).

Shape:  rl:<kind>:<company>:<policy>:<layer>:<identity>
  kind     b bucket | w window | p penalty | c concurrency
  company  the company id, or "platform" on the public site. Never from client input.
Identities that come from clients (IP, e-mail) are keyed-hashed, so keys stay short and
safe, hold no personal data, and an attacker cannot craft colliding values.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from django.conf import settings

_SAFE_PART = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def hash_identity(value: str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return "h" + digest[:24]


def build(kind: str, company: str, policy: str, layer: str, identity: str) -> str:
    parts = ["rl", kind, company, policy, layer, identity]
    for p in parts:
        if not _SAFE_PART.match(p):
            raise ValueError(f"Unsafe rate-limit key part: {p!r}")
    return ":".join(parts)
