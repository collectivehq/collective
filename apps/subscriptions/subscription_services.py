from __future__ import annotations

from apps.discussions.models import Discussion
from apps.subscriptions.models import Subscription
from apps.users.models import User


def subscribe(*, user: User, discussion: Discussion) -> Subscription:
    subscription, _ = Subscription.objects.get_or_create(
        created_by=user,
        discussion=discussion,
    )
    return subscription


def unsubscribe(*, user: User, discussion: Discussion) -> None:
    Subscription.objects.filter(created_by=user, discussion=discussion).delete()


def is_subscribed(*, user: User, discussion: Discussion) -> bool:
    return Subscription.objects.filter(created_by=user, discussion=discussion).exists()
