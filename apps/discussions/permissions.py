from __future__ import annotations

from apps.discussions.models import Discussion
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import _check_role_flag
from apps.users.models import User


def can_shape_tree(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_shape_tree", participant=participant)


def can_reorganise(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_reorganise", participant=participant)


def can_view_drafts(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_view_drafts", participant=participant)


def can_resolve_discussion(user: User, discussion: Discussion, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, discussion, "can_resolve", participant=participant)
