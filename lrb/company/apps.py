from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CompanyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lrb.company"
    label = "company"
    verbose_name = _("Company")

    def  ready(self):
            pass






    
    
    
    