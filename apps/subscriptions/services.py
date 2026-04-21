from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.nodes.models import Node
from apps.spaces.models import SpaceParticipant
from apps.subscriptions.models import Notification, Subscription
from apps.users.models import User


def subscribe(*, participant: SpaceParticipant, node: Node) -> Subscription:
    subscription, _ = Subscription.objects.get_or_create(
        participant=participant,
        node=node,
    )
    return subscription


def unsubscribe(*, participant: SpaceParticipant, node: Node) -> None:
    Subscription.objects.filter(participant=participant, node=node).delete()


def is_subscribed(*, participant: SpaceParticipant, node: Node) -> bool:
    return Subscription.objects.filter(participant=participant, node=node).exists()


def create_post_notifications(*, discussion: Node, post: Node, actor: User) -> None:
    subscriptions = (
        Subscription.objects.select_related("participant__user")
        .filter(node=discussion)
        .exclude(participant__user=actor)
    )
    Notification.objects.bulk_create(
        [
            Notification(
                participant=subscription.participant,
                node=discussion,
                post=post,
                actor=actor,
                event_type=Notification.EventType.POST_CREATED,
            )
            for subscription in subscriptions
        ]
    )


def create_discussion_status_notifications(
    *,
    discussion: Node,
    actor: User,
    event_type: Notification.EventType,
    resolution_type: str = "",
) -> None:
    subscriptions = (
        Subscription.objects.select_related("participant__user")
        .filter(node=discussion)
        .exclude(participant__user=actor)
    )
    Notification.objects.bulk_create(
        [
            Notification(
                participant=subscription.participant,
                node=discussion,
                actor=actor,
                event_type=event_type,
                resolution_type=resolution_type,
            )
            for subscription in subscriptions
        ]
    )


def get_notifications_for_user(*, user: User) -> QuerySet[Notification]:
    return Notification.objects.filter(participant__user=user).select_related(
        "participant__space", "node", "post", "actor"
    )


def get_unread_notification_count(*, user: User) -> int:
    return Notification.objects.filter(participant__user=user, read_at__isnull=True).count()


def mark_notification_read(*, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_notifications_read(*, user: User) -> int:
    return Notification.objects.filter(participant__user=user, read_at__isnull=True).update(read_at=timezone.now())


def notification_title(notification: Notification) -> str:
    actor_name = (
        notification.actor.name
        if notification.actor and notification.actor.name
        else notification.actor.email
        if notification.actor
        else "Someone"
    )
    discussion_label = notification.node.label or "Untitled"
    if notification.event_type == Notification.EventType.POST_CREATED:
        return f"{actor_name} posted in {discussion_label}"
    if notification.event_type == Notification.EventType.DISCUSSION_REOPENED:
        return f"{actor_name} reopened {discussion_label}"
    resolution_label = notification.resolution_type or "resolved"
    return f"{actor_name} {resolution_label} {discussion_label}"


def notification_preview(notification: Notification) -> str:
    if notification.post is None:
        return ""
    return Truncator(strip_tags(notification.post.content)).chars(140)
