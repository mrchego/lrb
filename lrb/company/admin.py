from django.contrib import admin
from lrb.core.admin import BaseModelAdmin
from lrb.company.models.company import Company

@admin.register(Company)
class CompanyAdmin(BaseModelAdmin):
    # Inherits 'id', 'created_at', 'updated_at' and date_hierarchy automatically!
    list_display = ['name', 'email', 'phone', 'country', 'city', 'is_active', 'created_at']
    list_filter = ['is_active', 'country', 'created_at']
    search_fields = ['name', 'email', 'phone', 'city']
    ordering = ['name']
    
    # Because Company uses fields, we add them to readonly_fields (additive)
    fieldsets = (
        (None, {'fields': ('name', 'email', 'phone', 'is_active')}),
        ('Location', {'fields': ('country', 'city', 'address')}),
        ('Branding', {'fields': ('logo_light', 'logo_dark')}),
        ('Audit', {'fields': ('id', 'created_at', 'updated_at')}),
    )

# @admin.register(CompanySettings)
# class CompanySettingsAdmin(BaseModelAdmin):
#     list_display = ['company', 'currency', 'timezone', 'theme']
#     list_filter = ['currency', 'timezone']