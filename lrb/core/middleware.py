from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from django.utils import timezone
from lrb.core.clock.zones import DEFAULT_TIMEZONE, get_company_timezone, get_zone

class TenantMiddleware(TenantMainMiddleware):
    """Host -> Domain -> Company -> search_path. Also blocks deactivated companies
    before any resolver runs."""

    def process_request(self, request):
        response = super().process_request(request)
        if response is not None:
            return response
        tenant = request.tenant
        if tenant.schema_name != get_public_schema_name() and not tenant.is_active:
            raise PermissionDenied("This company is deactivated.")
        return None


class RequireGraphQLPreflightMiddleware:
    """GraphQL is csrf_exempt and tenants are sibling subdomains. Requiring a custom
    header forces a CORS preflight, so a form POST from another tenant can't ride
    the session cookie."""

    HEADER = "Apollo-Require-Preflight"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == "POST"
            and request.path == "/graphql/"
            and not request.headers.get(self.HEADER)
        ):
            return JsonResponse({"errors": [{"message": "Missing required header."}]}, status=403)
        return self.get_response(request)


class CompanyTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with timezone.override(self._resolve(request)):
            return self.get_response(request)

    @staticmethod
    def _resolve(request):
        tenant = getattr(request, "tenant", None)
        if tenant is None or tenant.schema_name == get_public_schema_name():
            return get_zone(DEFAULT_TIMEZONE)
        return get_company_timezone(company_id=tenant.pk)


# Let's Understand CompanyTimezoneMiddleware
# The big picture
# This is a Django middleware — a piece of code that runs on every single request to your app, before your views run.

# What it does, in one sentence:

# "For each incoming request, figure out which company (tenant) is asking, look up that company's timezone, and make that timezone active for the rest of the request."

# So when your view calls timezone.localtime(...) or saves a datetime, it automatically uses the right company's timezone — without every view having to pass it around manually.

# Think of it like an airport arrivals hall. Before you go anywhere in the country, you pass through a desk that sets your watch to local time. Every traveler gets the right local time automatically. You don't have to think about it. That desk is the middleware.

# What is middleware?
# Quick refresher, since it's central here.

# Middleware is code that sits between the web server and your views. Every request passes through it on the way in, and every response passes through it on the way out.

# text
# Request → [Middleware 1] → [Middleware 2] → [Your view] → [Middleware 2] → [Middleware 1] → Response
# Django runs your middleware in order on the request, and in reverse order on the response.

# The two "hook" methods
# A middleware class has two required methods:

# Method	When it runs
# __init__(self, get_response)	Once, at startup — when the middleware is first loaded
# __call__(self, request)	On every request — this is the actual work
# The get_response parameter is a callable — the next step in the chain (either the next middleware, or your view if this is the last one).

# The magic trick: calling self.get_response(request) passes the request forward to the next step. Whatever it returns is the response — which you must return.

# Line-by-line breakdown
# The class declaration
# python
# class CompanyTimezoneMiddleware:
# We're defining a middleware class named CompanyTimezoneMiddleware. The name is descriptive: "middleware that sets the company timezone."

# __init__ — the startup phase
# python
# def __init__(self, get_response):
#     self.get_response = get_response
# This runs once, when Django starts up.

# get_response → the next step in the middleware chain (a callable).

# self.get_response = get_response → save it on self, so we can call it later on every request.

# That's the entire __init__. It just memorizes get_response. This is the standard Django middleware pattern — nearly every middleware looks exactly like this.

# Why save it? Because __init__ runs once, but __call__ runs thousands of times. We need to keep a reference to get_response around so that __call__ can use it.

# __call__ — the per-request work
# python
# def __call__(self, request):
#     with timezone.override(self._resolve(request)):
#         return self.get_response(request)
# This is the heart of the middleware. Two lines. Let's unpack each.

# The body of __call__
# python
# with timezone.override(self._resolve(request)):
#     return self.get_response(request)
# Reading it top to bottom:

# self._resolve(request) — figure out the right timezone for this request (more below).

# timezone.override(...) — temporarily activate that timezone for the duration of a with block.

# Inside the block: return self.get_response(request) — pass the request to the next step (the view). Whatever the view returns is returned.

# When the with block exits, the previous timezone is restored.

# Why a with block? Because middleware runs in the same thread as the view, and that thread handles many requests over its lifetime. If we set the timezone and never restored it, the next request on the same thread would inherit the previous request's timezone. Bad.

# with timezone.override(...) is a context manager — it guarantees to restore the old value, even if the view raises an exception. That's the safety net.

# timezone.override — a Django utility from django.utils.timezone. It temporarily changes the active timezone (the one that timezone.localtime(), date formatting, etc., use by default). When you exit the with block, the old timezone is restored.

# What "active" means here: Django has a thread-local concept of "current timezone." Many Django functions read it. So by setting it here once, every code path in the view — and every template rendering, every form, every filter — automatically uses this company's timezone as the default. Elegant.

