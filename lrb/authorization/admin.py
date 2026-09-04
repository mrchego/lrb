# lrb/authorization/admin.py
from django.contrib import admin
from django.db.models import Count

from lrb.core.admin import BaseModelAdmin
from lrb.authorization.models.permission import Permission 
from lrb.authorization.models.role import Role
from lrb.authorization.models.user_role import UserRole, UserPermissionOverride


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------
@admin.register(Permission)
class PermissionAdmin(BaseModelAdmin):
    """
    Permissions are seeded from PERMISSION_REGISTRY via the sync_permissions
    management command — admins should never hand-create or rename these,
    only see what exists and which roles use them.
    """

    list_display = ["codename", "label", "category", "role_count"]
    list_filter = ["category"]
    search_fields = ["codename", "label"]
    ordering = ["category", "codename"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_role_count=Count("roles"))

    @admin.display(description="Roles using this", ordering="_role_count")
    def role_count(self, obj):
        return obj._role_count

    def has_add_permission(self, request):
        # Keep the registry as the single source of truth for what exists.
        return False

    def has_change_permission(self, request, obj=None):
        # codename/label/category are code-defined; nothing here should be edited by hand.
        return False


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------
class UserRoleInline(admin.TabularInline):
    """Shows (and lets you manage) which staff currently hold this role."""

    model = UserRole
    extra = 1
    autocomplete_fields = ["user"]
    verbose_name = "Assigned staff member"
    verbose_name_plural = "Assigned staff"


@admin.register(Role)
class RoleAdmin(BaseModelAdmin):
    list_display = [
        "name",
        "company",
        "is_default",
        "permission_count",
        "staff_count",
        "created_at",
    ]
    list_filter = ["is_default", "company"]
    search_fields = ["name", "company__name"]
    ordering = ["company", "name"]
    filter_horizontal = ["permissions"]
    inlines = [UserRoleInline]
    readonly_fields = ['id']

    fieldsets = (
        (None, {"fields": ("id","company", "name", "is_default")}),
        ("Permissions", {"fields": ("permissions",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("company")
            .annotate(
                _permission_count=Count("permissions", distinct=True),
                _staff_count=Count("user_roles", distinct=True),
            )
        )

    @admin.display(description="Permissions", ordering="_permission_count")
    def permission_count(self, obj):
        return obj._permission_count

    @admin.display(description="Staff", ordering="_staff_count")
    def staff_count(self, obj):
        return obj._staff_count


# ---------------------------------------------------------------------------
# UserRole (direct assignment table — useful for bulk lookups/edits
# outside the context of a single Role's inline)
# ---------------------------------------------------------------------------
@admin.register(UserRole)
class UserRoleAdmin(BaseModelAdmin):
    list_display = ["user", "role", "company", "created_at"]
    list_filter = ["role__company", "role"]
    search_fields = ["user__email", "role__name"]
    autocomplete_fields = ["user", "role"]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "role", "role__company")
        )

    @admin.display(description="Company", ordering="role__company")
    def company(self, obj):
        return obj.role.company


# ---------------------------------------------------------------------------
# UserPermissionOverride
# ---------------------------------------------------------------------------
@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(BaseModelAdmin):
    list_display = ["user", "permission", "is_granted", "created_at"]
    list_filter = ["is_granted", "permission__category"]
    search_fields = ["user__email", "permission__codename"]
    autocomplete_fields = ["user", "permission"]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "permission")
