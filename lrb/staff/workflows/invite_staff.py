from django.db import transaction
from django.utils import timezone

from lrb.accounts.services.create_user import create_user
from lrb.authorization.models.user_role import UserRole
from lrb.core.constants import INVITATION_EXPIRY_DAYS
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.staff.models import Invitation
from lrb.staff.services.send_invitation_email import send_invitation_email


@transaction.atomic
def invite_staff(
    *,
    email,
    first_name,
    last_name,
    company,
    invited_by,
    request,
    can_login=True,
    role=None,
):
    from lrb.accounts.selectors.get_user_by_email import get_user_by_email

    existing = get_user_by_email(email=email)
    if existing and existing.is_active:
        raise ApplicationError(
            message="User with this email already active.",
            code=ErrorCode.USER_ALREADY_EXISTS,
        )

    if can_login and role is None:
        raise ApplicationError(
            message="A role is required to grant login access.",
            code=ErrorCode.VALIDATION_ERROR,
        )

    user = create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=None,
        company=company,
        can_login=False,
        is_active=not can_login,
        is_staff=False,
    )

    invitation = None
    if can_login:
        UserRole.objects.create(user=user, role=role)
        invitation = Invitation.objects.create(
            email=email,
            company=company,
            invited_by=invited_by,
            role=role,
            expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
        )
        send_invitation_email(request=request, invitation=invitation)

    return user, invitation


# Yes — you have the right idea. The important thing is that None is the initial value, and later the variable can be reassigned to an actual Invitation object.

# Let's go slowly.

# 1. First: invitation = None

# You have:

# invitation = None

# Think of a variable as a label attached to a value.

# At this moment:

# invitation
#     ↓
#   None

# None is a special Python value meaning roughly:

# "There is currently no value/object here."

# It does not mean the variable doesn't exist.

# The variable invitation exists. Its current value is None.

# 2. Why would we start with None?

# Look at your code:

# invitation = None

# if can_login:
#     UserRole.objects.create(user=user, role=role)

#     invitation = Invitation.objects.create(
#         email=email,
#         company=company,
#         invited_by=invited_by,
#         role=role,
#         expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
#     )

# There are potentially two paths.

# Path A — can_login is False

# The if block doesn't run:

# invitation = None

# So at the end:

# invitation → None

# There is no invitation.

# Path B — can_login is True

# The if block runs.

# Initially:

# invitation → None

# Then Python reaches:

# invitation = Invitation.objects.create(...)

# Now invitation is reassigned.

# Conceptually:

# BEFORE

# invitation
#     ↓
#   None

# Then:

# invitation = Invitation.objects.create(...)

# becomes:

# AFTER

# invitation
#     ↓
# Invitation object

# So yes:

# None is the initial/default value, and then the variable gets a new value if can_login is true.

# 3. But what does Invitation.objects.create() actually do?

# This is the really important part.

# You can think of:

# Invitation.objects.create(...)

# as roughly meaning:

# "Create a new Invitation database record using these values, save it to the database, and give me back the newly created Invitation object."

# For example:

# invitation = Invitation.objects.create(
#     email=email,
#     company=company,
#     invited_by=invited_by,
#     role=role,
# )

# Django creates something like:

# Invitation
# --------------------------------
# id:          42
# email:       alice@example.com
# company:     ABC Ltd
# invited_by:  John
# role:        Manager
# expires_at:  ...
# --------------------------------

# And then the result of .create() is assigned to:

# invitation

# So:

# invitation = Invitation.objects.create(...)

# can be mentally read as:

# "Create an Invitation and store the resulting Invitation object in the variable called invitation."

# 4. Let's break this apart

# Take:

# Invitation.objects.create(
#     email=email,
#     company=company,
#     invited_by=invited_by,
#     role=role,
#     expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
# )

# There are several pieces.

# Invitation

# This is probably your Django model.

# Something like:

# class Invitation(models.Model):
#     email = models.EmailField()
#     company = models.ForeignKey(...)
#     invited_by = models.ForeignKey(...)
#     role = models.ForeignKey(...)
#     expires_at = models.DateTimeField()

# So Invitation describes what an invitation looks like in your database.

# .objects

# Django gives models an objects manager.

# Think of it as:

# A tool Django gives you for interacting with the database for this model.

# For example:

# Invitation.objects.create(...)
# Invitation.objects.get(...)
# Invitation.objects.filter(...)
# .create(...)

