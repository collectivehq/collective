from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.nodes.models import Node
from apps.spaces.services import get_active_space, get_participant
from apps.subscriptions import services as sub_services
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