# The order matters, by the way. We must set the timezone before calling self.get_response(request). That way, the view runs inside the override. If we set it after, the view would run with the wrong (previous) timezone.

# The _resolve static method
# python
# @staticmethod
# def _resolve(request):
#     tenant = getattr(request, "tenant", None)
#     if tenant is None or tenant.schema_name == get_public_schema_name():
#         return get_zone(DEFAULT_TIMEZONE)
#     return get_company_timezone(company_id=tenant.pk)
# Purpose: Given a request, figure out which timezone to use. Three possible scenarios:

# No tenant on this request → use the default timezone.

# Public schema (the shared "no specific company" space) → use the default timezone.

# A real company's tenant → use that company's timezone.

# Let's walk through the code.

# @staticmethod
# This decorator means "this method doesn't need self — it doesn't touch the instance."

# Notice _resolve takes request as its parameter — not self. It doesn't need to remember anything from the middleware instance. It's a pure utility that just takes a request and returns a timezone.

# You'd call it as self._resolve(request) (through the instance) or CompanyTimezoneMiddleware._resolve(request) (through the class). Both work.

# tenant = getattr(request, "tenant", None)
# "Get the request.tenant attribute if it exists; otherwise return None."

# What is request.tenant? In django-tenants (a popular multi-tenancy library for Django), a previous middleware — typically TenantMainMiddleware — reads the hostname (or domain) of the incoming request and attaches the matching tenant object to request.tenant.

# For example:

# acme.myapp.com → request.tenant = Company "Acme"

# globex.myapp.com → request.tenant = Company "Globex"

# So by the time our middleware runs, request.tenant should already be set. But we can't assume — if TenantMainMiddleware isn't in the chain, or the request is for a domain with no tenant, request.tenant won't exist. That's why we use getattr with a default of None.

# getattr(obj, name, default) — "Get attribute name from obj. If it doesn't exist, return default instead of raising AttributeError." Safe lookup.

# The first branch
# python
# if tenant is None or tenant.schema_name == get_public_schema_name():
#     return get_zone(DEFAULT_TIMEZONE)
# Two conditions, joined by or:

# Condition 1: tenant is None

# No tenant at all. This happens on:

# Health checks — GET /health from a load balancer.

# Admin of the shared database — the central admin site.

# Local development — when the hostname isn't mapped to any company.

# Static file requests — sometimes not routed through tenant resolution.

# For all these, we can't look up a company. Fall back to the default.

# Condition 2: tenant.schema_name == get_public_schema_name()

# The request does have a tenant, but it's the public schema.

# What's a schema? In a shared-database multi-tenant setup (like django-tenants), all companies share one physical database, but each company has its own schema — a namespace of tables.

# public schema → the shared stuff — the login page, signup, the list of companies. Everyone lands here before logging in. No specific company.

# acme schema → Acme's isolated data. Only accessible when the request is for acme.myapp.com.

# get_public_schema_name() returns the name of the public schema — usually the string "public".

# So this condition means: "This request is for the shared/public space, not any specific company's space."

# In both cases, we don't have a company timezone — so return the default.

# get_zone(DEFAULT_TIMEZONE) — turn the string "Africa/Nairobi" (or whatever DEFAULT_TIMEZONE is) into a timezone object. get_zone is a helper (probably from zoneinfo or pytz) that converts a name into a usable timezone. It returns something you can pass to timezone.override.

# Why DEFAULT_TIMEZONE? It's a constant defined elsewhere — the app's fallback. Probably matches settings.TIME_ZONE. This is the same DEFAULT_TIMEZONE used in timezone_choices() earlier — the one that's always offered in the dropdown.

# The second branch (a real company)
# python
# return get_company_timezone(company_id=tenant.pk)
# If we got this far, there is a tenant, and it's not the public schema. This is a real company's request.

# tenant.pk → the primary key (the database ID) of the tenant row. For django-tenants, tenant is often a Company (or Client) model instance. tenant.pk = that company's row ID.

# get_company_timezone(company_id=...) → a helper function (elsewhere in the codebase) that looks up the company's saved timezone setting. Probably queries something like:

# python
# Company.objects.values_list("timezone", flat=True).get(pk=company_id)
# — that's the .values_list("timezone", flat=True) from your earlier question! It fetches only the timezone string, nothing else. Lean and fast.

# Then converts the string to a timezone object (probably via get_zone) and returns it.

# Result: something like <ZoneInfo 'Africa/Nairobi'> — usable in timezone.override.

# If the company has no timezone set? That's get_company_timezone's job — probably it falls back to DEFAULT_TIMEZONE. Not shown here, but that would be the sensible design.

# The full flow, end to end
# Let's trace a request.

# Request 1 — acme.myapp.com/invoices
# text
# 1. TenantMainMiddleware runs.
#    → Sees hostname "acme.myapp.com"
#    → Looks up tenant, sets request.tenant = <Company: Acme, pk=42>

