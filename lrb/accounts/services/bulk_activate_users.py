from __future__ import annotations
from email import message
from typing import Iterable
from django.db import transaction
from lrb.core.services.bulk_result import BulkActionResult
from lrb.core.exceptions import ApplicationError
from lrb.accounts.selectors.get_users_by_ids import get_users_by_ids

def bulk_activate_users(*, user_ids: Iterable[str], company_id:str) -> BulkActionResult:
    result = BulkActionResult()
    normalized_ids = [str(uid) for uid in user_ids]
    users = list(get_users_by_ids(user_ids=normalized_ids, company_id=company_id))
    found_ids = {str(u.id) for u in users}

    for user in users:
        uid = str(user.id)
        if user.is_active:
            result.add_failure(user_id=uid, reason="Already active")
            continue
        
        try:
            with transaction.atomic():
                user.is_active = True
                user.save(update_fields=["is_active"])
            result.add_success(user_id=uid)
        except Exception as e:
            result.add_failure(user_id=uid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(user_id=missing, reason="Use not found in company")

    return result
