import uuid

from django.db import models
from django.db.models import UniqueConstraint


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey("spaces.SpaceParticipant", on_delete=models.CASCADE, related_name="subscriptions")
    node = models.ForeignKey("nodes.Node", on_delete=models.CASCADE, related_name="subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions"
        constraints = [
            UniqueConstraint(fields=["participant", "node"], name="subscriptions_participant_node_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.participant} subscribed to {self.node}"
