from __future__ import annotations

from django.utils import timezone

from apps.core.permissions import user_matches
from apps.discussions.models import Discussion
from apps.posts.models import Post
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import _check_role_flag, can_modify_space, get_role_for_user, get_space_participant
from apps.users.models import User


def can_post_to_discussion(user: User, discussion: Discussion, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        discussion,
        "can_post",
        participant=participant,
        extra_check=can_modify_space(user, discussion.space, participant=participant),
    )


def can_view_post(user: User, post: Post, *, participant: SpaceParticipant | None = None) -> bool:
    role = get_role_for_user(user, post.space, participant)
    if role is None:
        return False
    if not post.is_draft:
        return True
    return user_matches(user, user_id=post.author_id) or bool(role.can_view_drafts)


def can_edit_post(
    user: User,
    post: Post,
    space: Space,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    return get_post_edit_denial_reason(user, post, space, participant=participant) is None


def can_create_draft(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_create_draft",
        participant=participant,
        extra_check=can_modify_space(user, space, participant=participant),
    )


def can_upload_images(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    participant_record = get_space_participant(user, space, participant)
    if participant_record is None:
        return False
    if not can_modify_space(user, space, participant=participant_record):
        return False
    role = participant_record.role
    return bool(role.can_post or role.can_create_draft or role.can_edit_others_post or role.can_set_permissions)


def can_view_history(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_view_history", participant=participant)


def can_promote_post(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user,
        space,
        "can_promote_post",
        participant=participant,
        extra_check=can_modify_space(user, space, participant=participant),
    )


def can_delete_post(
    user: User,
    post: Post,
    space: Space,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    participant_record = get_space_participant(user, space, participant)
    if participant_record is None:
        return False
    if not can_modify_space(user, space, participant=participant_record):
        return False
    if user_matches(user, candidate=post.author):
        return bool(participant_record.role.can_delete_own_post)
    return bool(participant_record.role.can_moderate_content)


def get_post_edit_denial_reason(
    user: User,
    post: Post,
    space: Space,
    *,
    participant: SpaceParticipant | None = None,
) -> str | None:
    participant_record = get_space_participant(user, space, participant)
    if participant_record is None:
        return "Permission denied"
    if not can_modify_space(user, space, participant=participant_record):
        if space.lifecycle == Space.Lifecycle.ARCHIVED:
            return "This space is archived"
        if space.lifecycle == Space.Lifecycle.CLOSED:
            return "This space is closed"
        return "This space cannot be modified right now"
    can_edit_others = bool(participant_record.role.can_edit_others_post)
    is_author = user_matches(user, candidate=post.author)
    if not is_author and not can_edit_others:
        return "Permission denied"
    if post.is_draft:
        if is_author and not participant_record.role.can_create_draft:
            return "Permission denied"
        return None
    if can_edit_others:
        return None
    if space.edit_window_minutes == 0:
        return "Editing is disabled"
    if space.edit_window_minutes is not None:
        elapsed = (timezone.now() - post.created_at).total_seconds() / 60
        if elapsed > space.edit_window_minutes:
            return "Edit window has expired"
    return None
