from __future__ import annotations

import uuid as uuid_mod
from collections.abc import Sequence
from typing import Any

from django.dispatch import receiver

from apps.nodes.models import Node
from apps.nodes.signals import discussion_posted, discussion_status_changed, nodes_soft_deleted
from apps.subscriptions import services as subscription_services
from apps.subscriptions.models import Notification, Subscription
from apps.users.models import User


def _coerce_lookup_id(value: object) -> str | uuid_mod.UUID | None:
    if isinstance(value, (str, uuid_mod.UUID)):
        return value
    return None


@receiver(nodes_soft_deleted)
def delete_subscriptions_for_soft_deleted_nodes(*, node_ids: Sequence[object], **kwargs: Any) -> None:
    Subscription.objects.filter(node_id__in=node_ids).delete()


@receiver(discussion_posted)
def create_notifications_for_discussion_post(
    *, discussion_id: object, post_id: object, actor_id: object, **kwargs: Any
) -> None:
    discussion_lookup = _coerce_lookup_id(discussion_id)
    post_lookup = _coerce_lookup_id(post_id)
    actor_lookup = _coerce_lookup_id(actor_id)
    if discussion_lookup is None or post_lookup is None or actor_lookup is None:
        return
    discussion = Node.objects.filter(pk=discussion_lookup, deleted_at__isnull=True).first()
    post = Node.objects.filter(pk=post_lookup, deleted_at__isnull=True).first()
    actor = User.objects.filter(pk=actor_lookup).first()
    if discussion is None or post is None or actor is None:
        return
    subscription_services.create_post_notifications(discussion=discussion, post=post, actor=actor)


@receiver(discussion_status_changed)
def create_notifications_for_discussion_status(
    *,
    discussion_id: object,
    actor_id: object,
    event_type: str,
    resolution_type: str,
    **kwargs: Any,
) -> None:
    discussion_lookup = _coerce_lookup_id(discussion_id)
    actor_lookup = _coerce_lookup_id(actor_id)
    if discussion_lookup is None or actor_lookup is None:
        return
    discussion = Node.objects.filter(pk=discussion_lookup, deleted_at__isnull=True).first()
    actor = User.objects.filter(pk=actor_lookup).first()
    if discussion is None or actor is None:
        return

    if event_type == "reopened":
        subscription_services.create_discussion_status_notifications(
            discussion=discussion,
            actor=actor,
            event_type=Notification.EventType.DISCUSSION_REOPENED,
        )
        return

    subscription_services.create_discussion_status_notifications(
        discussion=discussion,
        actor=actor,
        event_type=Notification.EventType.DISCUSSION_RESOLVED,
        resolution_type=resolution_type,
    )
