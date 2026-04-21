from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.nodes.models import Node
from apps.opinions import services as opinion_services
from apps.opinions.rate_limits import allow_toggle_request
from apps.spaces.permissions import can_opine, can_react
from apps.spaces.services import get_active_space, get_participant
from apps.users.utils import get_user


@require_POST
@login_required
def toggle_opinion(request: HttpRequest, space_id: str, node_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    node = get_object_or_404(Node, pk=node_id, space=space, deleted_at__isnull=True)
    user = get_user(request)
    participant = get_participant(space=space, user=user)

    if not can_opine(user, node, participant=participant) or participant is None:
        raise PermissionDenied

    if not allow_toggle_request(request=request, action="opinion", space_id=str(space.pk)):
        return HttpResponse("Too many opinion toggles. Please wait a moment.", status=429)

    opinion_type = request.POST.get("type", "")
    if not opinion_type:
        return HttpResponse("Type is required", status=400)

    try:
        result = opinion_services.toggle_opinion(participant=participant, node=node, opinion_type=opinion_type)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    opinions = opinion_services.get_opinion_counts(node)
    user_opinion = result.opinion_type if result else None

    buttons_html = render_to_string(
        "opinions/opinion_buttons.html",
        {"space": space, "node": node, "opinions": opinions, "user_opinion": user_opinion},
        request=request,
    )
    bar_oob_html = render_to_string(
        "opinions/opinion_bar_oob.html",
        {"discussion": node, "opinions": opinions},
        request=request,
    )
    response = HttpResponse(buttons_html + bar_oob_html)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def toggle_reaction(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    post = get_object_or_404(Node, pk=post_id, space=space, node_type=Node.NodeType.POST, deleted_at__isnull=True)
    user = get_user(request)
    participant = get_participant(space=space, user=user)

    if not can_react(user, post, participant=participant) or participant is None:
        raise PermissionDenied

    if not allow_toggle_request(request=request, action="reaction", space_id=str(space.pk)):
        return HttpResponse("Too many reaction toggles. Please wait a moment.", status=429)

    reaction_type = request.POST.get("type", "")
    if not reaction_type:
        return HttpResponse("Type is required", status=400)

    try:
        result = opinion_services.toggle_reaction(participant=participant, post=post, reaction_type=reaction_type)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    user_reaction = result.reaction_type if result else ""
    reaction_counts = opinion_services.get_reaction_counts_batch([post.pk]).get(post.pk, {})

    return render(
        request,
        "opinions/reaction_buttons.html",
        {
            "post": post,
            "space": space,
            "participant": participant,
            "user_reaction": user_reaction,
            "reaction_counts": reaction_counts,
        },
    )
