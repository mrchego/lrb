from django.core.exceptions import ValidationError

def validate_company_name(*, value):
    if len(value.strip()) < 2:
        raise ValidationError(message="Company name must be at least 2 characters long.")
    return value