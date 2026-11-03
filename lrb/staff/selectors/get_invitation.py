from typing import Optional

from lrb.core.tenancy import require_company_id
from lrb.staff.models import Invitation


def get_invitation(*, invitation_id: str, company_id: str) -> Optional[Invitation]:
    company_id = require_company_id(company_id)
    return Invitation.objects.filter(pk=invitation_id, company_id=company_id).first()
