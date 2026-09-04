from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from lrb.core.admin import BaseModelAdmin
from lrb.accounts.forms import UserAdminChangeForm, UserAdminCreationForm
from lrb.accounts.models import User

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)


@admin.register(User)
class UserAdmin(BaseModelAdmin, auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = ['email', 'first_name', 'last_name', 'company', 'can_login', 'is_active', 'created_at']
    list_filter = ['can_login', 'is_active', 'is_staff', 'is_superuser', 'company', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['id']  # UUID pk isn't shown by default; useful for GraphQL debugging/support

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "avatar")}),
        (_("Organization"), {"fields": ("company",)}),
        (_("Security & Login"), {"fields": ("can_login", "password_reset_required", "locked_until", "failed_login_attempts")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    # REMOVED: "groups", "user_permissions"
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "last_password_change")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )