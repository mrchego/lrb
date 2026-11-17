from lrb.company.cache_policies import COMPANY_SETTINGS
from lrb.core.cache import cached_read
from lrb.core.exceptions import ApplicationError, ErrorCode


def get_cached_company_settings(*, company_id: str) -> dict:
    """The company's display settings, served from the cache when possible.

    Same failure as get_company_settings: no settings row is a COMPANY_NOT_FOUND error.
    """
    snapshot = cached_read(policy=COMPANY_SETTINGS, company_id=company_id)
    if snapshot is None:
        raise ApplicationError(
            message="Company settings not found.", code=ErrorCode.COMPANY_NOT_FOUND
        )
    return snapshot