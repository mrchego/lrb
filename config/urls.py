from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from strawberry.django.views import GraphQLView
from config.schema import schema

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # User management
    # path("accounts/", include("lrb.accounts.urls", namespace="accounts")),
    # Your stuff: custom urls includes go here
    path(
        "graphql/",
        csrf_exempt(
            GraphQLView.as_view(
                schema=schema,
                multipart_uploads_enabled=True,  # required for Upload scalar / file uploads
            )
        ),
    ),
    # ...
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]



# 1. Purpose

# This is a URL route definition — a single entry in Django's URL configuration (typically urls.py) that tells Django: "when a request comes in for the path graphql/, hand it to this specific view." This is the exact line your own project notes describe: "GraphQL served at /graphql/ via csrf_exempt(GraphQLView.as_view(schema=schema))." Everything you've built today — every service, selector, model, and GraphQL type — is ultimately reachable because this one line exists, wiring a URL to the code that can actually process a GraphQL request.

# 2. What is it? — every piece, explained from scratch
# python
# path(
#     "graphql/",
#     csrf_exempt(
#         GraphQLView.as_view(
#             schema=schema,
#             multipart_uploads_enabled=True,
#         )
#     ),
# ),
# path(...) — a Django function (imported from django.urls) that builds one URL routing rule. It's not shown here, but this line would sit inside a list, typically called urlpatterns, that Django reads top to bottom when deciding which view handles an incoming request.
# First argument, "graphql/" — the URL pattern to match. This is a plain string — no wildcards or parameters here — meaning this rule only matches a request to exactly /graphql/ (Django automatically handles whatever comes before this, like your domain and any URL-prefix configured elsewhere).
# Second argument — the view: the actual callable Django hands the request to once the path matches. This is where nearly all the interesting machinery lives, and it's built up in layers, from the inside out.
# 3. Signature — breaking down the nested calls, inside-out

# This is a great moment to apply the exact "evaluate nested calls inside-out" reading strategy your own project notes say you want to build. Let's do that explicitly, one layer at a time, starting from the innermost call and working outward.

# Layer 1 (innermost): GraphQLView.as_view(...)

# python
# GraphQLView.as_view(
#     schema=schema,
#     multipart_uploads_enabled=True,
# )
# GraphQLView — a class, imported from Strawberry's Django integration (strawberry.django.views.GraphQLView or similar) — this is the class whose job is to receive an HTTP request, parse it as a GraphQL query, run it against your schema, and return a GraphQL-shaped response.
# .as_view(...) — this is a Django class-based view convention, not something Strawberry invented. Django URL routing needs a plain function to call for each incoming request — but GraphQLView is a class, with its own internal state and methods. .as_view(...) is a class method that bridges this gap: it takes your class, configures it with whatever keyword arguments you pass in, and returns an ordinary function that Django's URL routing can call directly. Every request to /graphql/ calls that returned function, which internally creates a fresh GraphQLView instance configured with your settings and dispatches the request to it.
# schema=schema — passes in your actual GraphQL schema object (the one composed in config/schema.py, per your project notes — combining AuthMutation, ProductQuery, SessionQuery, and every other @strawberry.type you've built today into one unified API). This is what GraphQLView actually executes incoming queries against.
# multipart_uploads_enabled=True — a specific configuration flag Strawberry's GraphQLView understands. The comment right above it in your code already tells you what it's for: enabling GraphQL's Upload scalar type, which lets a client send an actual file (an image, a document) as part of a GraphQL mutation, using a different request encoding than a normal JSON-only GraphQL call. Without this flag, GraphQLView wouldn't know to parse that special multipart format at all — file-upload mutations would simply fail.

# Layer 2: csrf_exempt(...)

# python
# csrf_exempt(
#     GraphQLView.as_view(schema=schema, multipart_uploads_enabled=True)
# )
# csrf_exempt — a Django function (a decorator, but here used as a plain function call rather than with @ syntax — you'll see why in a moment) that takes a view and returns a version of it with Django's built-in CSRF (Cross-Site Request Forgery) protection turned off for that view specifically.
# Why turn CSRF protection off here, specifically? Django's default CSRF protection expects a specific token to be included with certain kinds of requests (like a form's hidden CSRF field), matched against a value stored in the user's session/cookie. GraphQL clients (especially non-browser clients, or a frontend making raw fetch() calls) generally don't participate in that Django-specific token dance — they just POST a JSON body containing a query. Rather than requiring every GraphQL client to somehow learn and replay Django's CSRF token scheme (which GraphQL wasn't designed around), the common, practical choice — the one this project has made — is to exempt just this one endpoint from that specific protection mechanism.
# Why is this csrf_exempt(...) used as a direct function call instead of @csrf_exempt above a def? Because there's no def here to decorate — GraphQLView.as_view(...) is an expression, evaluated once, producing a plain function, right here in the middle of building this URL pattern. csrf_exempt needs something already built to wrap — so it's called directly on the result of .as_view(...), rather than being written as a decorator syntax that would only apply to a function you're defining with def right below it. Same tool (csrf_exempt), same effect, just used in its "plain function call" form rather than its "@ syntax" form because of where in the code it's needed.

