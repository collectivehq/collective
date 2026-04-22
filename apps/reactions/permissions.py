from __future__ import annotations

from apps.posts.models import Post
from apps.spaces.models import SpaceParticipant
from apps.spaces.permissions import get_role_for_user
from apps.users.models import User


def can_react(user: User, post: Post, *, participant: SpaceParticipant | None = None) -> bool:
    space = post.space
    if post.is_draft or not space.reaction_types:
        return False
    role = get_role_for_user(user, space, participant)
    return bool(role and role.can_react and space.is_active)
