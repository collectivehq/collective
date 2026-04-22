from __future__ import annotations

import uuid

from django.db import models
from treebeard.mp_tree import MP_Node

from apps.core.models import CRUDModel, OrderableModel, ResolvableModel


class DiscussionQuerySet(models.QuerySet["Discussion"]):
    def active(self) -> DiscussionQuerySet:
        return self.filter(deleted_at__isnull=True)


class DiscussionManager(models.Manager["Discussion"]):
    def get_queryset(self) -> DiscussionQuerySet:
        return DiscussionQuerySet(self.model, using=self._db)


class Discussion(MP_Node, CRUDModel, ResolvableModel, OrderableModel):  # type: ignore[misc]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("spaces.Space", on_delete=models.CASCADE, related_name="discussions")
    label = models.CharField(max_length=255, blank=True, default="")

    node_order_by = ["sequence_index"]
    objects = DiscussionManager()

    class Meta:
        db_table = "discussions"
        ordering = ["path"]
        verbose_name = "discussion"
        verbose_name_plural = "discussions"
        indexes = [
            models.Index(fields=["space", "deleted_at"], name="discussions_space_deleted_idx"),
        ]

    def __str__(self) -> str:
        return self.label or f"Discussion {self.id}"

    @property
    def is_discussion(self) -> bool:
        return True

    @property
    def is_post(self) -> bool:
        return False

    @property
    def is_link(self) -> bool:
        return False


__all__ = ["Discussion"]
