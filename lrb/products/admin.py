from django.contrib import admin
from lrb.core.admin import BaseModelAdmin
from lrb.products.models import Product


@admin.register(Product)
class ProductAdmin(BaseModelAdmin):
    list_display = ["name", "sku", "price", "company", "is_active", "created_at"]
    list_filter = ["is_active", "company"]
    search_fields = ["name", "sku"]