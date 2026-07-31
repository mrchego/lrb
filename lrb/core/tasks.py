from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_email_task(self, *, subject, message, recipient_list):
    """
    email goes through here so SMTP latency
    and transient failures never block the request/response cycle inside
    a GraphQL mutation.
    """
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
    )
    
    
    
    
    
# Level 1 — Big Picture

# Why does this file exist?
# core.tasks is the home for background work that's shared across apps. This particular function exists because sending an email is a slow, unreliable, external I/O operation — it involves opening a network connection to an SMTP server (or a provider API), and that server can be slow, timeout, or momentarily reject your connection. None of that has anything to do with whether the GraphQL mutation that triggered it succeeded.

# What problem does it solve?
# Without this, your mutation code would look like:

# python
# def create_verification_code(*, user):
#     code = VerificationCode.objects.create(user=user, ...)
#     send_mail(subject="Verify", message=code.code, ...)  # blocks here
#     return code

# If SMTP is slow (say, 2–3 seconds) or down entirely, your GraphQL mutation — which the frontend is waiting on synchronously — hangs or errors, even though the actual business operation (creating the code in the DB) already succeeded. Worse, if the mail server throws an exception, your whole mutation could fail and roll back a DB write that had nothing wrong with it.

# Why is this responsibility placed here (in core), not in identity or staff?
# Because the task itself — "send this email, retry if it fails" — has zero domain knowledge. It doesn't know what a verification code is, or what a staff invitation is. It's a generic capability: "send plain-text email, resiliently." Both identity (verification/reset) and staff (invitations) consume it, but neither owns it. Docstring literally says this: "Shared by identity ... and staff." That's the tell that it belongs in core — a shared kernel, not a specific bounded context.

# What would happen if this file didn't exist?
# Every app that needs to send email would either duplicate this retry/async logic, or (worse) call send_mail directly and inherit the blocking behavior above. You'd have inconsistent retry policies scattered across apps.

# Which architectural layer does this belong to?
# This is infrastructure, sitting just below your service layer. Your services (in identity, staff) call send_email_task.delay(...). The task itself calls Django's send_mail, which talks to SMTP. So the chain is:

# GraphQL mutation → service → send_email_task.delay() → [returns immediately]
#                                        ↓ (async, separate process)
#                               send_email_task runs → send_mail() → SMTP server

# How does it communicate with the rest of the app?
# Not via a normal function call. .delay(...) (or .apply_async(...)) serializes the task name + arguments into a message, pushes it onto the Redis broker, and returns instantly. A separate Celery worker process picks up that message and actually executes the function body. The calling code and the task body run in different processes, possibly on different machines — they only communicate through Redis.

# Level 2 — Design Thinking

# Why a function decorated with @shared_task, not a method on a service class?
# Celery tasks need to be importable, top-level callables that Celery's worker can discover and register by a stable name (core.tasks.send_email_task). Wrapping this in a service class would add no value — there's no state to encapsulate, no self that matters beyond what Celery itself injects (see bind=True below). A task is fundamentally a registered function, not an object.

# Why not just call send_mail() directly inside the service function?
# Because then it's synchronous. The whole point is decoupling "the mutation succeeded" from "the email definitely sent." A dropped/slow email should never be the reason a user's password-reset request appears to fail.

# Why keyword-only arguments (*, subject, message, recipient_list)?
# This matches the convention already established across your project's services (keyword-only args everywhere). For tasks specifically there's an extra reason: task arguments get serialized (usually as JSON) and stored in the broker message. Positional args in Celery are a common source of subtle bugs when task signatures change over time — a keyword-only call site is self-documenting and immune to argument-order mistakes when someone edits the signature later.

# Why not put retry logic in the caller (the service) instead of the task?
# Because retry is a concern of "how do we deliver this message reliably," which is orthogonal to "what email are we sending and why." If retry logic lived in the service, identity and staff would each have to reimplement backoff/retry — again, duplicated infrastructure concern living in a domain layer where it doesn't belong.

# Level 3 — Pattern Recognition

# Pattern: Command Pattern (loosely).
# A Celery task is essentially a command object in disguise — a message consisting of "here is a name of an operation, and here are its arguments," which gets queued and executed later, decoupled from the invoker. The task function is the command's execute().

