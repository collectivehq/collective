from __future__ import annotations

from apps.nodes.models import Node
from apps.spaces.models import SpaceParticipant
from apps.subscriptions.models import Subscription


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
