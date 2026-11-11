"""The only place cache keys are built.

Every key starts with a namespace and a company id, so two companies can never
share a key. Django's KEY_FUNCTION (django_tenants.cache.make_key) adds the
schema name on top of this, but it reads the *current* database connection,
which is wrong in places like Celery tasks. Putting the company id into the
key itself means correctness does not depend on connection state.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable, Mapping

from lrb.core.tenancy import get_current_tenant, require_company_id

if TYPE_CHECKING:
    from lrb.core.cache.policies import CachePolicy

# Letters, digits, underscore, dot, hyphen. No ":" (our separator), no spaces.
# A part containing ":" could make ("a:b",) collide with ("a", "b").
_SAFE_PART = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def current_tenant_scope() -> str:
    """Company id of the schema active right now. Fails closed on the public schema."""
    return str(get_current_tenant().pk)


def build_key(*, namespace: str, company_id, parts: Iterable[object]) -> str:
    company = require_company_id(company_id)
    pieces = [namespace, company, *(str(p) for p in parts)]
    for piece in pieces:
        if not _SAFE_PART.match(piece):
            raise ValueError(f"Unsafe cache key part: {piece!r}")
    return ":".join(pieces)


def policy_key(*, policy: "CachePolicy", company_id, params: Mapping[str, str] | None = None) -> str:
    """Key for one cached value of a policy. Params are sorted so order never matters."""
    parts = [f"{name}-{value}" for name, value in sorted((params or {}).items())]
    return build_key(namespace=policy.name, company_id=company_id, parts=parts)


def lock_key(key: str) -> str:
    return f"{key}:lock"


def refresh_lock_key(key: str) -> str:
    return f"{key}:refresh"
