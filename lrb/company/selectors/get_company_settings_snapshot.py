from typing import Optional

from lrb.company.models.settings import CompanySettings
from lrb.core.tenancy import require_company_id

# Exactly what the cache may hold. An explicit list (not "every column") so that a field added
# to CompanySettings later is never cached by accident; the test beside this fails until someone
# decides to add it here or to exclude it on purpose.
SNAPSHOT_FIELDS = ("timezone", "currency", "language", "date_format", "theme")


def get_company_settings_snapshot(*, company_id: str) -> Optional[dict]:
    """Plain-data copy of one company's display settings, for the cache.

    Returns a dict of strings (JSON-friendly, as the cache requires), or None if the company has
    no settings row. Called by cached_read as loader(company_id=...).
    """
    return (
        CompanySettings.objects.filter(company_id=require_company_id(company_id))
        .values(*SNAPSHOT_FIELDS)
        .first()
    )