# Layer 3 (outermost): path("graphql/", ...)

# The fully-built, CSRF-exempt, schema-configured view (everything from Layers 1 and 2) is passed as the second argument to path(...), completing the URL rule.

# 4. Why is it written this way?
# Function composition, not separate steps — this whole thing could have been written more verbosely:
# python
#   view = GraphQLView.as_view(schema=schema, multipart_uploads_enabled=True)
#   exempt_view = csrf_exempt(view)
#   urlpatterns = [path("graphql/", exempt_view)]

# Writing it nested instead, as one expression, is a stylistic choice common in Django urls.py files specifically — since this configuration is typically only built once, at startup, and never reused elsewhere, there's little benefit to naming each intermediate step with its own variable. It's the same "why not just name it?" question worth asking of any deeply-nested expression — here, the honest answer is: because nothing later in the file needs to refer back to the intermediate view or exempt_view on their own.

# A single endpoint for the entire GraphQL API — this is a defining trait of GraphQL as an architecture, worth understanding in contrast to what you might expect from a REST API: a typical Django REST API might have dozens of URL patterns (/products/, /products/<id>/, /users/, etc.), one per resource. GraphQL flips that entirely — there's exactly one URL, /graphql/, and every query and mutation you've written today (login, products, bulkActivateUsers, all of it) is routed through this single endpoint. The schema itself — not the URL structure — is what determines which operation actually runs; the URL's only job is to get every request to the one place that can read the request body and dispatch based on its contents.
# 5. Connections
# This is the literal front door to everything you've built today. Every resolver method inside AuthMutation, ProductQuery, SessionQuery — none of them are reachable by a client until a request lands here first. GraphQLView reads the incoming query, matches it against the combined schema object, and calls the correct @strawberry.field/@strawberry.mutation method behind the scenes.
# Directly connects to info: strawberry.Info, a parameter you've now seen in nearly every resolver today. GraphQLView is the piece of machinery that actually constructs that info object for each request — attaching things like info.context.request (the underlying Django HttpRequest, which you saw django_login/django_logout and get_current_user rely on) before handing control off to whichever resolver the query is asking for.
# multipart_uploads_enabled=True hints at a feature you haven't seen elsewhere today — some mutation somewhere in this project almost certainly accepts a file upload (a product image, perhaps, given everything you've read about Product) using Strawberry's Upload scalar type, which this flag is a prerequisite for.
# 6. Advanced concepts

# Class-based views vs. function-based views, and why .as_view() exists at all: Django was originally built around plain view functions — def my_view(request): ... — because a URL route just needs something callable with a request. A class like GraphQLView is more powerful (it can hold configuration, share logic across HTTP methods, etc.) but isn't itself callable the way a plain function is — you can't just plug a class directly into path(...) and have Django know what to do with it. .as_view(...) is the standard bridge: it's a class method (defined on Django's own base View class, which GraphQLView ultimately inherits from) that returns a genuine function wrapping the class, configured with whatever you passed to .as_view(...). This is a pattern you'll see anywhere Django (or a library built on top of it) offers a class-based view — always paired with .as_view() at the point where it's actually wired into a URL.

# 7. Small example
# python
# from django.urls import path
# from django.views.decorators.csrf import csrf_exempt
# from django.views import View

# class PingView(View):
#     def get(self, request):
#         return HttpResponse("pong")

# urlpatterns = [
#     path("ping/", csrf_exempt(PingView.as_view())),
# ]

# Same shape, much simpler: a class-based view, turned into a callable via .as_view(), wrapped in csrf_exempt, wired to a URL — exactly the pattern your GraphQL route follows, just with a trivial view instead of an entire GraphQL schema behind it.

# 8. What to remember
# .as_view() is the standard bridge between a Django class-based view and the plain callable Django's URL routing actually needs — expect to see it paired with any class-based view wired into urlpatterns.
# csrf_exempt can be used as a direct function call on an already-built view, not just as @csrf_exempt above a def — same tool, different syntax form, chosen based on whether you're decorating a function definition or wrapping an already-constructed callable expression.
# GraphQL APIs typically expose exactly one URL — unlike REST's many endpoints, the schema itself (not the URL) determines what a given request actually does, which is why this single path("graphql/", ...) line is enough to serve every resolver you've built today.
# Reading deeply nested function calls inside-out (innermost first) is the correct way to untangle a line like this — you resolved GraphQLView.as_view(...) first, then csrf_exempt(...) around it, then path(...) around that, which is exactly the order Python itself evaluates them in.
# This single line is the literal connection point between the URL a client actually requests and the entire GraphQL schema you've spent this whole conversation reading — every model, selector, service, input, payload, and resolver you've studied today is inert code until a request lands here and gets routed into it.