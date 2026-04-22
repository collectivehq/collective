from __future__ import annotations

from django import template

from apps.posts.models import Post

register = template.Library()


@register.filter
def is_edited(post: Post) -> bool:
    prefetched = getattr(post, "_prefetched_objects_cache", {}).get("revisions")
    if prefetched is not None:
        return len(prefetched) > 1
    return post.revisions.count() > 1
