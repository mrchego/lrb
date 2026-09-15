from typing import Optional

from lrb.accounts.models import User


def get_login_attempt(*, user:User, since:Optional[int] = None) -> List:
    return []