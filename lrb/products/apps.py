from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lrb.products"
    label = "products"
    verbose_name = _("Products")

    def ready(self):
        from lrb.core.money.usage import register_money_usage_check
        from lrb.products.models import Product
        register_money_usage_check(lambda *, company: Product.objects.filter(company=company).exists())