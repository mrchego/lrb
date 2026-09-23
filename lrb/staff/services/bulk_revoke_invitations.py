from django.db import transaction

from lrb.core.services.bulk_result import BulkActionResult
from lrb.staff.models import Invitation
from lrb.staff.selectors.get_invitations_by_ids import get_invitations_by_ids


def bulk_revoke_invitations(*, invitation_ids, company_id):
    result = BulkActionResult()
    normalized_ids = [str(iid) for iid in invitation_ids]
    invitations = list(
        get_invitations_by_ids(invitation_ids=normalized_ids, company_id=company_id)
    )
    found_ids = {str(inv.id) for inv in invitations}

    for invitation in invitations:
        iid = str(invitation.id)
        if invitation.used:
            result.add_failure(item_id=iid, reason="Already used.")
            continue
        try:
            with transaction.atomic():
                user = invitation.company.users.filter(
                    email=invitation.email, can_login=False,is_active=False
                ).first()
                if user:
                    user.delete()
                invitation.delete()
            result.add_success(item_id=iid)
        except Exception as e:
            result.add_failure(item_id=iid, reason=str(e))

    for missing in set(normalized_ids) - found_ids:
        result.add_failure(
            item_id=missing, reason="Invitation not found in this company."
        )

    return result
