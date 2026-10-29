from django.contrib import admin
from lrb.core.admin import BaseModelAdmin
from lrb.identity.models import VerificationCode


@admin.register(VerificationCode)
class VerificationCodeAdmin(BaseModelAdmin):
    list_display = ["user", "purpose", "code", "expires_at", "used_at", "created_at"]
    list_filter = ["purpose"]
    search_fields = ["user__email", "code"]