# 2. CompanyTimezoneMiddleware.__call__ runs.
#    → Calls self._resolve(request)
#      → tenant = <Company: Acme, pk=42>
#      → tenant is not None → condition 1 false
#      → tenant.schema_name = "acme" ≠ "public" → condition 2 false
#      → Falls through to: return get_company_timezone(company_id=42)
#      → get_company_timezone(42) → <ZoneInfo 'Europe/London'>  (Acme's tz)
#    → with timezone.override(<ZoneInfo 'Europe/London'>):
#      → self.get_response(request) → runs the view, returns Response
#    → with-block exits → previous tz restored

# 3. Response flows back up.
# Result: inside the view, all datetime operations default to London time — because Acme is in London. Even though the server might be in UTC, or Nairobi, or anywhere.

# Request 2 — myapp.com/signup (public page)
# text
# 1. TenantMainMiddleware runs.
#    → Hostname has no company match
#    → Falls to public schema
#    → request.tenant = <Client: public, schema_name="public">

# 2. CompanyTimezoneMiddleware.__call__ runs.
#    → Calls self._resolve(request)
#      → tenant = public tenant
#      → condition 2: tenant.schema_name == "public" → TRUE
#      → return get_zone(DEFAULT_TIMEZONE)
#    → with timezone.override(get_zone(DEFAULT_TIMEZONE)):
#      → self.get_response(request) → runs the signup view
#    → with-block exits

# 3. Response flows back up.
# Result: on the shared public page (signup, login, marketing), we use the default timezone — because there is no specific company yet. Makes sense.

# Request 3 — a health check
# text
# 1. No TenantMainMiddleware (or it doesn't match)
#    → request.tenant doesn't exist

# 2. CompanyTimezoneMiddleware.__call__ runs.
#    → Calls self._resolve(request)
#      → getattr(request, "tenant", None) → None
#      → condition 1: tenant is None → TRUE
#      → return get_zone(DEFAULT_TIMEZONE)

# 3. Same as above — default tz.
# Result: health checks use the default. Safe and predictable.

# Why this design is powerful
# Consider the alternative — manually passing the timezone everywhere:

# python
# def invoice_list(request):
#     tz = get_company_timezone(company_id=request.tenant.pk)   # look up
#     invoices = Invoice.objects.filter(created_at__gte=...)
#     for inv in invoices:
#         local_time = inv.created_at.astimezone(tz)   # convert manually
#         # ... every single view has to do this
# This is exhausting and bug-prone. Someone forgets to convert in one view — that view silently shows wrong times. Users complain. You spend hours tracking it down.

# With the middleware, every view just works:

# python
# def invoice_list(request):
#     invoices = Invoice.objects.filter(created_at__gte=...)
#     # Django already knows this company's tz — no manual conversion
#     return render(request, "invoices.html", {"invoices": invoices})
# Template rendering also benefits. If a template does:

# django
# {{ invoice.created_at|date:"Y-m-d H:i" }}
# Django automatically renders it in the active timezone — which the middleware set. No view code needed.

# This is the essence of middleware: cross-cutting concerns. Things that should happen on every request (auth, logging, timezone, request ID) belong in middleware — so views stay focused on their own logic.

# A subtle but important detail: thread safety
# Django's timezone is thread-local. Each thread has its own "current timezone."

# Why does this matter?

# If the middleware used a global variable, two simultaneous requests (Acme's and Globex's) would overwrite each other's timezone — chaos.

# With thread-local, Acme's thread has London, Globex's thread has New York. No interference.

# Django handles this. timezone.override(...) is thread-safe. You don't have to do anything. But it's why Django chose this design — and why you should not try to set the timezone via os.environ or a global variable.

# The with block's restoration is also thread-safe — the restore happens in the same thread that set it.

# Summary table
# Piece	Meaning
# CompanyTimezoneMiddleware	A Django middleware that sets the active timezone per request
# __init__(self, get_response)	Runs once at startup — saves get_response
# __call__(self, request)	Runs on every request — does the actual work
# self.get_response(request)	Passes the request forward — to the next middleware or the view
# with timezone.override(...):	Temporarily sets the timezone; restores the old one on exit
# self._resolve(request)	Decides which timezone to use
# @staticmethod	_resolve doesn't need self
# getattr(request, "tenant", None)	Safely get request.tenant (or None)
# tenant is None	No tenant → use the default tz
# tenant.schema_name == "public"	Public/shared schema → use the default tz
# get_zone(DEFAULT_TIMEZONE)	Turn the default string into a timezone object
# tenant.pk	The company's primary key
# get_company_timezone(company_id=...)	Look up this company's saved timezone
# timezone.override	Sets the "active" tz (thread-local) that Django uses by default
# One-line summary
# CompanyTimezoneMiddleware is a per-request timezone switcher. It looks at which company the request is for, sets the active timezone to that company's timezone, runs the view inside that setting, and then restores the previous one. Every view, template, and form in the app then automatically uses the right timezone — without anyone having to think about it.

