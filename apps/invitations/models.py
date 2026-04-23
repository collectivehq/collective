from __future__ import annotations

import datetime
import uuid

from apps.core.models import AcceptableModel, BaseModel, RejectableModel
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_invite_expiry() -> datetime.datetime:
    return timezone.now() + datetime.timedelta(days=settings.INVITE_DEFAULT_EXPIRY_DAYS)


class SpaceInvite(BaseModel, AcceptableModel, RejectableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("spaces.Space", on_delete=models.CASCADE, related_name="invites")
    role = models.ForeignKey("spaces.Role", on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField(blank=True, default="", db_index=True)
    expires_at = models.DateTimeField(default=default_invite_expiry, db_index=True)
    last_sent_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "space_invites"
        verbose_name = "space invite"
        verbose_name_plural = "space invites"

    def __str__(self) -> str:
        if self.email:
            return f"Invite {self.email} to {self.space} as {self.role}"
        return f"Invite to {self.space} as {self.role}"

    def clean(self) -> None:
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.role_id is not None and self.role is not None and self.role.space_id != self.space_id:
            raise ValidationError({"role": "Role must belong to the invite's space."})

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_email_invite(self) -> bool:
        return bool(self.email)


__all__ = ["SpaceInvite", "default_invite_expiry"]
