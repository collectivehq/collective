from __future__ import annotations

import datetime
import re
import uuid as uuid_mod

from django.db import transaction
from django.utils import timezone

from apps.discussions.models import Discussion
from apps.invitations.models import SpaceInvite
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.users.models import User

VALID_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    Space.Lifecycle.DRAFT: {Space.Lifecycle.OPEN},
    Space.Lifecycle.OPEN: {Space.Lifecycle.CLOSED},
    Space.Lifecycle.CLOSED: {Space.Lifecycle.OPEN, Space.Lifecycle.ARCHIVED},
    Space.Lifecycle.ARCHIVED: {Space.Lifecycle.CLOSED},
}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _ensure_role_belongs_to_space(*, role: Role, space: Space) -> None:
    if role.space_id != space.pk:
        raise ValueError("Role does not belong to this space")


def _normalize_post_highlight_color(value: str | None) -> str:
    color = (value or "").strip()
    if not color:
        return ""
    if not HEX_COLOR_RE.fullmatch(color):
        raise ValueError("Post highlight color must be a hex color like #A1B2C3.")
    return color.upper()


def touch_space(*, space: Space | None = None, space_id: uuid_mod.UUID | str | None = None) -> None:
    target_space_id = space.pk if space is not None else space_id
    if target_space_id is None:
        raise ValueError("touch_space requires either space or space_id")
    updated_at = timezone.now()
    Space.objects.filter(pk=target_space_id).update(updated_at=updated_at)
    if space is not None:
        space.updated_at = updated_at


def _create_default_roles(*, space: Space, created_by: User) -> tuple[Role, Role]:
    facilitator_role = Role.objects.create(
        space=space,
        created_by=created_by,
        label="Facilitator",
        can_post=True,
        can_create_draft=True,
        can_edit_others_post=True,
        can_delete_own_post=True,
        can_view_history=True,
        can_create_discussion=True,
        can_rename_discussion=True,
        can_delete_discussion=True,
        can_promote_post=True,
        can_set_permissions=True,
        can_resolve=True,
        can_reopen_discussion=True,
        can_reorganise=True,
        can_restructure=True,
        can_moderate_content=True,
        can_manage_participants=True,
        can_close_space=True,
        can_archive_space=True,
        can_unarchive_space=True,
        can_modify_closed_space=True,
        can_view_drafts=True,
        can_opine=True,
        can_react=True,
    )

    Role.objects.create(
        space=space,
        created_by=created_by,
        label="Moderator",
        can_post=True,
        can_create_draft=True,
        can_edit_others_post=True,
        can_delete_own_post=True,
        can_view_history=True,
        can_view_drafts=True,
        can_opine=True,
        can_react=True,
        can_rename_discussion=True,
        can_promote_post=True,
        can_resolve=True,
        can_reopen_discussion=True,
        can_reorganise=True,
        can_moderate_content=True,
        can_modify_closed_space=True,
    )

    member_role = Role.objects.create(
        space=space,
        created_by=created_by,
        label="Member",
        can_post=True,
        can_create_draft=True,
        can_delete_own_post=True,
        can_view_history=True,
        can_opine=True,
        can_react=True,
        is_default=True,
    )

    Role.objects.create(
        space=space,
        created_by=created_by,
        label="Observer",
        can_post=False,
        can_create_draft=False,
        can_edit_others_post=False,
        can_delete_own_post=False,
        can_view_history=True,
        can_opine=False,
        can_react=False,
    )

    return facilitator_role, member_role


def create_space(
    *,
    title: str,
    created_by: User,
    description: str = "",
    information: str = "",
    template_slug: str = "",
    is_public: bool = True,
    opinion_types: list[str] | None = None,
    reaction_types: list[str] | None = None,
    starts_at: datetime.datetime | None = None,
    ends_at: datetime.datetime | None = None,
) -> Space:
    if opinion_types is None:
        opinion_types = ["agree", "disagree"]
    if reaction_types is None:
        reaction_types = ["like", "dislike"]

    with transaction.atomic():
        space = Space.objects.create(
            title=title,
            description=description,
            information=information,
            template_slug=template_slug,
            is_public=is_public,
            opinion_types=opinion_types,
            reaction_types=reaction_types,
            starts_at=starts_at,
            ends_at=ends_at,
            created_by=created_by,
        )

        facilitator_role, member_role = _create_default_roles(space=space, created_by=created_by)

        space.default_role = member_role
        root_discussion = Discussion.add_root(
            space=space,
            created_by=created_by,
            label=title,
            sequence_index=0,
        )
        space.root_discussion = root_discussion
        space.save(update_fields=["default_role", "root_discussion"])

        SpaceParticipant.objects.create(
            space=space,
            user=created_by,
            role=facilitator_role,
            created_by=created_by,
        )

    return space


