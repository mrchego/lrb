from lrb.core.exceptions import AppValidationError
from lrb.core.validators.brand_color import validate_brand_color

# Keep these in step with lib/theme-engine.ts on the frontend.
SURFACES = ("neutral", "warm", "cool", "brand")
INTENSITIES = ("subtle", "soft", "rich")
SIDEBARS = ("match", "tinted", "dark", "brand")
RADII = ("sharp", "default", "soft", "round")
CHARTS = ("varied", "shades")
COLOR_SLOTS = ("background", "card", "sidebar", "foreground", "border")
MODES = ("light", "dark")

_CHOICES = (
    ("surface", SURFACES),
    ("intensity", INTENSITIES),
    ("sidebar", SIDEBARS),
    ("radius", RADII),
    ("charts", CHARTS),
)


def _invalid(message: str = "Appearance settings are not valid."):
    return AppValidationError(message=message, field="appearance")


def validate_appearance(*, value) -> dict:
    """Return a clean, minimal appearance dict (``{}`` means "default look").

    Only known keys and values are accepted: every choice must be one of the allowed
    options and every custom color a ``#RRGGBB`` string. Nothing else is stored, so the
    value can never carry CSS or markup into the pages that render it. Readability is
    enforced when the theme is rendered, so a stored value can never make text unreadable.
    """
    if value in (None, "", {}):
        return {}
    if not isinstance(value, dict):
        raise _invalid()

    unknown = set(value) - {"surface", "intensity", "sidebar", "radius", "charts", "overrides"}
    if unknown:
        raise _invalid()

    clean: dict = {}
    for key, allowed in _CHOICES:
        if key in value and value[key] is not None:
            if value[key] not in allowed:
                raise _invalid(f"Choose a supported {key} option.")
            clean[key] = value[key]

    overrides = value.get("overrides") or {}
    if not isinstance(overrides, dict) or set(overrides) - set(MODES):
        raise _invalid()

    clean_overrides: dict = {}
    for mode in MODES:
        slots = overrides.get(mode) or {}
        if not isinstance(slots, dict) or set(slots) - set(COLOR_SLOTS):
            raise _invalid()
        picked = {}
        for slot, color in slots.items():
            if not isinstance(color, str):
                raise _invalid()
            cleaned = validate_brand_color(value=color, field="appearance")
            if cleaned:
                picked[slot] = cleaned
        if picked:
            clean_overrides[mode] = picked
    if clean_overrides:
        clean["overrides"] = clean_overrides

    return clean