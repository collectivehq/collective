from __future__ import annotations

from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    """Tracks creation metadata for persistent records."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdateableModel(models.Model):
    """Tracks the last update timestamp for mutable records."""

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DeletableModel(models.Model):
    """Supports soft deletion for records that should remain recoverable."""

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class OrderableModel(models.Model):
    """Provides a stable sequence index for ordered records."""

    sequence_index = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True


class ResolvableModel(models.Model):
    """Tracks resolution state for records with a resolution lifecycle."""

    resolution_type = models.CharField(max_length=20, blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class CRUDModel(BaseModel, UpdateableModel, DeletableModel):
    """Full lifecycle abstract model for created, updated, soft-deleted records."""

    class Meta:
        abstract = True
