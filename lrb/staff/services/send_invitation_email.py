from django.conf import settings
from django.template.loader import render_to_string

from lrb.core.tasks import send_email_task


def send_invitation_email(*, request, invitation):
    base = settings.FRONTEND_URL_TEMPLATE.format(slug=invitation.company.slug).rstrip("/")
    accept_url = f"{base}/accept-invitation?token={invitation.token}"

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