# Why it exists: to decouple "when/where a command is issued" from "when/where it runs."
# Advantage: the caller doesn't need to know or care about execution timing, retries, or failure handling.
# Disadvantage: debugging becomes harder — you can't just step through a stack trace; you have to look at worker logs, since execution is detached from the calling code's context.
# Common mistake: passing non-serializable objects (like a Django model instance) as task arguments — more on this in Level 8.

# Pattern: Retry / Circuit-breaker adjacent (via autoretry_for + retry_backoff).
# This isn't a full circuit breaker (which would stop calling a failing service entirely for a cooldown period), but it's the same family of idea: don't treat a single failure as final; assume transient failures are common in distributed systems and build resilience in.

# Why it exists: network calls fail sometimes for reasons that have nothing to do with your code being wrong (DNS blip, SMTP server restart, rate limiting).
# Disadvantage: if the failure is not transient (e.g., malformed email address, permanently misconfigured SMTP credentials), you retry 3 times for nothing, delaying the eventual failure signal.
# Common mistake: using autoretry_for=(Exception,) too broadly — it'll retry on truly permanent errors too (e.g., a TypeError from a bug in your own code), masking bugs as "transient failures." (Worth flagging as a real trade-off in your code — more in Level 8.)

# Not really Service Layer / Repository here — this file is neither. It's a pure infrastructure/task layer. Worth noting explicitly since it's easy to over-apply pattern labels; not everything is a "service."

# Level 4 — Framework Thinking

# @shared_task — why does Celery provide this instead of just @app.task?
# In a Django project made of multiple apps (core, identity, staff, ...), each app might want to define tasks without importing the specific Celery app instance (which usually lives in something like config/celery.py). shared_task lets you decorate a function without binding it to a particular Celery app at import time — the binding happens lazily, when Celery actually configures itself. This avoids circular imports (core.tasks importing config.celery, while config.celery might indirectly trigger app loading that imports core.tasks).

# Without shared_task, every task-defining module across every app would need from config.celery import app and use @app.task, creating tighter coupling between each app and your project's specific Celery configuration — bad for a reusable app.

# send_mail — why does Django provide this instead of you using smtplib directly?
# Django's send_mail wraps EmailMessage/EmailMultiAlternatives and reads your EMAIL_BACKEND setting, so the same call works whether you're using real SMTP in production, a console backend in development (prints to terminal instead of sending), or a locmem backend in tests (stores sent emails in a list for assertions). Without this abstraction, you'd hardcode SMTP details into every part of the app that sends mail, and testing would require mocking smtplib everywhere.

# Internally: send_mail() constructs an EmailMessage object and calls .send() on it, which asks django.core.mail.get_connection() for a connection using your configured backend, then calls the backend's send_messages().

# Level 5 — Build It Yourself (from first principles)

# Imagine Celery and send_mail don't exist. How would you build "send email reliably, without blocking the request"?

# The queue. You need somewhere to put "pending work" that isn't the request/response cycle. You'd build a table (or use Redis) as a queue: PendingEmail(subject, message, recipients, attempts, status).
# The producer. Your mutation, instead of sending email, inserts a row: PendingEmail.objects.create(subject=..., message=..., recipients=..., status="pending"). Fast, DB write only, no network call to SMTP blocking the request.
# The worker. A separate long-running process (a management command run via while True: ... or a cron job) polls that table: SELECT * FROM pendingemail WHERE status='pending' LIMIT 10, then for each one, tries to actually connect to SMTP and send it.
# Retry. If sending fails, increment attempts, and if attempts < 3, leave it as pending (maybe with a next_attempt_at timestamp using exponential backoff: now() + 2**attempts seconds); if attempts >= 3, mark as failed and stop trying.
# Concurrency safety. Multiple worker processes polling the same table need SELECT ... FOR UPDATE SKIP LOCKED (Postgres) so two workers don't grab and send the same email twice.
# The actual SMTP call. You'd use Python's built-in smtplib: open a connection, STARTTLS, login(), construct a MIME message, sendmail().

# This is, roughly, what Celery + a broker + Django's mail backend give you for free — durable queuing, retry/backoff, worker concurrency, and a uniform send API across environments.

