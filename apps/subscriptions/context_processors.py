from __future__ import annotations

from django.http import HttpRequest

from apps.subscriptions.notification_services import get_unread_notification_count


def notifications(request: HttpRequest) -> dict[str, int]:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_notifications_count": 0}
    return {"unread_notifications_count": get_unread_notification_count(user=user)}
