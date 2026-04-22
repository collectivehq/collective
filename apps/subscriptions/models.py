from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Index, UniqueConstraint
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.core.models import BaseModel


class Subscription(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discussion = models.ForeignKey("discussions.Discussion", on_delete=models.CASCADE, related_name="subscriptions")

    class Meta:
        db_table = "subscriptions"
        verbose_name = "subscription"
        verbose_name_plural = "subscriptions"
        constraints = [
            UniqueConstraint(fields=["created_by", "discussion"], name="subscriptions_user_discussion_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.created_by} subscribed to {self.discussion}"


class Notification(BaseModel):
    class EventType(models.TextChoices):
        POST_CREATED = "post_created", "Post created"
        DISCUSSION_RESOLVED = "discussion_resolved", "Discussion resolved"
        DISCUSSION_REOPENED = "discussion_reopened", "Discussion reopened"

    RESOLUTION_VERB_LABELS = {
        "accept": "accepted",
        "reject": "rejected",
        "close": "closed",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="notifications")
    discussion = models.ForeignKey("discussions.Discussion", on_delete=models.CASCADE, related_name="notifications")
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="post_notifications",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    resolution_type = models.CharField(max_length=20, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at"]
        indexes = [
            Index(fields=["recipient", "read_at", "created_at"], name="notif_rcpt_read_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.recipient} {self.event_type} {self.discussion}"

    def title(self) -> str:
        actor_name = self.actor_name
        discussion_label = self.discussion.label or "Untitled"
        if self.event_type == self.EventType.POST_CREATED:
            return f"{actor_name} posted in {discussion_label}"
        if self.event_type == self.EventType.DISCUSSION_REOPENED:
            return f"{actor_name} reopened {discussion_label}"
        resolution_label = self.RESOLUTION_VERB_LABELS.get(self.resolution_type, "resolved")
        return f"{actor_name} {resolution_label} {discussion_label}"

    def preview(self) -> str:
        if self.post is None:
            return ""
        return Truncator(strip_tags(self.preview_source_content())).chars(140)

    @property
    def actor_name(self) -> str:
        if self.created_by.name:
            return self.created_by.name
        if self.created_by.email:
            return self.created_by.email
        return "Someone"

    def preview_source_content(self) -> str:
        if self.post is None:
            return ""
        if self.event_type != self.EventType.POST_CREATED:
            return str(self.post.content)

        revisions = list(self.post.revisions.all())
        if revisions:
            return str(revisions[-1].content)
        return str(self.post.content)
