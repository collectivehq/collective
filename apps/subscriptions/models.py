import uuid

from django.conf import settings
from django.db import models
from django.db.models import Index, UniqueConstraint


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


class Notification(models.Model):
    class EventType(models.TextChoices):
        POST_CREATED = "post_created", "Post created"
        DISCUSSION_RESOLVED = "discussion_resolved", "Discussion resolved"
        DISCUSSION_REOPENED = "discussion_reopened", "Discussion reopened"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey("spaces.SpaceParticipant", on_delete=models.CASCADE, related_name="notifications")
    node = models.ForeignKey("nodes.Node", on_delete=models.CASCADE, related_name="notifications")
    post = models.ForeignKey(
        "nodes.Node",
        on_delete=models.CASCADE,
        related_name="post_notifications",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_notifications",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    resolution_type = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            Index(fields=["participant", "read_at", "created_at"], name="notif_part_read_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.participant} {self.event_type} {self.node}"
