from __future__ import annotations

from django.utils import timezone

from apps.core.permissions import user_matches
from apps.discussions.models import Discussion
from apps.posts.models import Post
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import _check_role_flag, get_role_for_user, get_space_participant
from apps.users.models import User


def can_post_to_discussion(user: User, discussion: Discussion, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user, discussion, "can_post", participant=participant, extra_check=discussion.space.is_active
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
    is_moderator = participant_record.role.can_moderate
    if post.author is None or (not user_matches(user, candidate=post.author) and not is_moderator):
        return "Permission denied"
    if post.is_draft:
        return None
    if post.author == user and not is_moderator:
        if space.edit_window_minutes == 0:
            return "Editing is disabled"
        if space.edit_window_minutes is not None:
            elapsed = (timezone.now() - post.created_at).total_seconds() / 60
            if elapsed > space.edit_window_minutes:
                return "Edit window has expired"
    return None
