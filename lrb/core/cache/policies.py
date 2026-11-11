"""Every cached type is declared once, as a CachePolicy, in its app's cache_policies.py.

Why a registry instead of passing a TTL at each call site:
  * freshness rules live in one reviewable place;
  * the rules are validated at startup (a bad policy stops the app booting);
  * the background refresh task can find a policy (and its loader) by name;
  * a test can prove that no app caches outside the platform.

A new app joins by adding `<app>/cache_policies.py`. Nothing else to register:
CoreConfig.ready() imports that file from every installed app.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import autodiscover_modules


class Consistency(str, Enum):
    # Security-relevant data (permissions). Never served after it expires.
    STRICT = "strict"
    # Read models (dashboard stats). May be served slightly stale while a
    # background task refreshes it.
    BOUNDED_STALE = "bounded_stale"


_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_OWNER = re.compile(r"^[a-z][a-z0-9_]*$")
_DOTTED_PATH = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")

MAX_TTL_SECONDS = {Consistency.STRICT: 300, Consistency.BOUNDED_STALE: 3600}
MAX_STALE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class CachePolicy:
    name: str  # "dashboard.product_stats": "<owner>.<what>", used as the key namespace
    owner: str  # the domain that owns it; must be the first part of `name`
    consistency: Consistency
    ttl: int  # seconds the value counts as fresh
    description: str  # one line: what is cached and why it is safe to cache
    stale_ttl: int = 0  # extra seconds a stale value may be served (BOUNDED_STALE only)
    cache_missing: bool = False  # remember "not found" too (negative caching)
    missing_ttl: int = 30  # how long "not found" is remembered
    # Dotted path of the selector that computes the value, called as
    # loader(company_id=..., **params). Required for cached_read policies.
    loader: str | None = None

    def __post_init__(self) -> None:
        def bad(message: str):
            raise ImproperlyConfigured(f"CachePolicy {self.name!r}: {message}")

        if not isinstance(self.name, str) or not _NAME.match(self.name):
            bad("name must look like 'owner.thing' (lowercase letters, digits, _).")
        if not isinstance(self.owner, str) or not _OWNER.match(self.owner):
            bad("owner must be lowercase letters, digits and _.")
        if not self.name.startswith(self.owner + "."):
            bad(f"name must start with the owner ({self.owner!r}.).")
        if not isinstance(self.consistency, Consistency):
            bad("consistency must be a Consistency member.")
        if not isinstance(self.description, str) or not self.description.strip():
            bad("description is required.")
        if type(self.ttl) is not int or not 1 <= self.ttl <= MAX_TTL_SECONDS[self.consistency]:
            bad(f"ttl must be 1..{MAX_TTL_SECONDS[self.consistency]} seconds for {self.consistency.value}.")
        if type(self.stale_ttl) is not int or not 0 <= self.stale_ttl <= MAX_STALE_TTL_SECONDS:
            bad(f"stale_ttl must be 0..{MAX_STALE_TTL_SECONDS} seconds.")
        if self.consistency is Consistency.STRICT and self.stale_ttl:
            bad("STRICT data must never be served stale (stale_ttl must be 0).")
        if self.loader is not None and (
            not isinstance(self.loader, str) or not _DOTTED_PATH.match(self.loader)
        ):
            bad("loader must be a dotted path like 'lrb.app.selectors.thing.get_thing'.")
        if self.stale_ttl and not self.loader:
            bad("a background refresh needs a loader.")
        if self.cache_missing and (type(self.missing_ttl) is not int or not 1 <= self.missing_ttl <= self.ttl):
            bad("missing_ttl must be between 1 and ttl when cache_missing is on.")


_REGISTRY: dict[str, CachePolicy] = {}


def register_policy(policy: CachePolicy) -> CachePolicy:
    existing = _REGISTRY.get(policy.name)
    if existing is not None and existing != policy:
        raise ImproperlyConfigured(f"Cache policy {policy.name!r} is already registered differently.")
    _REGISTRY[policy.name] = policy
    return policy


def get_policy(name: str) -> CachePolicy:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ImproperlyConfigured(
            f"Unknown cache policy {name!r}. Declare it in an app's cache_policies.py."
        ) from None


def all_policies() -> list[CachePolicy]:
    return sorted(_REGISTRY.values(), key=lambda p: p.name)


def autodiscover_cache_policies() -> None:
    """Import `cache_policies.py` from every installed app (a missing file is fine)."""
    autodiscover_modules("cache_policies")
