import uuid

from django.db import models
from django.db.models import UniqueConstraint


class Opinion(models.Model):
    class Type(models.TextChoices):
        AGREE = "agree", "Agree"
        ABSTAIN = "abstain", "Abstain"
        DISAGREE = "disagree", "Disagree"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey("spaces.SpaceParticipant", on_delete=models.CASCADE, related_name="opinions")
    node = models.ForeignKey("nodes.Node", on_delete=models.CASCADE, related_name="opinions")
    opinion_type = models.CharField(max_length=20, choices=Type.choices, db_column="type")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "opinions"
        verbose_name = "opinion"
        verbose_name_plural = "opinions"
        constraints = [
            UniqueConstraint(fields=["participant", "node"], name="opinions_participant_node_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.participant} -> {self.opinion_type} on {self.node}"


class Reaction(models.Model):
    class Type(models.TextChoices):
        LIKE = "like", "Like"
        DISLIKE = "dislike", "Dislike"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey("spaces.SpaceParticipant", on_delete=models.CASCADE, related_name="reactions")
    post = models.ForeignKey("nodes.Node", on_delete=models.CASCADE, related_name="reactions")
    reaction_type = models.CharField(max_length=20, choices=Type.choices, db_column="type")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reactions"
        verbose_name = "reaction"
        verbose_name_plural = "reactions"
        constraints = [
            UniqueConstraint(fields=["participant", "post"], name="reactions_participant_post_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.participant} -> {self.reaction_type} on {self.post}"
