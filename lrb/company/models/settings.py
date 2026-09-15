from django.db import models
from lrb.company.models.company import Company
from lrb.core.models.base import BaseModel


class CompanySettings(BaseModel):
    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, related_name="settings"
    )
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=10, default="KES")
    language = models.CharField(max_length=10, default="en")
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")
    theme = models.CharField(max_length=20, default="light")

    class Meta:
        ordering = ["company__name"]

    def __str__(self):
        return f"{self.company.name} Settings"
