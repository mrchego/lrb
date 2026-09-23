import email

from django.utils import timezone

from lrb.accounts.selectors.get_user import get_user
from lrb.authorization.models.user_role import UserRole
from lrb.authorization.selectors.get_user_permissions import (
    invalidate_user_permissions_cache,
)
from lrb.core.constants import INVITATION_EXPIRY_DAYS
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation
from lrb.staff.selectors.get_pending_invitation_for_email import (
    get_pending_invitation_for_email,
)
from lrb.staff.services.send_invitation_email import send_invitation_email


def promote_staff_to_login(*, user_id, company, role, invited_by, request):
    user = get_user(user_id=user_id)
    if not user or user.company_id != company.id:
        raise ApplicationError(
            message="Staff member not found.", code=ErrorCode.USER_NOT_FOUND
        )

    if user.can_login:
        raise ApplicationError(
            message="This staff member can already log in.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    if get_pending_invitation_for_email(email=user.email, company_id=company.id):
        raise ApplicationError(
            message="An invitation is already pending for this staff member.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    UserRole.objects.create(user=user, role=role)
    invalidate_user_permissions_cache(user_id=user.id)

    invitation = Invitation.objects.create(
        email=user.email,
        company=company,
        invited_by=invited_by,
        role=role,
        expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
    )
    send_invitation_email(request=request, invitation=invitation)
    return user, invitation


# Absolutely. The key part to understand is:

# if not user or user.company_id != company.id:

# There are actually two separate checks joined by or. The part you especially asked about:

# user.company_id != company.id

# is checking whether the user belongs to the same company as the company object.

# Let's break it down very slowly.

# 1. First, understand the objects

# Imagine you have:

# user
# company

# The user might represent:

# John
# user.id         → 25
# user.company_id → 10

# And company might represent:

# ABC Limited
# company.id → 10

# So visually:

# user
#  ├── id = 25
#  └── company_id = 10
#                     │
#                     ▼
#               company
#               └── id = 10

# The important relationship is:

# user.company_id

# versus:

# company.id
# 2. What does user.company_id mean?

# Start from the left:

# user

# This is a Python object.

# For example:

# user = User(
#     id=25,
#     company_id=10,
# )

# The object has attributes:

# user.id
# user.company_id

# So:

# user.company_id

# means:

# "Go inside the user object and get its company_id."

# If:

# user.company_id == 10

# then:

# user.company_id

# produces:

# 10
# 3. What does company.id mean?

# Same idea.

# Suppose:

# company = Company(
#     id=10,
#     name="ABC Limited",
# )

# Then:

# company.id

# means:

# "Go inside the company object and get its id."

# So:

# company.id

# produces:

# 10
# 4. Now compare them

# We have:

# user.company_id != company.id

# Let's replace the values.

# Suppose:

# user.company_id = 10
# company.id = 10

# Then Python effectively sees:

# 10 != 10

# != means:

# "is not equal to"

# Therefore:

# 10 != 10

# is:

# False

# So the condition is false.

# 5. What if they are different?

# Suppose:

# user.company_id = 10
# company.id = 20

# Then:

# user.company_id != company.id

# becomes:

# 10 != 20

# Since 10 and 20 are different:

# 10 != 20

# is:

# True

# So:

# user.company_id != company.id

# means:

# "The user's company is NOT the company we're currently dealing with."

# That's the main idea.