from __future__ import annotations

import uuid

from django.db import models
from django.db.models import UniqueConstraint

from apps.core.models import BaseModel


class Reaction(BaseModel):
    class Type(models.TextChoices):
        LIKE = "like", "Like"
        DISLIKE = "dislike", "Dislike"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="reactions")
    reaction_type = models.CharField(max_length=20, choices=Type.choices)

    class Meta:
        db_table = "reactions"
        verbose_name = "reaction"
        verbose_name_plural = "reactions"
        constraints = [
            UniqueConstraint(
                fields=["created_by", "post"],
                name="reactions_user_post_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.created_by} -> {self.reaction_type} on {self.post}"


__all__ = ["Reaction"]
