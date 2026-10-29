from lrb.company.models.company import Company

from lrb.core.exceptions import BusinessRuleViolationError, ErrorCode


def validate_company_email_unique(*, value, instance=None):
    qs = Company.objects.filter(email=value)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise BusinessRuleViolationError(message="A company with this email already exists.", code=ErrorCode.COMPANY_ALREADY_EXISTS)
    return value
