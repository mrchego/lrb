from django.db import models

from lrb.company.models.company import Company
from lrb.core.models.base import BaseModel


class CurrencyConversion(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="currency_conversions")
    from_currency = models.CharField(max_length=10)
    to_currency = models.CharField(max_length=10)
    rate = models.DecimalField(max_digits=30, decimal_places=12)  # 1 from = rate to
    rows_converted = models.JSONField(default=dict)               # {"products": 120}
    # No FK to User: this table is in the public schema, users live in tenant schemas.
    converted_by_id = models.UUIDField(null=True, blank=True)
    converted_by_email = models.EmailField(blank=True)

    class Meta:
        ordering = ["-created_at"]