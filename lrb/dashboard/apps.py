from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lrb.dashboard"
    label = "dashboard"
    verbose_name = _("Dashboard")
    
    def ready(self):
        # Import signals if needed
        pass