def _set_lifecycle(*, space: Space, lifecycle: str) -> Space:
    space.lifecycle = lifecycle
    space.save(update_fields=["lifecycle"])
    touch_space(space=space)
    return space


def open_space(*, space: Space) -> Space:
    return _set_lifecycle(space=space, lifecycle=Space.Lifecycle.OPEN)


def transition_space_lifecycle(*, space: Space, lifecycle: str) -> Space:
    if lifecycle == space.lifecycle:
        return space
    allowed = VALID_LIFECYCLE_TRANSITIONS.get(space.lifecycle, set())
    if lifecycle not in allowed:
        raise ValueError(f"Cannot transition from '{space.lifecycle}' to '{lifecycle}'.")
    return _set_lifecycle(space=space, lifecycle=lifecycle)


def join_space(*, space: Space, user: User, role: Role | None = None) -> SpaceParticipant:
    if not space.is_active:
        msg = "Cannot join a space that is not active"
        raise ValueError(msg)
    if role is None:
        role = space.default_role
    if role is None:
        msg = "Space has no default role configured"
        raise ValueError(msg)
    _ensure_role_belongs_to_space(role=role, space=space)
    participant, _created = SpaceParticipant.objects.get_or_create(
        space=space,
        user=user,
        defaults={"role": role, "created_by": user},
    )
    if _created:
        touch_space(space=space)
    return participant


def leave_space(*, space: Space, user: User) -> None:
    deleted_count, _ = SpaceParticipant.objects.filter(space=space, user=user).delete()
    if deleted_count:
        touch_space(space=space)


def delete_space(*, space: Space) -> Space:
    with transaction.atomic():
        SpaceParticipant.objects.filter(space=space).delete()
        SpaceInvite.objects.filter(space=space).delete()
        if space.default_role_id is not None or space.root_discussion_id is not None:
            space.default_role = None
            space.root_discussion = None
            space.save(update_fields=["default_role", "root_discussion"])
        Discussion.objects.filter(space=space).delete()
        Role.objects.filter(space=space).delete()
        space.delete()
    return space


def update_participant_role(*, participant: SpaceParticipant, role: Role) -> SpaceParticipant:
    _ensure_role_belongs_to_space(role=role, space=participant.space)
    participant.role = role
    participant.save(update_fields=["role"])
    touch_space(space=participant.space)
    return participant


# ── Role management ───────────────────────────────────────────────


def create_role(*, space: Space, label: str, created_by: User, post_highlight_color: str = "") -> Role:
    if not label:
        raise ValueError("Role name is required.")
    if Role.objects.filter(space=space, label=label).exists():
        raise ValueError(f'Role "{label}" already exists.')
    role = Role.objects.create(
        space=space,
        label=label,
        created_by=created_by,
        post_highlight_color=_normalize_post_highlight_color(post_highlight_color),
    )
    touch_space(space=space)
    return role


def update_role(
    *,
    role: Role,
    label: str | None = None,
    permissions: dict[str, bool] | None = None,
    post_highlight_color: str | None = None,
) -> Role:
    with transaction.atomic():
        if label and label != role.label:
            if Role.objects.filter(space=role.space, label=label).exclude(pk=role.pk).exists():
                raise ValueError(f'Role "{label}" already exists.')
            role.label = label

        if post_highlight_color is not None:
            role.post_highlight_color = _normalize_post_highlight_color(post_highlight_color)

        if permissions is not None:
            for field, value in permissions.items():
                setattr(role, field, value)

        # Guard: prevent removing the last role with can_set_permissions
        if not role.can_set_permissions:
            other_admin_roles = (
                Role.objects.select_for_update().filter(space=role.space, can_set_permissions=True).exclude(pk=role.pk)
            )
            if not other_admin_roles.exists():
                raise ValueError("At least one role must retain permission management.")

        update_fields = ["label"]
        if post_highlight_color is not None:
            update_fields.append("post_highlight_color")
        if permissions is not None:
            update_fields.extend(permissions.keys())
        role.save(update_fields=update_fields)
        touch_space(space=role.space)
    return role


def delete_role(*, role: Role) -> str:
    if SpaceParticipant.objects.filter(role=role).exists():
        raise ValueError(f'Cannot delete "{role.label}" — it has participants assigned.')
    if role.space.default_role_id == role.pk:
        raise ValueError(f'Cannot delete "{role.label}" — it is the default role.')
    label = role.label
    space = role.space
    role.delete()
    touch_space(space=space)
    return label


def set_default_role(*, space: Space, role: Role) -> Space:
    _ensure_role_belongs_to_space(role=role, space=space)
    space.default_role = role
    space.save(update_fields=["default_role"])
    touch_space(space=space)
    return space
