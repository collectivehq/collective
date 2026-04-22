from __future__ import annotations

import uuid as uuid_mod
from collections.abc import Sequence

from django.dispatch import receiver

from apps.discussions.models import Discussion
from apps.discussions.signals import discussion_items_soft_deleted, discussion_posted, discussion_status_changed
from apps.posts.models import Post
from apps.subscriptions.models import Notification, Subscription
from apps.subscriptions.notification_services import (
    create_discussion_status_notifications,
    create_post_notifications,
)
from apps.users.models import User


def _coerce_lookup_id(value: object) -> str | uuid_mod.UUID | None:
    if isinstance(value, (str, uuid_mod.UUID)):
        return value
    return None


@receiver(discussion_items_soft_deleted)
def delete_subscriptions_for_soft_deleted_discussion_items(
    *, item_ids: Sequence[object], **kwargs: object
) -> None:
    Subscription.objects.filter(discussion_id__in=item_ids).delete()


@receiver(discussion_posted)
def create_notifications_for_discussion_post(
    *, discussion_id: object, post_id: object, actor_id: object, **kwargs: object
) -> None:
    discussion_lookup = _coerce_lookup_id(discussion_id)
    post_lookup = _coerce_lookup_id(post_id)
    actor_lookup = _coerce_lookup_id(actor_id)
    if discussion_lookup is None or post_lookup is None or actor_lookup is None:
        return
    discussion = Discussion.objects.filter(pk=discussion_lookup, deleted_at__isnull=True).first()
    post = Post.objects.filter(pk=post_lookup, deleted_at__isnull=True).first()
    actor = User.objects.filter(pk=actor_lookup).first()
    if discussion is None or post is None or actor is None:
        return
    create_post_notifications(discussion=discussion, post=post, actor=actor)


@receiver(discussion_status_changed)
def create_notifications_for_discussion_status(
    *,
    discussion_id: object,
    actor_id: object,
    event_type: str,
    resolution_type: str,
    **kwargs: object,
) -> None:
    discussion_lookup = _coerce_lookup_id(discussion_id)
    actor_lookup = _coerce_lookup_id(actor_id)
    if discussion_lookup is None or actor_lookup is None:
        return
    discussion = Discussion.objects.filter(pk=discussion_lookup, deleted_at__isnull=True).first()
    actor = User.objects.filter(pk=actor_lookup).first()
    if discussion is None or actor is None:
        return

    if event_type == "reopened":
        create_discussion_status_notifications(
            discussion=discussion,
            actor=actor,
            event_type=Notification.EventType.DISCUSSION_REOPENED,
        )
        return

    create_discussion_status_notifications(
        discussion=discussion,
        actor=actor,
        event_type=Notification.EventType.DISCUSSION_RESOLVED,
        resolution_type=resolution_type,
    )
