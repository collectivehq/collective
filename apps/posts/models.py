from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.db import models

from apps.core.models import BaseModel, DeletableModel, OrderableModel, UpdateableModel

if TYPE_CHECKING:
    from apps.discussions.models import Discussion
    from apps.spaces.models import Space
    from apps.users.models import User


class DiscussionContent(BaseModel, DeletableModel, OrderableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discussion = models.ForeignKey(
        "discussions.Discussion",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        related_query_name="%(class)s",
    )

    class Meta:
        abstract = True
        ordering = ["sequence_index", "created_at"]

    def get_parent(self) -> Discussion:
        return self.discussion

    @property
    def space(self) -> Space:
        return self.discussion.space

    @property
    def space_id(self) -> uuid.UUID:
        return self.discussion.space_id

    @property
    def is_discussion(self) -> bool:
        return False


class Post(DiscussionContent, UpdateableModel):
    is_draft = models.BooleanField(default=False)

    class Meta:
        db_table = "posts"
        verbose_name = "post"
        verbose_name_plural = "posts"
        indexes = [
            models.Index(fields=["discussion", "sequence_index"], name="posts_discussion_sequence_idx"),
        ]

    def __str__(self) -> str:
        return f"Post #{self.sequence_index}"

    @property
    def author(self) -> User:
        return self.created_by

    @author.setter
    def author(self, value: User) -> None:
        self.created_by = value

    @property
    def author_id(self) -> uuid.UUID:
        return self.created_by_id

    @property
    def latest_revision(self) -> PostRevision | None:
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("revisions")
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return self.revisions.first()

    @property
    def content(self) -> str:
        revision = self.latest_revision
        return revision.content if revision is not None else ""

    @property
    def is_post(self) -> bool:
        return True

    @property
    def is_link(self) -> bool:
        return False


class Link(DiscussionContent):
    target = models.ForeignKey("discussions.Discussion", on_delete=models.CASCADE, related_name="incoming_links")

    class Meta:
        db_table = "links"
        verbose_name = "link"
        verbose_name_plural = "links"
        indexes = [
            models.Index(fields=["discussion", "sequence_index"], name="links_discussion_sequence_idx"),
            models.Index(fields=["target"], name="links_target_idx"),
        ]

    def __str__(self) -> str:
        return f"Link -> {self.target_id}"

    @property
    def is_post(self) -> bool:
        return False

    @property
    def is_link(self) -> bool:
        return True


class PostRevision(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="revisions")
    content = models.TextField()

    class Meta:
        db_table = "post_revisions"
        ordering = ["-created_at"]
        verbose_name = "post revision"
        verbose_name_plural = "post revisions"

    def __str__(self) -> str:
        return f"Revision of {self.post_id} at {self.created_at}"


__all__ = ["DiscussionContent", "Link", "Post", "PostRevision"]
