import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint
from treebeard.mp_tree import MP_Node


class Node(MP_Node):  # type: ignore[misc]
    class NodeType(models.TextChoices):
        DISCUSSION = "discussion", "Discussion"
        POST = "post", "Post"
        LINK = "link", "Link"

    class ResolutionType(models.TextChoices):
        ACCEPT = "accept", "Accept"
        REJECT = "reject", "Reject"
        CLOSE = "close", "Close"

    class PermissionMode(models.TextChoices):
        INHERITED = "inherited", "Inherited"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("spaces.Space", on_delete=models.CASCADE, related_name="nodes")
    node_type = models.CharField(max_length=20, choices=NodeType.choices, default=NodeType.DISCUSSION)
    sequence_index = models.IntegerField(default=0)
    permission_mode = models.CharField(
        max_length=20,
        choices=PermissionMode.choices,
        default=PermissionMode.INHERITED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Discussion fields
    label = models.CharField(max_length=255, blank=True)
    resolution_type = models.CharField(max_length=20, choices=ResolutionType.choices, default="", blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_discussions",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    child_count = models.PositiveIntegerField(default=0)

    # Post fields
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posts",
    )
    content = models.TextField(blank=True)
    reopens_discussion = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)

    # Link fields
    target = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="links",
    )

    node_order_by: list[str] = []

    class Meta:
        db_table = "nodes"
        indexes = [
            models.Index(
                fields=["deleted_at"],
                name="nodes_deleted_at_partial",
                condition=Q(deleted_at__isnull=True),
            ),
        ]
        constraints = [
            UniqueConstraint(
                fields=["path", "sequence_index"],
                name="nodes_parent_sequence_index_unique",
                condition=Q(deleted_at__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        if self.node_type == self.NodeType.POST:
            return f"Post #{self.sequence_index}"
        if self.node_type == self.NodeType.LINK:
            return f"Link → {self.target_id}"
        return self.label or f"Discussion {self.id}"

    @property
    def is_discussion(self) -> bool:
        return self.node_type == self.NodeType.DISCUSSION

    @property
    def is_post(self) -> bool:
        return self.node_type == self.NodeType.POST

    @property
    def is_link(self) -> bool:
        return self.node_type == self.NodeType.LINK


class PostRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="revisions")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post_revisions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Revision of {self.post} at {self.created_at}"
