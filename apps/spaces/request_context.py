from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from apps.core.utils import get_user
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import get_space_participant
from apps.users.models import User


@dataclass(frozen=True, slots=True)
class SpaceRequestContext:
    space: Space
    user: User
    participant: SpaceParticipant | None


def get_space_request_context(
    request: HttpRequest,
    space_id: str,
    *,
    active: bool = False,
    select_related: tuple[str, ...] = (),
) -> SpaceRequestContext:
    queryset = Space.objects.active() if active else Space.objects.all()
    if select_related:
        queryset = queryset.select_related(*select_related)

    lookup_kwargs: dict[str, object] = {"pk": space_id}
    if not active:
        lookup_kwargs["deleted_at__isnull"] = True

    space = get_object_or_404(queryset, **lookup_kwargs)
    user = get_user(request)
    participant = get_space_participant(user, space)
    return SpaceRequestContext(space=space, user=user, participant=participant)


def get_active_space_request_context(
    request: HttpRequest,
    space_id: str,
    *,
    select_related: tuple[str, ...] = (),
) -> SpaceRequestContext:
    return get_space_request_context(request, space_id, active=True, select_related=select_related)
