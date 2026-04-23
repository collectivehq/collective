from __future__ import annotations

from typing import Protocol

from apps.spaces.models import Role, Space, SpaceParticipant
from apps.users.models import User


class HasSpace(Protocol):
    @property
    def space(self) -> Space: ...


def get_space_participant(
    user: User,
    space: Space,
    participant: SpaceParticipant | None = None,
) -> SpaceParticipant | None:
    if participant is not None:
        return participant
    return space.participants.select_related("role").filter(user=user).first()


def get_role_for_user(
    user: User,
    space: Space,
    participant: SpaceParticipant | None = None,
) -> Role | None:
    resolved = get_space_participant(user, space, participant)
    return resolved.role if resolved is not None else None


def _check_role_flag(
    user: User,
    space_or_node: Space | HasSpace,
    attr: str,
    *,
    participant: SpaceParticipant | None = None,
    extra_check: bool = True,
) -> bool:
    space = space_or_node.space if hasattr(space_or_node, "space") else space_or_node
    role = get_role_for_user(user, space, participant)
    if role is None:
        return False
    if not extra_check:
        return False
    return bool(getattr(role, attr))


def _role_can_modify_space(*, role: Role, space: Space) -> bool:
    if space.deleted_at is not None or space.lifecycle == Space.Lifecycle.ARCHIVED:
        return False
    if space.lifecycle == Space.Lifecycle.CLOSED:
        return bool(role.can_modify_closed_space)
    return space.is_active


def can_modify_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    role = get_role_for_user(user, space, participant)
    if role is None:
        return False
    return _role_can_modify_space(role=role, space=space)


def can_set_permissions(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_set_permissions",
        participant=participant,
        extra_check=can_modify_space(user, space, participant=participant),
    )


def can_moderate_content(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_moderate_content",
        participant=participant,
        extra_check=can_modify_space(user, space, participant=participant),
    )


def can_manage_participants(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_manage_participants",
        participant=participant,
        extra_check=can_modify_space(user, space, participant=participant),
    )


def can_close_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_close_space", participant=participant)


def can_archive_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_archive_space", participant=participant)


def can_unarchive_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_unarchive_space", participant=participant)


def can_modify_closed_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_modify_closed_space", participant=participant)


def can_view_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    """A user can view a space if they are a participant (any role)."""
    resolved = get_space_participant(user, space, participant)
    return resolved is not None