# Level 6 — Generic Blueprint

# Every "fire a resilient background side-effect" task should generally follow this shape:

# Accept only serializable, keyword-only arguments (primitives, not model instances)
# Declare retry policy declaratively (what counts as retryable, how many attempts, backoff strategy)
# Do the actual I/O (the one thing this task is responsible for) — nothing else
# Let exceptions propagate naturally so the retry mechanism (not your own try/except) handles failure
# Keep the task itself free of business logic — business rules belong in the service that calls the task, not in the task




# What responsibilities does `send_email_task` need to have, at minimum? -> its responsibility is that email goes through here so SMTP latency and transient failures never block the request/response cycle inside a graphql mutation  -> What arguments does it need to receive, and why keyword-only? ->it needs to receive keyword aguments (

# ```python
# subject, message, recipient_list
# ```

# ) because when  asterics are used (*) at the start the ones that follow must be kyword argument, to avoid postional value arguments error (order matters ) in keyword arguments order does not matter , its self documenting and its clean code readability  -> What should happen if `send_mail` raises an exception — should the function catch it? Why or why not, given `autoretry_for`? -> The function should do nothing. No try/except anywhere in the body. Look at the code again — there is no try: block. send_mail(...) is called plainly, and if it raises, the exception just propagates up out of the function.

# Here's the actual mechanism: autoretry_for=(Exception,) tells Celery itself — not your function — "if this task raises any of these exception types, don't mark it failed — silently schedule a retry instead." Celery wraps your function's execution; when it sees an exception matching autoretry_for, it calls the equivalent of self.retry(exc=exc) on your behalf, using retry_backoff and retry_kwargs to decide the delay and the max attempts.

# So the retry logic lives entirely in the decorator's configuration, not in the function body. If you added your own try/except Exception: pass inside the body, you'd actually break retries — you'd be swallowing the exception before Celery ever sees it, so it would look like the task succeeded when the email actually failed to send.

# General principle worth keeping: when a framework offers declarative error-handling (autoretry, middleware exception handling, etc.), don't also add imperative try/except for the same failure — that either duplicates the behavior or silently defeats it.

# 4. bind=True — not quite; this isn't about circular imports. That was shared_task (question wasn't asking about that one — good instinct that it's related to avoiding tight coupling, just attached to the wrong decorator).

# bind=True is about what self is when Celery calls your function. With bind=True, Celery passes the task instance itself as the first argument (self), giving you access to things like self.request.retries (how many times has this been retried so far?), self.request.id (the task's unique ID, useful for logging/tracing), and — critically — the ability to call self.retry(...) manually, with custom logic, if you ever needed to retry conditionally rather than automatically.

# In this specific function, self isn't used inside the body at all — so functionally, right now, bind=True is doing nothing observable. It's there defensively/idiomatically: if you ever want to add self.request.retries to a log line ("retry attempt 2 of 3 for verification email"), or want to override the retry delay conditionally, the plumbing is already in place. It's a very common pairing with autoretry_for/retry_kwargs even when unused, because those retry-related settings are inherently about task instance state.



