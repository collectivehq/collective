from __future__ import annotations

from django.utils import timezone

from apps.nodes.models import Node
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.services import get_participant
from apps.users.models import User


def _resolve_participant(
    user: User,
    space: Space,
    participant: SpaceParticipant | None = None,
) -> SpaceParticipant | None:
    if participant is not None:
        return participant
    return get_participant(space=space, user=user)


def _check_role_flag(
    user: User,
    space_or_node: Space | Node,
    attr: str,
    *,
    participant: SpaceParticipant | None = None,
    extra_check: bool = True,
) -> bool:
    space = space_or_node.space if isinstance(space_or_node, Node) else space_or_node
    resolved = _resolve_participant(user, space, participant)
    if resolved is None:
        return False
    if not extra_check:
        return False
    return bool(getattr(resolved.role, attr))


def can_post_to_discussion(user: User, discussion: Node, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(
        user, discussion, "can_post", participant=participant, extra_check=discussion.space.is_active
    )


def can_resolve_discussion(user: User, discussion: Node, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, discussion, "can_resolve", participant=participant)


def can_shape_tree(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_shape_tree", participant=participant)


def can_set_permissions(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_set_permissions", participant=participant)


def can_reorganise(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_reorganise", participant=participant)


def can_moderate(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_moderate", participant=participant)


def can_close_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_close_space", participant=participant)


def can_view_drafts(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    return _check_role_flag(user, space, "can_view_drafts", participant=participant)


def can_view_post(user: User, post: Node, *, participant: SpaceParticipant | None = None) -> bool:
    resolved = _resolve_participant(user, post.space, participant)
    if resolved is None:
        return False
    if not post.is_draft:
        return True
    return post.author_id == user.pk or bool(resolved.role.can_view_drafts)


def can_opine(user: User, node: Node, *, participant: SpaceParticipant | None = None) -> bool:
    space = node.space
    if not space.opinion_types:
        return False
    return _check_role_flag(user, node, "can_opine", participant=participant, extra_check=space.is_active)


def can_react(user: User, node: Node, *, participant: SpaceParticipant | None = None) -> bool:
    space = node.space
    if node.is_draft or not space.reaction_types:
        return False
    return _check_role_flag(user, node, "can_react", participant=participant, extra_check=space.is_active)


def can_view_space(user: User, space: Space, *, participant: SpaceParticipant | None = None) -> bool:
    """A user can view a space if they are a participant (any role)."""
    resolved = _resolve_participant(user, space, participant)
    return resolved is not None


def can_edit_post(
    user: User,
    post: Node,
    space: Space,
    *,
    participant: SpaceParticipant | None = None,
) -> bool:
    return get_post_edit_denial_reason(user, post, space, participant=participant) is None


def get_post_edit_denial_reason(
    user: User,
    post: Node,
    space: Space,
    *,
    participant: SpaceParticipant | None = None,
) -> str | None:
    """Return the reason a post cannot be edited, or None when editing is allowed."""
    p = _resolve_participant(user, space, participant)
    if p is None:
        return "Permission denied"
    is_mod = p is not None and p.role.can_moderate
    if post.author is None or (post.author != user and not is_mod):
        return "Permission denied"
    if post.is_draft:
        return None
    if post.author == user and not is_mod:
        if space.edit_window_minutes == 0:
            return "Editing is disabled"
        if space.edit_window_minutes is not None:
            elapsed = (timezone.now() - post.created_at).total_seconds() / 60
            if elapsed > space.edit_window_minutes:
                return "Edit window has expired"
    return None
