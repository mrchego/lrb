from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lrb.identity"
    label = "identity"
    verbose_name = _("Identity")
    
    def ready(self):
        # Import signals if needed
        pass
