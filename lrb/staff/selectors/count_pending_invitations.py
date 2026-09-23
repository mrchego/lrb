from lrb.staff.models import Invitation


def count_pending_invitations(*, company_id:str) -> int: 
    return Invitation.objects.filter(company_id=company_id, used=False).count()