# Imports
# python
# from celery import shared_task
# from django.conf import settings
# from django.core.mail import send_mail
# shared_task — the decorator, covered above (Level 4): lets core define a task without importing your project's specific Celery app instance, avoiding circular imports between core and config/celery.py.
# from django.conf import settings — Django's lazy settings proxy. It doesn't eagerly load your settings module at import time; it resolves DJANGO_SETTINGS_MODULE on first attribute access. This is why apps import settings this way instead of import config.settings.production directly — it keeps the app agnostic about which settings module is active (local/staging/production), which matters a lot in a cookiecutter-django project where you have multiple settings files.
# send_mail — Django's high-level mail-sending function, discussed in Level 4 above (backend-agnostic: console in dev, SMTP in prod, locmem in tests).
# The decorator
# python
# @shared_task(
#     bind=True,
#     autoretry_for=(Exception,),
#     retry_backoff=True,
#     retry_kwargs={"max_retries": 3},
# )
# bind=True — covered above.
# autoretry_for=(Exception,) — a tuple of exception classes; any exception that isinstance()-matches one of these triggers an automatic retry instead of task failure. (Exception,) is the broadest possible net — it'll catch SMTPException, ConnectionRefusedError, but also, e.g., a TypeError from a bug in your own code. Worth flagging now for Level 8: this is a real trade-off, not free resilience.
# retry_backoff=True — instead of retrying immediately (which would hammer an already-struggling SMTP server), Celery waits an exponentially increasing delay between attempts (roughly 1s, 2s, 4s by default). This is the standard "don't retry-storm a failing dependency" pattern.
# retry_kwargs={"max_retries": 3} — caps it at 3 attempts total, so a permanently broken SMTP config doesn't retry forever; eventually the task gives up and is marked failed (visible in your Celery result backend/monitoring, if configured).
# The signature
# python
# def send_email_task(self, *, subject, message, recipient_list):
# self — present because bind=True; Celery injects the task instance here automatically. You never pass this yourself when calling .delay(...).
# * — forces everything after it to be keyword-only, as you correctly identified.
# subject, message, recipient_list — the three keyword-only arguments. Note these are all plain, JSON-serializable types (strings, and a list of strings) — no Django model instances, no querysets. This matters a lot: Celery serializes task arguments (JSON by default) to put them on the Redis broker as a message. A Django User instance can't be JSON-serialized directly, and even if you pickled it, you'd be sending a stale snapshot of that object across process/machine boundaries — by the time the worker runs (possibly seconds later), the DB row might have changed. The correct pattern (which this function follows) is: pass primitive IDs/strings, and if you need related data, re-fetch it fresh inside the task.
# The docstring
# Shared by identity (verification/reset codes) and staff (invitations) —
# any Django-sendable plain-text email goes through here so SMTP latency
# and transient failures never block the request/response cycle inside
# a GraphQL mutation.

# This is doing real architectural documentation, not just describing syntax — it's telling future-you (or a teammate) why this exists and who depends on it, which is exactly the kind of comment that survives refactors, versus a comment like # sends email which adds nothing.

# The body
# python
# send_mail(
#     subject=subject,
#     message=message,
#     from_email=settings.DEFAULT_FROM_EMAIL,
#     recipient_list=recipient_list,
# )
# Called with all keyword arguments, matching your project's convention.
# from_email=settings.DEFAULT_FROM_EMAIL — pulled from settings rather than being a parameter. This is a deliberate design choice: the "from" address is a project-wide constant (you don't want identity and staff each deciding their own from-address, risking inconsistency or a typo'd sender). Anything that's a project-wide policy belongs in settings, not in per-call arguments.
# No return statement — the task's return value would be None. That's fine here because nothing consumes the result; this is fire-and-forget (no .get() is called on the resulting AsyncResult). If you needed to know whether the send succeeded from the calling code, you'd need a Celery result backend and to actually poll/await the result — which would reintroduce blocking, defeating the purpose. So the design silently accepts "we don't confirm success back to the original request" — worth sitting with as a trade-off.
# No try/except — as established, this is intentional; retries are declarative, not imperative.
# Level 8 — Engineering Trade-offs (quick hit, since we touched on it above)

# Why autoretry_for=(Exception,) instead of something narrower like (SMTPException, ConnectionError)?

# Pro: simplicity — one line, covers every failure mode without needing to enumerate every possible SMTP/network exception class.
# Con: it also retries on bugs. If settings.DEFAULT_FROM_EMAIL were misconfigured (say, None), send_mail might raise a TypeError or ValueError — a permanent misconfiguration, not a transient failure — yet Celery will burn 3 retries with backoff before giving up, delaying visibility into a bug that will never fix itself on retry.
# A stricter version might do autoretry_for=(SMTPException, TimeoutError, ConnectionError) — only genuinely transient, environment-related failures — and let programming errors fail fast and loud on the first attempt.