# create() means:

# Create a new database record.

# So:

# Invitation.objects.create(...)

# means:

# Invitation model
#        ↓
# objects manager
#        ↓
# create a new record
#        ↓
# save it to database
#        ↓
# return the new Invitation object
# 5. Now the individual fields

# You have:

# email=email,
# company=company,
# invited_by=invited_by,
# role=role,

# This can look confusing because the same word appears twice.

# For example:

# email=email

# The left side is the field on the Invitation model.

# The right side is the Python variable you're passing into it.

# Think:

# Invitation's email field
#           =
# value currently inside the email variable

# So:

# email=email

# means:

# "Set the new Invitation's email field to the value stored in the email variable."

# Same idea:

# company=company

# means:

# "Set the Invitation's company field to the value stored in company."

# 6. Now the difficult one: expires_at

# You have:

# expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),

# Let's break this into pieces.

# First:

# expires_at=

# This is the Invitation model field.

# It probably represents:

# The date and time when this invitation stops being valid.

# Now look at the right side:

# timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS)

# That's calculating the expiration date.

# 7. timezone.now()
# timezone.now()

# means:

# "Give me the current date and time."

# For example, imagine the current time is:

# 2026-09-22 19:00

# Then:

# timezone.now()

# might give you something equivalent to:

# 2026-09-22 19:00

# The exact representation depends on Django's timezone configuration.

# 8. timezone.timedelta(...)

# Now:

# timezone.timedelta(days=INVITATION_EXPIRY_DAYS)

# creates a time duration.

# For example, suppose:

# INVITATION_EXPIRY_DAYS = 7

# Then:

# timezone.timedelta(days=INVITATION_EXPIRY_DAYS)

# means:

# 7 days

# So:

# timezone.timedelta(days=7)

# represents a duration of seven days.

# It doesn't mean:

# "What date is seven days?"

# It means:

# "A duration/amount of time equal to seven days."

# 9. Then the +

# Now we have:

# timezone.now() + timezone.timedelta(days=7)

# Suppose:

# Current time:
# September 22, 2026 at 19:00

# Add:

# 7 days

# You get:

# September 29, 2026 at 19:00

# So:

# timezone.now() + timezone.timedelta(days=7)

# means:

# "Take the current date/time and move forward 7 days."

# 10. So what does the entire line mean?

# This:

# expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),

# means:

# "Set the invitation's expires_at field to the current time plus however many days the application allows invitations to remain valid."

# If:

# INVITATION_EXPIRY_DAYS = 7

# then:

# expires_at=timezone.now() + timezone.timedelta(days=7)

# might produce:

# expires_at = September 29, 2026 at 19:00
# 11. Put everything together

# Your code:

# invitation = None

# if can_login:
#     UserRole.objects.create(user=user, role=role)

#     invitation = Invitation.objects.create(
#         email=email,
#         company=company,
#         invited_by=invited_by,
#         role=role,
#         expires_at=timezone.now() + timezone.timedelta(days=INVITATION_EXPIRY_DAYS),
#     )

# can be mentally translated to:

# Start by saying:
# "There is currently no invitation."

#         ↓

# invitation = None

#         ↓

# Check:
# "Can this user log in?"

#         ↓

# if can_login:

#         ↓ YES

# Create a UserRole

#         ↓

# Create a new Invitation

#         ↓

# Give the invitation:
#     email
#     company
#     person who invited them
#     role
#     expiration date

#         ↓

# Save that Invitation to the database

#         ↓

# Give me the newly-created Invitation object

#         ↓

# Store it in the variable "invitation"

# So the variable changes:

# invitation = None
#        ↓
#        ↓ can_login is True
#        ↓
# invitation = <new Invitation object>

# But if:

# can_login = False

# then:

# invitation = None

# stays unchanged.

# 12. One very important distinction

# This:

# invitation = None

# does not create an empty invitation in the database.

# It simply creates a Python variable whose current value is None.

# Whereas:

# Invitation.objects.create(...)

# actually tells Django:

# Create and save a new Invitation record in the database.

# That's a very important distinction to remember:

# Code	What it does
# invitation = None	Python variable currently has no object/value
# Invitation.objects.create(...)	Creates and saves a new database record
# invitation = Invitation.objects.create(...)	Creates the record and stores the resulting object in invitation

# And that last pattern is extremely common in Django.