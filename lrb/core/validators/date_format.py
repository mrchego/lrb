from lrb.core.exceptions import AppValidationError

ALLOWED_DATE_FORMATS = ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY")


def validate_date_format(*, value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned not in ALLOWED_DATE_FORMATS:
        raise AppValidationError(
            message="Choose a supported date format.", field="date_format"
        )
    return cleaned
