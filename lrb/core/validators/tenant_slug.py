import re

from lrb.core.exceptions import AppValidationError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}[a-z0-9]$")  # 3-42 chars
RESERVED = {
    "public", "www", "api", "admin", "app", "static", "media", "mail", "root",
    "support", "status", "dashboard", "login", "register", "localhost",
}


def validate_tenant_slug(*, value: str) -> str:
    slug = (value or "").strip().lower()
    if not SLUG_RE.match(slug):
        raise AppValidationError(
            message="Use 3-42 lowercase letters, numbers or hyphens (no leading/trailing hyphen).",
            field="slug",
        )
    if slug in RESERVED:
        raise AppValidationError(message="This workspace address is reserved.", field="slug")
    return slug


def schema_name_for(*, slug: str) -> str:
    # Hyphens are the only difference, and underscores are banned in slugs, so this is one-to-one.
    return "t_" + slug.replace("-", "_")