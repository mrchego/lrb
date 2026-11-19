import re

from lrb.core.exceptions import AppValidationError

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_brand_color(*, value: str, field: str = "brand_color") -> str:
    """Return the colour as upper-case ``#RRGGBB``.

    An empty value is allowed and means "use the default colours" (this is how an owner
    resets the theme). Anything else must be exactly ``#`` plus six hex digits, so the
    stored value can never carry CSS or markup into the pages that render it.
    """
    cleaned = (value or "").strip()
    if cleaned == "":
        return ""
    if not _HEX_COLOR.match(cleaned):
        raise AppValidationError(
            message="Choose a valid color, like #2563EB.", field=field
        )
    return cleaned.upper()