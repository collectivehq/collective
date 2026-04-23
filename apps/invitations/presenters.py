from __future__ import annotations

from typing import TypedDict

from apps.invitations.models import SpaceInvite
from apps.spaces.models import Space
from apps.users.models import User


class InvitationListItem(TypedDict):
    invite: SpaceInvite
    registered_user: User | None
    status: str
    status_label: str
    status_tone: str


class InvitedSpaceItem(TypedDict):
    space: Space
    invite: SpaceInvite


def build_invitation_items(invites: list[SpaceInvite]) -> list[InvitationListItem]:
    email_values = [invite.email for invite in invites if invite.email]
    users_by_email = {
        resolved_user.email.casefold(): resolved_user for resolved_user in User.objects.filter(email__in=email_values)
    }

    items: list[InvitationListItem] = []
    for invite in invites:
        registered_user = users_by_email.get(invite.email.casefold()) if invite.email else None
        if invite.accepted_at is not None:
            status = "accepted"
            status_label = "Accepted"
            status_tone = "badge-success"
        elif invite.rejected_at is not None:
            status = "rejected"
            status_label = "Rejected"
            status_tone = "badge-neutral"
        elif invite.is_expired:
            status = "expired"
            status_label = "Expired"
            status_tone = "badge-error"
        elif registered_user is None:
            status = "invited"
            status_label = "Invited"
            status_tone = "badge-info"
        else:
            status = "pending"
            status_label = "Pending"
            status_tone = "badge-warning"

        items.append(
            {
                "invite": invite,
                "registered_user": registered_user,
                "status": status,
                "status_label": status_label,
                "status_tone": status_tone,
            }
        )

    return items


def build_invited_space_items(spaces: list[Space], invites: list[SpaceInvite]) -> list[InvitedSpaceItem]:
    invite_map: dict[str, SpaceInvite] = {}
    for invite in invites:
        invite_map.setdefault(str(invite.space_id), invite)

    return [{"space": space, "invite": invite_map[str(space.pk)]} for space in spaces if str(space.pk) in invite_map]


__all__ = ["InvitationListItem", "InvitedSpaceItem", "build_invitation_items", "build_invited_space_items"]
