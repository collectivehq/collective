from __future__ import annotations

import datetime
from typing import TypedDict

from django.db.models import Prefetch
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.discussions.models import Discussion
from apps.posts.models import Post, PostRevision
from apps.spaces.models import Space


class RecentActivityItem(TypedDict):
    kind: str
    title: str
    detail: str
    actor: str
    created_at: datetime.datetime
    discussion_id: str
    url: str


def build_space_recent_activity(space: Space, *, limit: int = 8) -> list[RecentActivityItem]:
    discussions_qs = Discussion.objects.filter(space=space, deleted_at__isnull=True)
    if space.root_discussion_id is not None:
        discussions_qs = discussions_qs.exclude(pk=space.root_discussion_id)
    discussions = list(discussions_qs.select_related("created_by").order_by("-created_at")[:limit])
    posts = list(
        Post.objects.filter(discussion__space=space, deleted_at__isnull=True, is_draft=False)
        .select_related("created_by", "discussion")
        .prefetch_related(Prefetch("revisions", queryset=PostRevision.objects.order_by("-created_at")))
        .order_by("-created_at")[:limit]
    )

    items: list[RecentActivityItem] = []
    for discussion in discussions:
        items.append(
            {
                "kind": "discussion",
                "title": discussion.label or "Untitled discussion",
                "detail": "Discussion created",
                "actor": discussion.created_by.name or discussion.created_by.email,
                "created_at": discussion.created_at,
                "discussion_id": str(discussion.pk),
                "url": reverse(
                    "discussions:discussion_detail",
                    kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
                ),
            }
        )
    for post in posts:
        items.append(
            {
                "kind": "post",
                "title": Truncator(strip_tags(post.content).strip() or "Post").chars(90),
                "detail": post.discussion.label or "In the main discussion",
                "actor": post.created_by.name or post.created_by.email,
                "created_at": post.created_at,
                "discussion_id": str(post.discussion_id),
                "url": reverse(
                    "discussions:discussion_detail",
                    kwargs={"space_id": space.pk, "discussion_id": post.discussion_id},
                ),
            }
        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:limit]


__all__ = [
    "RecentActivityItem",
    "build_space_recent_activity",
]
