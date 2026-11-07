"""Which timezones exist, and which one a company uses."""
from __future__ import annotations

import logging
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "UTC"

# Legacy aliases and fixed-offset oddities. Valid for Python, confusing for people.
_EXCLUDED_PREFIXES = (
    "Etc/", "SystemV/", "posix/", "right/",
    "US/", "Canada/", "Brazil/", "Chile/", "Mexico/",
)


@lru_cache(maxsize=1)
def timezone_choices() -> frozenset[str]:
    return frozenset(
        name
        for name in available_timezones()
        if name == DEFAULT_TIMEZONE
        or ("/" in name and not name.startswith(_EXCLUDED_PREFIXES))
    )


def get_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)  # zoneinfo caches instances itself


def get_company_timezone(*, company_id) -> ZoneInfo:
    """The company's timezone, read fresh from the database on every call.

    Deliberately NOT cached: the project cache is per-process (LocMemCache), so
    after the owner changes the timezone, other workers would keep serving the
    old one. One primary-key-indexed read per request is the cheaper price.

    Fails safe: a missing row or a corrupt name logs an error and falls back to
    UTC, because a time-zone problem must never turn into a 500 on every request.
    """
    from lrb.company.models.settings import CompanySettings  # lazy: avoid import cycle

    name = (
        CompanySettings.objects.filter(company_id=company_id)
        .values_list("timezone", flat=True)
        .first()
    )
    if not name:
        logger.error("No CompanySettings timezone for company %s; using UTC", company_id)
        return get_zone(DEFAULT_TIMEZONE)
    try:
        return get_zone(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.error("Invalid timezone %r for company %s; using UTC", name, company_id)
        return get_zone(DEFAULT_TIMEZONE)


# Let's Understand timezone_choices
# The big picture
# This function answers one question:

# "Which timezone names should we offer the user to pick from?"

# It returns a frozen set of timezone name strings — like {"Africa/Nairobi", "Europe/London", "America/New_York", ...}.

# It's the list of choices you'd put in a dropdown menu: "Pick your company's timezone."

# But it's not just any timezone name. It carefully filters the raw list from Python to keep only the ones that make sense for users to pick.

# The signature
# python
# def timezone_choices() -> frozenset[str]:
# timezone_choices — the function's name

# -> frozenset[str] — "I will return a frozenset of strings"

# What is a frozenset?
# A set in Python is a collection of unique items — no duplicates, and order doesn't matter:

# python
# {"Africa/Nairobi", "Europe/London", "Asia/Tokyo"}
# A frozenset is a set that's immutable — once created, nobody can add or remove items. Same idea as the @dataclass(frozen=True) from before.

# Why frozenset here?

# Safety — callers can't accidentally modify the shared result.

# Cacheable — immutable values can be stored in caches safely.

# Hashable — frozensets can themselves be used as keys or stored in other sets.

# The [str] part just says: "every item inside is a string."

# The decorator: @lru_cache(maxsize=1)
# python
# @lru_cache(maxsize=1)
# def timezone_choices() -> frozenset[str]:
# This is a label above the function that changes its behavior. Let's break it down.

# What is lru_cache?
# LRU = Least Recently Used. It's a caching decorator from functools.

# What it does: after the function runs once, Python remembers the result. Next time you call the function, Python doesn't re-run it — it just hands back the cached result.

# Why? Because available_timezones() reads from disk (the OS's timezone database). That's slow. Doing it every time someone opens a dropdown would be wasteful.

# What does maxsize=1 mean?
# It means: "only cache one result."

# Why only one? Because this function takes no arguments. There's only one possible answer. So one cached result is all we need.

# The effect
# python
# timezone_choices()   # first call — computes the whole set (slow)
# timezone_choices()   # second call — instant, returns cached set
# timezone_choices()   # third call — instant, same cached set
# All three calls return the exact same frozenset object — not a fresh copy. That's why frozenset matters: since callers all share the cached result, it must be immutable so nobody can corrupt it.

# Why this matters: building the list might take milliseconds — fine once, painful hundreds of times. Caching makes it a one-time cost.

# The body: a set comprehension
# python
# return frozenset(
#     name
#     for name in available_timezones()
#     if name == DEFAULT_TIMEZONE
#     or ("/" in name and not name.startswith(_EXCLUDED_PREFIXES))
# )
# This is a set comprehension — a compact way to build a set. It reads:

# "For each name in all available timezones, keep it only if it passes the test. Then wrap the result in a frozenset."

# Let's translate it into a plain loop, which is easier to read:

# python
# result = []
# for name in available_timezones():       # go through every raw timezone name
#     if name == DEFAULT_TIMEZONE:         # keep the default, always
#         result.append(name)
#     elif "/" in name and not name.startswith(_EXCLUDED_PREFIXES):
#         result.append(name)              # keep "Region/City" names, except excluded
# return frozenset(result)
# Same thing. The comprehension is just shorter.

# Let's walk through the pieces.

# available_timezones()
# This comes from Python's zoneinfo module. It returns all timezone names the OS knows about — the raw list.

# It looks like this (abbreviated):

# python
# {
#     "Africa/Nairobi",
#     "America/New_York",
#     "Europe/London",
#     "UTC",
#     "GMT",
#     "EST",
#     "MST",
#     "Factory",
#     "posixrules",
#     "Africa/Abidjan",
#     "US/Eastern",
#     "Etc/GMT+5",
#     ...
# }
# That's hundreds of names. But not all of them should be shown to users.

# Why? Because the raw list contains:

# Deprecated aliases — US/Eastern is an old name for America/New_York. We don't want users picking the old one.

# Technical entries — Factory, posixrules are internal system entries.

# Abbreviations — EST, MST are ambiguous (an "EST" could be Australian Eastern or US Eastern!). Not safe to show.

# Etc/GMT+5 style names — confusing reversed offsets. Etc/GMT+5 is actually UTC−5. So the + means the opposite of what you'd expect. Terrible UX.

# The function filters all of this cruft out.

# Filter 1: name == DEFAULT_TIMEZONE
# python
# if name == DEFAULT_TIMEZONE
# "Always keep the default timezone — even if it wouldn't pass the other filters."

# Why? Because DEFAULT_TIMEZONE might be something like "UTC" — which doesn't contain a slash and would otherwise be filtered out by rule 2. But we still need to offer it, because it's the app's default.

# Think of it like: "Even though 'UTC' doesn't look like a normal Region/City name, we still want to offer it."

# What is DEFAULT_TIMEZONE? A constant defined elsewhere in the file — the timezone your app falls back to. Probably "Africa/Nairobi" or "UTC".

# Filter 2: "/" in name and not name.startswith(_EXCLUDED_PREFIXES)
# python
# or ("/" in name and not name.startswith(_EXCLUDED_PREFIXES))
# This is the main filter. Two conditions must both be true:

# Condition A: "/" in name

# "The name must contain a slash."

# Why? Because the canonical timezone format is Region/City:

# ✅ "Africa/Nairobi" — clear and unambiguous

# ✅ "America/New_York" — clear

# ✅ "Europe/London" — clear

# ❌ "EST" — no slash, ambiguous

# ❌ "UTC" — no slash (but might still be added via DEFAULT_TIMEZONE)

# ❌ "Factory" — no slash, technical

# ❌ "posixrules" — no slash, internal

# So "/" in name is a simple way of saying: "keep only the properly-formatted Region/City names."

# It's a crude but effective filter. The slash requirement eliminates most of the junk.

# Why not be more precise? Because there's no perfect rule. A slash check is fast, simple, and gets you 95% of the way. The _EXCLUDED_PREFIXES handles the rest.

# Condition B: not name.startswith(_EXCLUDED_PREFIXES)

# "The name must not start with any of the excluded prefixes."

# What's _EXCLUDED_PREFIXES? A tuple of prefixes to reject. Something like:

# python
# _EXCLUDED_PREFIXES = ("Etc/", "SystemV/", "US/", "Canada/", "Mexico/", "Brazil/", "Chile/")
# Let's see why each one would be excluded:

# Prefix	Examples	Why exclude?
# "Etc/"	Etc/GMT+5, Etc/UTC	Confusing — Etc/GMT+5 is actually UTC−5!
# "US/"	US/Eastern, US/Pacific	Legacy aliases — use America/... instead
# "SystemV/"	SystemV/EST5	Obsolete
# "Canada/", "Mexico/"	Canada/Eastern, Mexico/General	Legacy aliases — use America/...
# The idea: "prefer the modern, canonical names; hide the old or confusing ones."

# So if _EXCLUDED_PREFIXES = ("Etc/", "US/"):

# "Etc/GMT+5" → excluded (starts with "Etc/")

# "US/Eastern" → excluded (starts with "US/")

# "Africa/Nairobi" → kept (starts with "Africa/", which isn't excluded)

# The startswith trick
# python
# name.startswith(_EXCLUDED_PREFIXES)
# Python's .startswith() accepts a tuple of prefixes. It returns True if the string starts with any of them. So this one call checks them all at once. Clean.

# Putting the filter together
# A name is kept if:

# It is the default timezone, OR

# It contains a slash AND doesn't start with any excluded prefix