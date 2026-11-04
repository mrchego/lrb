from django.conf import settings
from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name

from lrb.company.models.company import Company
from lrb.company.models.domain import Domain

class Command(BaseCommand):
    help = "Create the platform (public) tenant row + its domain. Idempotent."

    def handle(self, *args, **options):
        public = get_public_schema_name()
        company, _ = Company.objects.get_or_create(
            schema_name=public,
            defaults=dict(slug=public, name="Platform", email="platform@lrb.local",
                          phone="+254700000000", country="KE", city="Nairobi", address="-"),
        )
        Domain.objects.get_or_create(
            domain=settings.TENANT_BASE_DOMAIN, defaults={"tenant": company, "is_primary": True}
        )
        self.stdout.write(self.style.SUCCESS("Public tenant ready."))