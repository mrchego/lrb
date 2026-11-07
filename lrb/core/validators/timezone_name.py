from lrb.core.clock.zones import timezone_choices
from lrb.core.exceptions import AppValidationError


def validate_timezone_name(*, value: str) -> str:
    """Return the cleaned IANA timezone name or raise.

    We check against an allow-list built from the system tz database instead of
    just calling ZoneInfo(value): that way junk such as "EST5EDT", "Etc/GMT+5"
    or anything path-like never reaches the database, and the list the frontend
    shows is exactly the list the backend accepts.
    """
    cleaned = (value or "").strip()
    if cleaned not in timezone_choices():
        raise AppValidationError(
            message="Choose a valid timezone, e.g. Africa/Nairobi.",
            field="timezone",
        )
    return cleaned
