from django.template.loader import render_to_string

from lrb.core.constants import VERIFICATION_CODE_EXPIRY_MINUTES
from lrb.core.tasks import send_email_task
from lrb.identity.models import VerificationCode
from lrb.identity.services.generate_verification_code import generate_verification_code


def send_password_reset_code(*, user):
    verification_code = generate_verification_code(
        user=user, purpose=VerificationCode.Purpose.PASSWORD_RESET
    )
    message = render_to_string(
        "identity/verification_code_email.txt",
        {
            "code": verification_code.code,
            "minutes": VERIFICATION_CODE_EXPIRY_MINUTES,
            "purpose_label": VerificationCode.Purpose.PASSWORD_RESET.label,
        },
    )
    send_email_task.delay(
        subject="Your password reset code",
        message=message,
        recipient_list=[user.email],
    )
    return True


# 1. Purpose

# This function orchestrates the full "send a password reset code" flow: generate a fresh OTP (reusing the generate_verification_code service you just reviewed), render it into an email template, and queue that email to be sent asynchronously. It's the layer that sits between "user clicked forgot password" and "user receives an email" — pulling together a service, a template, and a background task into one coherent action.

# Good news up front: unlike the last three files, this one looks correct. No crashing bugs. I'll walk through it fully and point out a couple of design choices worth understanding, plus the same small consistency gaps you've now trained your eye to spot.

# 2. Imports — explained from scratch
# python
# from django.template.loader import render_to_string
# django.template.loader is Django's module for finding and rendering template files (files that mix static text with placeholders Django fills in). render_to_string takes a template file and a dictionary of values, and returns the finished text as a Python string — as opposed to Django's more commonly-known render(), which returns an HTTP response for a webpage. Here, you're not building a webpage — you're building the body text of an email — so render_to_string is the right tool: it gives you plain text you can hand to something else (an email function), not a response Django sends back to a browser.
# python
# from lrb.core.tasks import send_email_task
# Your own project code. The name and the .delay(...) call you'll see below are the signature of Celery — a library for running tasks in the background, outside the request/response cycle, usually processed by a separate worker process.
# python
# from lrb.identity.services.generate_verification_code import generate_verification_code
# Imports the exact function from the previous file — this is the connection made concrete: this service calls that service.
# 3. Signature
# python
# def send_password_reset_code(*, user):
# Same familiar shape: * forces user to be passed as a keyword (send_password_reset_code(user=some_user)).
# No type hint on user, and no -> bool return hint — the same recurring gap you've now seen across several service files in this codebase (contrast with the model's is_expired -> bool). Worth a note if you're doing a cleanup pass, not a functional problem.
# 4. Body — step by step
# python
#     verification_code = generate_verification_code(
#         user=user, purpose=VerificationCode.Purpose.PASSWORD_RESET
#     )
# Calls the service from the previous file, passing the enum value VerificationCode.Purpose.PASSWORD_RESET you defined in the model — not the raw string "PASSWORD_RESET". This is exactly the payoff of using TextChoices: this line autocompletes, can't typo, and is instantly readable.
# verification_code now holds the freshly-created VerificationCode row (remember: generate_verification_code returns the object via .objects.create(...)).
# python
#     message = render_to_string(
#         "identity/verification_code_email.txt",
#         {
#             "code": verification_code.code,
#             "minutes": VERIFICATION_CODE_EXPIRY_MINUTES,
#             "purpose_label": "password reset",
#         },
#     )
# First positional argument: "identity/verification_code_email.txt" — the path to a template file, relative to wherever your project's template directories are configured. .txt (not .html) tells you this is a plain-text email, not HTML.
# Second positional argument: a dictionary — the context. Each key here becomes a placeholder Django's template engine will substitute inside the .txt file — e.g. the template file itself probably contains something like Your code is {{ code }}, valid for {{ minutes }} minutes. Django replaces {{ code }} with verification_code.code, and so on.
# verification_code.code — reading the actual generated code string off the object returned in the step above.
# Notice "purpose_label": "password reset" is a hardcoded string here rather than reusing VerificationCode.Purpose.PASSWORD_RESET.label (which your TextChoices enum already provides as the human-readable "Password Reset"). Not a bug, but a tiny missed reuse opportunity — if you ever reused this same template for email verification, you'd need a matching send_email_verification_code function that repeats a similarly-hardcoded label rather than deriving it from the enum.
# python
#     send_email_task.delay(
#         subject="Your password reset code",
#         message=message,
#         recipient_list=[user.email],
#     )
# .delay(...) is Celery's method for saying "don't run this function right now, in this request — hand it off to a background worker and return immediately." This matters a lot for user experience: sending an actual email over the network can take a noticeable moment; you don't want the user's "forgot password" request to sit there waiting on that network call. .delay() queues the job (usually via Redis or a similar broker) and returns instantly, while a separate worker process picks it up and actually sends the email moments later.
# The keyword arguments (subject, message, recipient_list) must match whatever parameters send_email_task itself was defined with — you'd want to check that file to confirm, the same way you checked set_password's real signature earlier.
# recipient_list=[user.email] — a one-item list. The list shape strongly suggests send_email_task is built to support multiple recipients at once, even though this call only ever sends to one.
# python
#     return True
# Returns a plain boolean, not the verification_code object and not the code itself.
# 5. Why this approach
# Splitting "generate the code" from "send it via email" into two separate services (this file vs. the last one) means generate_verification_code stays reusable — e.g., a future SMS-based delivery method could call the same generation service without dragging along any email-specific code.
# Using .delay() instead of sending the email synchronously keeps the user-facing request fast and avoids the whole request failing just because an email provider is slow or briefly down.
# render_to_string with a template file instead of an f-string built inline separates content (the email wording, which a non-developer might need to edit) from logic (this Python file) — a common professional pattern: templates live in template files, not hardcoded strings buried in service code.
# Returning True rather than the verification_code object or the raw code itself — this is a deliberate security choice, not an oversight. The whole point of an OTP delivered by email is that only the email inbox holds it. If this function returned the code (or the full object, which has .code right there on it), any GraphQL mutation calling this function could accidentally leak the code back into the API response — completely defeating the purpose of sending it by email in the first place. Returning a bare True gives the caller just enough to know "yes, this succeeded," and nothing more.
# 6. Connections
# Upstream: almost certainly called directly from a GraphQL mutation like requestPasswordReset, right after looking up the User by submitted email.
# Downstream, inside this function: calls generate_verification_code (previous file), which itself wraps two database writes in @transaction.atomic; then hands off to Celery via send_email_task.
# The template file (identity/verification_code_email.txt) is a separate, non-Python file this function depends on — if you go looking for it, expect to find it under a templates/ directory in the identity app.
# @transaction.atomic correctly does not appear on this function — and this is worth understanding why, not just noting it: generate_verification_code already committed its own atomic transaction by the time this function calls render_to_string and .delay(). If this whole function were wrapped in @transaction.atomic instead, .delay() could queue the Celery task before the outer transaction actually commits to the database — risking a worker picking up the task and looking up a VerificationCode row that technically doesn't exist in the database yet. Leaving this function un-wrapped, while the inner generation step has its own atomic block, is the correct way to sequence "commit the write" before "fire the side effect."
# 7. Advanced concepts

