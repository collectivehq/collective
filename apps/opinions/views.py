from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.core.rate_limits import allow_toggle_request
from apps.discussions.models import Discussion
from apps.opinions import services as opinion_services
from apps.opinions.permissions import can_opine
from apps.spaces.request_context import get_active_space_request_context


@require_POST
@login_required
def toggle_opinion(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(Discussion, pk=discussion_id, space=space, deleted_at__isnull=True)

    if not can_opine(user, discussion, participant=participant) or participant is None:
        raise PermissionDenied

    if not allow_toggle_request(request=request, action="opinion", space_id=str(space.pk)):
        return HttpResponse("Too many opinion toggles. Please wait a moment.", status=429)

    opinion_type = request.POST.get("type", "")
    if not opinion_type:
        return HttpResponse("Type is required", status=400)

    try:
        result = opinion_services.toggle_opinion(user=user, discussion=discussion, opinion_type=opinion_type)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    opinions = opinion_services.get_opinion_counts(discussion)
    user_opinion = result.opinion_type if result else None

    buttons_html = render_to_string(
        "opinions/opinion_buttons.html",
        {"space": space, "discussion": discussion, "opinions": opinions, "user_opinion": user_opinion},
        request=request,
    )
    bar_oob_html = render_to_string(
        "opinions/opinion_bar_oob.html",
        {"discussion": discussion, "opinions": opinions},
        request=request,
    )
    response = HttpResponse(buttons_html + bar_oob_html)
    response["HX-Trigger"] = "refreshTree"
    return response
