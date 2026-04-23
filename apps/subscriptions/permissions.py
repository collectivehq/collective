from __future__ import annotations

from apps.discussions.models import Discussion
from apps.spaces.models import SpaceParticipant
from apps.spaces.permissions import get_space_participant
from apps.users.models import User


def can_toggle_subscription(
    user: User,
    discussion: Discussion,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    return get_space_participant(user, discussion.space, participant) is not None and discussion.space.is_active
