"""Who is making this request? Everything here comes from the server side."""
from __future__ import annotations

import ipaddress

from django.conf import settings

PLATFORM = "platform"


def company_scope(request) -> str:
    """Company id of the host being served; "platform" for the public site."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        from django.db import connection
        tenant = getattr(connection, "tenant", None)
    public = getattr(settings, "PUBLIC_SCHEMA_NAME", "public")
    if tenant is None or getattr(tenant, "schema_name", public) == public:
        return PLATFORM
    return str(tenant.pk)


def client_ip(request) -> str:
    """Client address. X-Forwarded-For is only believed for the number of proxy hops
    you declare in RATE_LIMIT_TRUSTED_PROXY_COUNT; each trusted proxy appends the
    address it saw, so the real client is the Nth entry from the RIGHT. Anything a
    client puts at the left of the header is ignored."""
    remote = request.META.get("REMOTE_ADDR", "")
    hops = int(getattr(settings, "RATE_LIMIT_TRUSTED_PROXY_COUNT", 0))
    candidate = remote
    if hops > 0:
        parts = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(parts) >= hops:
            candidate = parts[-hops]
    return _normalise(candidate) or _normalise(remote) or "unknown"


def _normalise(value: str) -> str | None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address)  # a /64 is one "host"
    return str(ip)


def actor_id(request) -> str | None:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"u-{user.pk}"
    return None


def normalise_subject(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()[:254]
    return value or None
