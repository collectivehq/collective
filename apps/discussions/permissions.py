from __future__ import annotations

from apps.discussions.models import Discussion
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import _check_role_flag, can_modify_space
from apps.users.models import User


def _is_modifiable_space(
    user: User,
    space_or_discussion: Space | Discussion,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    if isinstance(space_or_discussion, Discussion):
        return can_modify_space(user, space_or_discussion.space, participant=participant)
    return can_modify_space(user, space_or_discussion, participant=participant)


def can_create_discussion(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_create_discussion",
        participant=participant,
        extra_check=_is_modifiable_space(user, space, participant=participant),
    )


def can_rename_discussion(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_rename_discussion",
        participant=participant,
        extra_check=_is_modifiable_space(user, space, participant=participant),
    )


def can_delete_discussion(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_delete_discussion",
        participant=participant,
        extra_check=_is_modifiable_space(user, space, participant=participant),
    )


def can_reorganise(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_reorganise",
        participant=participant,
        extra_check=_is_modifiable_space(user, space, participant=participant),
    )


def can_restructure(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_restructure",
        participant=participant,
        extra_check=_is_modifiable_space(user, space, participant=participant),
    )


def can_view_drafts(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_view_drafts", participant=participant)


def can_resolve_discussion(user: User, discussion: Discussion, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        discussion,
        "can_resolve",
        participant=participant,
        extra_check=_is_modifiable_space(user, discussion, participant=participant),
    )


def can_reopen_discussion(
    user: User,
    space_or_discussion: Space | Discussion,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    return _check_role_flag(
        user,
        space_or_discussion,
        "can_reopen_discussion",
        participant=participant,
        extra_check=_is_modifiable_space(user, space_or_discussion, participant=participant),
    )
