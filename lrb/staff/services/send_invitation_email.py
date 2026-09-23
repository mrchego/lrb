from django.conf import settings
from django.template.loader import render_to_string

from lrb.core.tasks import send_email_task


def send_invitation_email(*, request, invitation):
    frontend_base = getattr(settings, "FRONTEND_URL", None)
    if frontend_base:
        accept_url = (
            f"{frontend_base.rstrip('/')}/accept-invitation? token={invitation.token}"
        )
    else:
        accept_url = request.build_absolute_uri(
            f"/accept-invitation? token={invitation.token}"
        )

    subject = f"You've been invited to join {invitation.company.name}"
    message = render_to_string(
        "staff/invitation_email.txt",
        {"invitation": invitation, "accept_url": accept_url},
    )

    send_email_task.delay(
        subject=subject,
        message=message,
        recipient_list=[invitation.email],
    )
    return True
