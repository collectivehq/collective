from __future__ import annotations

from django.db.models import Max
from django.db.models.functions import Coalesce

from apps.discussions.models import Discussion
from apps.posts.models import Link, Post


def next_sequence_index(parent: Discussion) -> int:
    Discussion.objects.select_for_update().filter(pk=parent.pk).first()
    discussion_max = (
        parent.get_children()
        .filter(deleted_at__isnull=True)
        .aggregate(max_idx=Coalesce(Max("sequence_index"), -1))["max_idx"]
    )
    post_max = Post.objects.filter(discussion=parent, deleted_at__isnull=True).aggregate(
        max_idx=Coalesce(Max("sequence_index"), -1)
    )["max_idx"]
    link_max = Link.objects.filter(discussion=parent, deleted_at__isnull=True).aggregate(
        max_idx=Coalesce(Max("sequence_index"), -1)
    )["max_idx"]
    return int(max(discussion_max, post_max, link_max)) + 1
