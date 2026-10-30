from django.db import transaction

from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)


@transaction.atomic
def cancel_invitation(*, invitation) -> None:
    """Delete a pending invitation and undo what created it.

    - Brand-new invitee (can_login=False, is_active=False): delete the user.
    - Promoted staff record (can_login=False, is_active=True): keep the user,
      strip the roles that were granted for the invitation.
    - can_login=True: someone with real access, so leave them alone.
    """
    user = invitation.company.users.filter(email=invitation.email).first()

    if user and not user.can_login:
        user_id = user.id
        if not user.is_active:
            user.delete()  # cascades to UserRole
        else:
            UserRole.objects.filter(user=user).delete()
        transaction.on_commit(lambda: invalidate_user_permissions_cache(user_id=user_id))

    invitation.delete()