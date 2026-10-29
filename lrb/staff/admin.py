from django.contrib import admin
from lrb.core.admin import BaseModelAdmin
from lrb.staff.models import Invitation


@admin.register(Invitation)
class InvitationAdmin(BaseModelAdmin):
    list_display = ["email", "company", "role", "invited_by", "used", "accepted_at", "created_at"]
    list_filter = ["used", "company"]
    search_fields = ["email"]