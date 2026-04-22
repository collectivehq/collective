from __future__ import annotations

import uuid

from django.db import models
from django.db.models import UniqueConstraint

from apps.core.models import BaseModel


class Opinion(BaseModel):
    class Type(models.TextChoices):
        AGREE = "agree", "Agree"
        ABSTAIN = "abstain", "Abstain"
        DISAGREE = "disagree", "Disagree"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discussion = models.ForeignKey("discussions.Discussion", on_delete=models.CASCADE, related_name="opinions")
    opinion_type = models.CharField(max_length=20, choices=Type.choices)

    class Meta:
        db_table = "opinions"
        verbose_name = "opinion"
        verbose_name_plural = "opinions"
        constraints = [
            UniqueConstraint(fields=["created_by", "discussion"], name="opinions_user_discussion_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.created_by} -> {self.opinion_type} on {self.discussion}"