# The transaction/task-queue ordering hazard, explained simply: think of @transaction.atomic as "don't let anyone else see this data until I say 'done.'" If you queue a background task inside that atomic block, the background worker might start running immediately (workers are often extremely fast) — possibly before the "I say done" moment happens. The worker looks for data that, from its point of view, doesn't exist yet. Django actually provides a tool for exactly this scenario — transaction.on_commit(lambda: send_email_task.delay(...)), which guarantees the task only fires after a successful commit — but this file sidesteps the whole problem more simply, by structuring the code so the atomic write already fully finished (in a separate function call) before the task gets queued.

# 8. Small example
# python
# def notify_order_shipped(*, order):
#     tracking = generate_tracking_number(order=order)  # its own @transaction.atomic
#     message = render_to_string("orders/shipped_email.txt", {"tracking": tracking.number})
#     send_email_task.delay(subject="Your order shipped", message=message, recipient_list=[order.user.email])
#     return True

# Same shape: call an atomic generation service first, render a template, queue a background task, return a plain success signal — nothing sensitive echoed back.

# 9. What to remember
# render_to_string renders a template file to a plain string — use it whenever you need finished text (emails, PDFs, exported files), as opposed to render(), which builds an HTTP response for the browser.
# .delay() is the signal that a function call is being handed to a background worker (Celery), not run immediately — recognize this pattern whenever you see .delay(...) in a codebase.
# Don't queue background tasks inside an @transaction.atomic block unless you specifically use transaction.on_commit(...) — otherwise a worker can race ahead of data that hasn't actually been saved yet.
# A function returning less than it could is sometimes a deliberate security boundary, not a missed opportunity — before assuming a return value should be "more useful," ask what leaking that value would cost.
# Chaining single-purpose services together (generate_verification_code → send_password_reset_code) instead of writing one big function keeps each piece independently testable and reusable — this is the same service/selector philosophy your whole project is built around, just visible now at a slightly larger scale.
