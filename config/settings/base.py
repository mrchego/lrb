# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""
import os
import ssl
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# lrb/
APPS_DIR = BASE_DIR / "lrb"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
DEBUG = env.bool("DJANGO_DEBUG", False)
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
SITE_ID = 1
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
if os.getenv("DATABASE_URL", default=None):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("POSTGRES_DB"),
            "USER": env.str("POSTGRES_USER"),
            "PASSWORD": env.str("POSTGRES_PASSWORD"),
            "HOST": env.str("POSTGRES_HOST", default="postgres"),
            "PORT": env.str("POSTGRES_PORT", default="5432"),
        },
    }

DATABASES["default"]["ATOMIC_REQUESTS"] = True
# TENANCY: schema-aware Postgres backend. Applies to BOTH branches above,
# so it must come after the if/else.
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"
DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]  # TENANCY

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# TENANCY: two URL confs. Tenant hosts (acme.localhost) get ROOT_URLCONF,
# the platform host (localhost) gets PUBLIC_SCHEMA_URLCONF.
ROOT_URLCONF = "config.urls_tenant"
PUBLIC_SCHEMA_URLCONF = "config.urls_public"
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
# TENANCY: SHARED_APPS live in the `public` schema. TENANT_APPS get their own
# tables inside every company's schema. An app listed in BOTH gets tables in
# both places (accounts: platform operators in public, company users per tenant).
SHARED_APPS = [
    "django_tenants",  # must be first
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",  # platform admin only (no admin on tenant hosts)
    "django.forms",
    # third party
    "corsheaders",
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "django_celery_beat",
    "strawberry_django",
    # local, public schema
    "lrb.core.apps.CoreConfig",
    "lrb.company.apps.CompanyConfig",  # Company (the tenant), Domain, CompanySettings
    "lrb.accounts.apps.AccountsConfig",  # public copy = platform operators only
]

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",  # per-schema sessions: a session can't cross companies
    "lrb.accounts.apps.AccountsConfig",
    "lrb.authorization.apps.AuthorizationConfig",
    "lrb.identity.apps.IdentityConfig",
    "lrb.staff.apps.StaffConfig",
    "lrb.products.apps.ProductsConfig",
    "lrb.dashboard.apps.DashboardConfig",
    # add lrb.categories / lrb.orders here when you install them
]

# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

# TENANCY
# ------------------------------------------------------------------------------
TENANT_MODEL = "company.Company"
TENANT_DOMAIN_MODEL = "company.Domain"
# Companies live at <slug>.<TENANT_BASE_DOMAIN>; the platform lives at the bare domain.
TENANT_BASE_DOMAIN = env("TENANT_BASE_DOMAIN", default="localhost")
# Invitation emails etc. build the company's frontend link from this.
FRONTEND_URL_TEMPLATE = env("FRONTEND_URL_TEMPLATE", default="http://{slug}.localhost:3000")

# MIGRATIONS
# ------------------------------------------------------------------------------
MIGRATION_MODULES = {"sites": "lrb.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# TENANCY: ModelBackend only. allauth's backend can resolve users through its
# public-schema EmailAddress table, which has no business on tenant hosts, and
# your login/verify/reset flows are custom OTP anyway.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "accounts:redirect"
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "lrb.core.middleware.TenantMiddleware",  # TENANCY: must be FIRST
    "lrb.core.middleware.RequireGraphQLPreflightMiddleware",  # TENANCY
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "lrb.core.middleware.CompanyTimezoneMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# SESSIONS  (TENANCY)
# ------------------------------------------------------------------------------
# DB sessions live in each company's own schema.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# Host-only cookie. NEVER set this to ".yourdomain.com": that would share one
# session cookie across every company's subdomain.
SESSION_COOKIE_DOMAIN = None

# STATIC
# ------------------------------------------------------------------------------
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(APPS_DIR / "static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(APPS_DIR / "media")
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "lrb.accounts.context_processors.allauth_settings",
            ],
        },
    },
]

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
ADMIN_URL = "admin/"
ADMINS = ['"Francis Chege" <mrchegoprime@gmail.com>']
MANAGERS = ADMINS
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# LOGGING
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = REDIS_URL
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_SSL else None
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# django-allauth (platform/public site only)
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_ADAPTER = "lrb.accounts.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "lrb.accounts.forms.UserSignupForm"}
SOCIALACCOUNT_ADAPTER = "lrb.accounts.adapters.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "lrb.accounts.forms.UserSocialSignupForm"}

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", ".localhost", "admin.localhost"],
)

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://*.localhost:8000",
]

# Your stuff...
# ------------------------------------------------------------------------------
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")  # platform site