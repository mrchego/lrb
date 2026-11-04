import io

from django.apps import apps
from django.contrib import admin, messages
from django.core.management import call_command
from django.db import transaction
from django.utils.html import format_html
from django_tenants.utils import get_public_schema_name, tenant_context
from django.utils.safestring import mark_safe
from lrb.company.models.company import Company
from lrb.company.models.domain import Domain
from lrb.company.models.settings import CompanySettings
from lrb.core.admin import BaseModelAdmin


def _in_schema(company, fn, default="-"):
    """Run fn() inside the company's schema. A broken or unprovisioned schema
    raises a DB error that would abort the whole admin request's transaction, so
    it runs in a savepoint and falls back to `default`."""
    try:
        with transaction.atomic(), tenant_context(company):
            return fn()
    except Exception:
        return default


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0
    fields = ["domain", "is_primary"]


class CompanySettingsInline(admin.StackedInline):
    model = CompanySettings
    extra = 0
    can_delete = False
    fields = ["timezone", "currency", "language", "date_format", "theme"]


@admin.register(Company)
class CompanyAdmin(BaseModelAdmin):
    list_display = [
        "name",
        "slug",
        "status",
        "owner_email",
        "user_count",
        "product_count",
        "email",
        "country",
        "created_at",
    ]
    list_filter = ["is_active", "country", "created_at"]
    search_fields = [
        "name",
        "slug",
        "schema_name",
        "email",
        "phone",
        "city",
        "domains__domain",
    ]
    ordering = ["name"]
    list_per_page = 25
    inlines = [DomainInline, CompanySettingsInline]
    actions = [
        "suspend_companies",
        "activate_companies",
        "sync_permissions_for_companies",
    ]

    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "schema_name", "email", "phone")}),
        ("Status", {"fields": ("is_active",)}),
        ("Location", {"fields": ("country", "city", "address")}),
        ("Branding", {"fields": ("logo_light", "logo_dark")}),
        ("Usage", {"fields": ("owner_email", "user_count", "product_count")}),
        ("Audit", {"fields": ("id", "created_at", "updated_at")}),
    )

    # ---- guard rails -------------------------------------------------------
    def get_queryset(self, request):
        # The platform's own "public" tenant row is not a customer.
        return (
            super().get_queryset(request).exclude(schema_name=get_public_schema_name())
        )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        # Companies are provisioned (schema, domain, permissions, founder) only by
        # the register flow. A bare row created here would have no schema.
        return False

    def has_delete_permission(self, request, obj=None):
        # Suspend instead. Deleting never drops the schema and is blocked while
        # users exist; offboarding is a deliberate CLI procedure.
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        fields += ["slug", "schema_name", "owner_email", "user_count", "product_count"]
        return fields

    # ---- computed columns (each opens the company's schema once) -------------

    @admin.display(description="Status", ordering="is_active")
    def status(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="color:#15803d;font-weight:600">Active</span>'
            )
        return mark_safe('<span style="color:#b91c1c;font-weight:600">Suspended</span>')

    @admin.display(description="Founder")
    def owner_email(self, obj):
        from lrb.accounts.models import User

        return _in_schema(
            obj,
            lambda: getattr(User.objects.filter(is_founder=True).first(), "email", "-"),
        )

    @admin.display(description="Users")
    def user_count(self, obj):
        from lrb.accounts.models import User

        return _in_schema(obj, lambda: User.objects.count())

    @admin.display(description="Products")
    def product_count(self, obj):
        try:
            Product = apps.get_model("products", "Product")
        except LookupError:
            return "-"
        return _in_schema(obj, lambda: Product.objects.count())

    # ---- actions -----------------------------------------------------------
    @admin.action(description="Suspend selected companies (blocks all access)")
    def suspend_companies(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"Suspended {n} company(ies).", messages.WARNING)

    @admin.action(description="Reactivate selected companies")
    def activate_companies(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"Reactivated {n} company(ies).", messages.SUCCESS)

    @admin.action(description="Sync permission catalogue into selected companies")
    def sync_permissions_for_companies(self, request, queryset):
        done, failed = 0, []
        for company in queryset:
            try:
                with transaction.atomic(), tenant_context(company):
                    call_command("sync_permissions", stdout=io.StringIO())
                done += 1
            except Exception as exc:
                failed.append(f"{company.slug}: {exc}")
        if done:
            self.message_user(request, f"Synced {done} company(ies).", messages.SUCCESS)
        for line in failed:
            self.message_user(request, f"Failed - {line}", messages.ERROR)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "tenant", "is_primary"]
    list_filter = ["is_primary"]
    search_fields = ["domain", "tenant__name", "tenant__slug"]

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(tenant__schema_name=get_public_schema_name())
        )


@admin.register(CompanySettings)
class CompanySettingsAdmin(BaseModelAdmin):
    list_display = ["company", "currency", "timezone", "language", "theme"]
    list_filter = ["currency", "timezone", "language", "theme"]
    search_fields = ["company__name", "company__slug"]

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(company__schema_name=get_public_schema_name())
        )
