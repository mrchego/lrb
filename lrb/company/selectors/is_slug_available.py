from lrb.company.models import Company
from lrb.core.exceptions import AppValidationError
from lrb.core.validators.tenant_slug import validate_tenant_slug


def is_slug_available(*, slug: str) -> bool:
    try:
        slug = validate_tenant_slug(value=slug)
    except AppValidationError:
        return False
    return not Company.objects.filter(slug=slug).exists()