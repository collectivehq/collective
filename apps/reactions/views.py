from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.core.rate_limits import allow_toggle_request
from apps.posts.models import Post
from apps.reactions import services as reaction_services
from apps.reactions.permissions import can_react
from apps.spaces.request_context import get_space_request_context


@require_POST
@login_required
def toggle_reaction(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)

    if not can_react(user, post, participant=participant) or participant is None:
        raise PermissionDenied

    if not allow_toggle_request(request=request, action="reaction", space_id=str(space.pk)):
        return HttpResponse("Too many reaction toggles. Please wait a moment.", status=429)

    reaction_type = request.POST.get("type", "")
    if not reaction_type:
        return HttpResponse("Type is required", status=400)

    try:
        result = reaction_services.toggle_reaction(user=user, post=post, reaction_type=reaction_type)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    user_reaction = result.reaction_type if result else ""
    reaction_counts = reaction_services.get_reaction_counts_batch([post.pk]).get(post.pk, {})

    return render(
        request,
        "reactions/reaction_buttons.html",
        {
            "post": post,
            "space": space,
            "participant": participant,
            "user_reaction": user_reaction,
            "reaction_counts": reaction_counts,
        },
    )
