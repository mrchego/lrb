import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from lrb.core.models.base import BaseModel


class Invitation(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    company = models.ForeignKey(
        "company.Company", on_delete=models.CASCADE, related_name="invitations"
    )
    invited_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    role = models.ForeignKey(
        "authorization.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def _assert_same_company(self) -> None:
        if self.role_id and self.role.company_id != self.company_id:
            raise ValidationError("An invitation's role must belong to its company.")

    def clean(self):
        self._assert_same_company()

    def save(self, *args, **kwargs):
        self._assert_same_company()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation for {self.email} ({self.company.name})"
