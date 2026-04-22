from __future__ import annotations

from apps.discussions.models import Discussion
from apps.spaces.models import SpaceParticipant
from apps.spaces.permissions import get_role_for_user
from apps.users.models import User


def can_opine(user: User, discussion: Discussion, *, participant: SpaceParticipant | None = None) -> bool:
    space = discussion.space
    if not space.opinion_types or not space.is_active:
        return False
    role = get_role_for_user(user, space, participant)
    return bool(role and role.can_opine)
