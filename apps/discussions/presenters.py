from __future__ import annotations

import uuid
from dataclasses import dataclass

from apps.discussions.models import Discussion
from apps.posts.models import Link, Post


@dataclass(slots=True)
class DiscussionDetailPost:
    post: Post
    user_can_edit: bool
    user_can_react: bool
    user_reaction_type: str
    reaction_counts: dict[str, int]

    @property
    def is_post(self) -> bool:
        return True

    @property
    def is_link(self) -> bool:
        return False

    @property
    def pk(self) -> uuid.UUID:
        return self.post.pk


@dataclass(slots=True)
class DiscussionDetailLink:
    link: Link
    link_preview_post: Post | None

    @property
    def is_post(self) -> bool:
        return False

    @property
    def is_link(self) -> bool:
        return True

    @property
    def pk(self) -> uuid.UUID:
        return self.link.pk


@dataclass(slots=True)
class DiscussionDetailSubDiscussion:
    discussion: Discussion
    active_child_count: int

    @property
    def pk(self) -> uuid.UUID:
        return self.discussion.pk

    @property
    def label(self) -> str:
        return self.discussion.label

    @property
    def resolution_type(self) -> str:
        return self.discussion.resolution_type


type DiscussionDetailInlineChild = DiscussionDetailPost | DiscussionDetailLink
