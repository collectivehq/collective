from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.rate_limits import allow_toggle_request
from apps.core.utils import get_user
from apps.discussions.models import Discussion
from apps.spaces.request_context import get_active_space_request_context
from apps.subscriptions.models import Notification
from apps.subscriptions.notification_services import (
    get_notifications_for_user,
    mark_all_notifications_read,
    mark_notification_read,
)
from apps.subscriptions.subscription_services import is_subscribed, subscribe, unsubscribe


@require_POST
@login_required
def toggle_subscription(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if participant is None:
        raise PermissionDenied

    if not allow_toggle_request(request=request, action="subscription", space_id=str(space.pk)):
        return HttpResponse("Too many subscription toggles. Please wait a moment.", status=429)

    if is_subscribed(user=user, discussion=discussion):
        unsubscribe(user=user, discussion=discussion)
        subscribed = False
    else:
        subscribe(user=user, discussion=discussion)
        subscribed = True

    return render(
        request,
        "subscriptions/subscription_button.html",
        {
            "space": space,
            "discussion": discussion,
            "subscribed": subscribed,
            "dropdown": bool(request.POST.get("dropdown")),
        },
    )


@login_required
def notification_center(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    notifications = get_notifications_for_user(user=user)
    notification_items = [
        {
            "notification": notification,
            "title": notification.title(),
            "preview": notification.preview(),
        }
        for notification in notifications
    ]
    return render(request, "subscriptions/notifications.html", {"notification_items": notification_items})


@require_POST
@login_required
def notification_mark_all_read(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    mark_all_notifications_read(user=user)
    return redirect("subscriptions:notifications")


@login_required
def notification_open(request: HttpRequest, notification_id: str) -> HttpResponse:
    user = get_user(request)
    notification = get_object_or_404(
        Notification.objects.select_related("discussion__space"),
        pk=notification_id,
        recipient=user,
    )
    mark_notification_read(notification=notification)
    destination = reverse("spaces:detail", kwargs={"space_id": notification.discussion.space_id})
    return redirect(f"{destination}#{notification.discussion.pk}")