# Conceptual (5)1. Why you cannot safely pass a Django model instanceDatabase State Staleness: Passing a full model object (e.g., user) serializes it into the key-value data store (like Redis) used by Celery. By the time the background worker picks up the queue message minutes later, the actual database record might have been updated or deleted, causing the task to work with stale data.Serialization Overhead: Celery needs to turn arguments into text (like JSON). Django model instances are complex objects with active database connections and cannot be natively converted to JSON string text. You should pass the integer or UUID primary key (user_id) instead, and let the task fetch a fresh object inside the worker runtime.2. Difference between @shared_task and @app.task@shared_task (Reusable Apps): This decorator creates a task without a direct reference to a specific Celery application instance (app). It is critical for reusable Django applications or modular project structures where the core app configuration might change or be initialized later in the runtime lifecycle.@app.task (App-Bound): This decorator explicitly binds a task to a hardcoded, specific instance of a Celery app variable defined in your project (e.g., from project.celery import app). It makes your module rigid and impossible to reuse across different projects or isolated settings.3. Why send_mail reads from_email from settings hereArchitectural Encapsulation: The business application triggering this email shouldn't need to care who the sender address is. Keeping it bound to settings.DEFAULT_FROM_EMAIL enforces a single source of truth across your entire system, abstracting configuration details away from your use cases.4. What retry_backoff=True mechanically changesExponential Delays: Instead of retrying instantly or waiting a static amount of time (like 1 second), it introduces an exponential delay between every attempt.The Math: The first retry might wait 2 seconds, the second retry waits 4 seconds, and the third waits 8 seconds. Celery also introduces random "jitter" to these timings automatically so that hundreds of failed emails don't hit your SMTP server simultaneously when a network connection recovers.5. Why there is no try/except block hereDeclarative Error Handling: The @shared_task decorator handles it for you natively. The autoretry_for=(Exception,) parameter tells Celery to implicitly wrap the entire function in an internal try/except block. If any unhandled exception occurs during the execution of send_mail, Celery automatically catches it and triggers the specified retry schedule.Design (3)1. HTML Email Modification vs. New TaskModify the existing task. Adding an optional keyword argument like html_message=None to the current task minimizes code duplication and keeps your core email-sending pipeline unified. You would pass it directly through to Django's native send_mail function, which natively accepts an html_message parameter.2. Where recipient_list validation should liveIt belongs before the task is queued (e.g., inside the GraphQL Mutation). Validation should happen synchronously on your web server before hitting Celery. Throwing a validation error to the client instantly prevents wasting database space, network bandwidth, and queue slots on a background job that is guaranteed to fail due to structural input mistakes.3. How to test this task without hitting a real SMTP serverUse Django's Memory Email Backend: In your test environment configuration (settings.py), set EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'.Assertion: When you execute the task in your automated tests, Django redirects the outgoing email to an in-memory array (django.core.mail.outbox), allowing you to assert that an email was created and verify its subject lines or content without connecting to the internet.Debugging (2)1. Top 2 hypotheses for "Silently Never Arrive"Hypothesis A: Celery Workers are Not Running. The GraphQL mutation successfully generates the task and pushes it to your Redis database queue, but no active worker process is alive to read the queue and execute the SMTP commands.Hypothesis B: Django's Console Backend is Enabled. In local development settings, EMAIL_BACKEND is frequently set to print out to the command line interface terminal (django.core.mail.backends.console.EmailBackend) instead of actually sending a real network packet. The email prints out to your worker log instead of hitting an inbox.2. What happens after permanent failureTask State Marked as FAILURE: The result backend (if configured) marks the specific task ID state as FAILURE along with the traceback string.Silent Failure Warning: Nobody is proactively notified by default. Unless you have set up a custom Celery failure hook, monitoring tools (like Flower), or logging aggregation (like Sentry), the error will sit silently in the background worker's historical state.


# import smtplib
# from celery import shared_task
# from django.conf import settings
# from django.core.mail import send_mail
# from django.core.mail.message import BadHeaderError


# @shared_task(
#     bind=True,
#     autoretry_for=(OSError, smtplib.SMTPException),
#     retry_backoff=True,
#     retry_kwargs={"max_retries": 3},
# )
# def send_email_task(self, *, subject, message, recipient_list):
#     if not recipient_list:
#         raise ValueError("Cannot send email: recipient_list is empty.")

#     try:
#         send_mail(
#             subject=subject,
#             message=message,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=recipient_list,
#         )
#     except (BadHeaderError, smtplib.SMTPRecipientsRefused) as e:
#         raise ValueError(f"Malformed input detected, skipping retry: {e}") from e