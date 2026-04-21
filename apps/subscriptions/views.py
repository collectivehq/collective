from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.nodes.models import Node
from apps.spaces.services import get_active_space, get_participant
from apps.subscriptions import services as sub_services
from apps.subscriptions.models import Notification
from apps.users.utils import get_user


@require_POST
@login_required
def toggle_subscription(request: HttpRequest, space_id: str, node_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    node = get_object_or_404(Node, pk=node_id, space=space, deleted_at__isnull=True)
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if participant is None:
        raise PermissionDenied

    if sub_services.is_subscribed(participant=participant, node=node):
        sub_services.unsubscribe(participant=participant, node=node)
        subscribed = False
    else:
        sub_services.subscribe(participant=participant, node=node)
        subscribed = True

    return render(
        request,
        "subscriptions/subscription_button.html",
        {"space": space, "node": node, "subscribed": subscribed, "dropdown": bool(request.POST.get("dropdown"))},
    )


@login_required
def notification_center(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    notifications = sub_services.get_notifications_for_user(user=user)
    notification_items = [
        {
            "notification": notification,
            "title": sub_services.notification_title(notification),
            "preview": sub_services.notification_preview(notification),
        }
        for notification in notifications
    ]
    return render(request, "subscriptions/notifications.html", {"notification_items": notification_items})


@require_POST
@login_required
def notification_mark_all_read(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    sub_services.mark_all_notifications_read(user=user)
    return redirect("subscriptions:notifications")


@login_required
def notification_open(request: HttpRequest, notification_id: str) -> HttpResponse:
    user = get_user(request)
    notification = get_object_or_404(
        Notification.objects.select_related("participant__space", "node"),
        pk=notification_id,
        participant__user=user,
    )
    sub_services.mark_notification_read(notification=notification)
    return redirect(
        f"{reverse('spaces:detail', kwargs={'space_id': notification.node.space_id})}#{notification.node.pk}"
    )
