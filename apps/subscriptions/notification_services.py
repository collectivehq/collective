from __future__ import annotations

import uuid

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.discussions.models import Discussion
from apps.posts.models import Post, PostRevision
from apps.subscriptions.models import Notification, Subscription
from apps.users.models import User


def _subscriber_ids(*, discussion: Discussion, actor: User) -> list[uuid.UUID]:
    return list(
        Subscription.objects.filter(discussion=discussion)
        .exclude(created_by=actor)
        .values_list("created_by_id", flat=True)
    )


def _create_notifications(
    *,
    discussion: Discussion,
    actor: User,
    recipient_ids: list[uuid.UUID],
    event_type: Notification.EventType,
    post: Post | None = None,
    resolution_type: str = "",
) -> None:
    Notification.objects.bulk_create(
        [
            Notification(
                created_by=actor,
                recipient_id=recipient_id,
                discussion=discussion,
                post=post,
                event_type=event_type,
                resolution_type=resolution_type,
            )
            for recipient_id in recipient_ids
        ]
    )


def create_post_notifications(*, discussion: Discussion, post: Post, actor: User) -> None:
    _create_notifications(
        discussion=discussion,
        actor=actor,
        recipient_ids=_subscriber_ids(discussion=discussion, actor=actor),
        event_type=Notification.EventType.POST_CREATED,
        post=post,
    )


def create_discussion_status_notifications(
    *,
    discussion: Discussion,
    actor: User,
    event_type: Notification.EventType,
    resolution_type: str = "",
) -> None:
    _create_notifications(
        discussion=discussion,
        actor=actor,
        recipient_ids=_subscriber_ids(discussion=discussion, actor=actor),
        event_type=event_type,
        resolution_type=resolution_type,
    )


def get_notifications_for_user(*, user: User) -> QuerySet[Notification]:
    return (
        Notification.objects.filter(recipient=user)
        .select_related("created_by", "recipient", "discussion__space", "post")
        .prefetch_related(Prefetch("post__revisions", queryset=PostRevision.objects.order_by("-created_at")))
    )


def get_unread_notification_count(*, user: User) -> int:
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_notification_read(*, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_notifications_read(*, user: User) -> int:
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(read_at=timezone.now())
