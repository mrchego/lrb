from __future__ import annotations

from typing import TYPE_CHECKING

from lrb.accounts.selectors.count_active_founders import count_active_founders
from lrb.core.exceptions import ApplicationError, ErrorCode

if TYPE_CHECKING:
    from lrb.accounts.models import User


def assert_not_last_founder(
    *, user: User, company_id: str, action: str = "modified"
) -> None:
    """Guard every destructive action against a founder-tier account.

    - The founder is immune to everyone, including co-founders.
    - A co-founder has the founder's powers, so another founder-tier user may
      act on them, but never the last active one (defensive: the founder is
      already protected, so this only fires on legacy / corrupted data).
    """
    if not user.has_founder_access:
        return

    if user.is_founder:
        raise ApplicationError(
            f"The founder's account cannot be {action}.",
            code=ErrorCode.CANNOT_MODIFY_FOUNDER,
        )

    remaining = count_active_founders(
        company_id=company_id, exclude_ids=[str(user.id)]
    )
    if remaining == 0:
        raise ApplicationError(
            f"This is the last active founder of the company and cannot be {action}.",
            code=ErrorCode.LAST_FOUNDER,
        )