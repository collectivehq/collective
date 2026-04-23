from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

from apps.invitations.models import SpaceInvite, default_invite_expiry
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.spaces.services import join_space, touch_space
from apps.users.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone


@dataclass(slots=True)
class InvitationBatchResult:
    invites: list[SpaceInvite]
    invalid_emails: list[str]
    skipped_participants: list[str]


def split_invitation_emails(value: str) -> list[str]:
    return [chunk for chunk in re.split(r"[\s,;]+", value) if chunk]


def normalize_invite_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email is required.")
    try:
        validate_email(normalized)
    except ValidationError as error:
        raise ValueError(f'Invalid email address: "{email.strip()}".') from error
    return normalized


def pending_targeted_invites_for_user(user: User) -> QuerySet[SpaceInvite]:
    return (
        SpaceInvite.objects.filter(
            email__iexact=user.email,
            accepted_at__isnull=True,
            rejected_at__isnull=True,
            expires_at__gt=timezone.now(),
            space__deleted_at__isnull=True,
        )
        .select_related("space", "space__root_discussion", "space__default_role", "role", "created_by")
        .order_by("space_id", "-last_sent_at", "-created_at")
    )


def pending_targeted_invite_for_space(*, space: Space, user: User) -> SpaceInvite | None:
    return pending_targeted_invites_for_user(user).filter(space=space).first()


def targeted_invites_for_space(*, space: Space, query: str = "") -> QuerySet[SpaceInvite]:
    invites = (
        SpaceInvite.objects.filter(space=space).exclude(email="").select_related("role", "created_by", "accepted_by")
    )
    if not query:
        return invites
    return invites.filter(
        Q(email__icontains=query)
        | Q(role__label__icontains=query)
        | Q(created_by__name__icontains=query)
        | Q(created_by__email__icontains=query)
    )


def invite_links_for_space(*, space: Space) -> QuerySet[SpaceInvite]:
    return (
        SpaceInvite.objects.filter(space=space, email="").select_related("role", "created_by").order_by("-created_at")
    )


def create_invite(*, space: Space, role: Role, created_by: User, email: str = "") -> SpaceInvite:
    if role.space_id != space.pk:
        raise ValueError("Role does not belong to this space")
    invite = SpaceInvite.objects.create(
        space=space,
        role=role,
        created_by=created_by,
        email=normalize_invite_email(email) if email else "",
    )
    touch_space(space=space)
    return invite


def create_or_refresh_email_invites(
    *,
    space: Space,
    role: Role,
    created_by: User,
    emails: list[str],
) -> InvitationBatchResult:
    if role.space_id != space.pk:
        raise ValueError("Role does not belong to this space")

    invites: list[SpaceInvite] = []
    invalid_emails: list[str] = []
    skipped_participants: list[str] = []
    seen_emails: set[str] = set()

    with transaction.atomic():
        for raw_email in emails:
            try:
                normalized = normalize_invite_email(raw_email)
            except ValueError:
                invalid_emails.append(raw_email.strip())
                continue

            if normalized in seen_emails:
                continue
            seen_emails.add(normalized)

            if SpaceParticipant.objects.filter(space=space, user__email__iexact=normalized).exists():
                skipped_participants.append(normalized)
                continue

            invite = (
                SpaceInvite.objects.filter(space=space, accepted_at__isnull=True, email__iexact=normalized)
                .order_by("-last_sent_at", "-created_at")
                .first()
            )

            now = timezone.now()
            expires_at = default_invite_expiry()
            if invite is None:
                invite = SpaceInvite.objects.create(
                    space=space,
                    role=role,
                    created_by=created_by,
                    email=normalized,
                    last_sent_at=now,
                    expires_at=expires_at,
                )
            else:
                invite.role = role
                invite.created_by = created_by
                invite.email = normalized
                invite.last_sent_at = now
                invite.expires_at = expires_at
                invite.rejected_at = None
                invite.rejected_by = None
                invite.save(
                    update_fields=[
                        "role",
                        "created_by",
                        "email",
                        "last_sent_at",
                        "expires_at",
                        "rejected_at",
                        "rejected_by",
                    ]
                )
            invites.append(invite)

        if invites:
            touch_space(space=space)

    return InvitationBatchResult(
        invites=invites,
        invalid_emails=invalid_emails,
        skipped_participants=skipped_participants,
    )


def refresh_invites(*, invites: list[SpaceInvite], created_by: User) -> list[SpaceInvite]:
    if not invites:
        return []

    with transaction.atomic():
        for invite in invites:
            invite.created_by = created_by
            invite.last_sent_at = timezone.now()
            invite.expires_at = default_invite_expiry()
            invite.rejected_at = None
            invite.rejected_by = None
            invite.save(update_fields=["created_by", "last_sent_at", "expires_at", "rejected_at", "rejected_by"])

        touch_space(space=invites[0].space)

    return invites


def accept_invite(*, invite: SpaceInvite, user: User) -> SpaceParticipant:
    if invite.email and invite.email.casefold() != user.email.casefold():
        raise ValueError("This invitation was sent to a different email address.")
    if invite.is_expired:
        raise ValueError("This invitation has expired.")
    if invite.rejected_at is not None:
        raise ValueError("This invitation has already been declined.")

    participant = join_space(space=invite.space, user=user, role=invite.role)
    if invite.email:
        invite.accepted_at = timezone.now()
        invite.accepted_by = user
        invite.rejected_at = None
        invite.rejected_by = None
        invite.save(update_fields=["accepted_at", "accepted_by", "rejected_at", "rejected_by"])
    return participant


def reject_invite(*, invite: SpaceInvite, user: User) -> SpaceInvite:
    if not invite.email:
        raise ValueError("Only targeted invitations can be declined.")
    if invite.email.casefold() != user.email.casefold():
        raise ValueError("This invitation was sent to a different email address.")
    if invite.accepted_at is not None:
        raise ValueError("This invitation has already been accepted.")
    if invite.is_expired:
        raise ValueError("This invitation has expired.")

    invite.rejected_at = timezone.now()
    invite.rejected_by = user
    invite.save(update_fields=["rejected_at", "rejected_by"])
    return invite


def send_invitation_email(request: HttpRequest, invite: SpaceInvite) -> None:
    invite_path = reverse("invitations:invite_accept", kwargs={"space_id": invite.space_id, "invite_id": invite.pk})
    invite_url = request.build_absolute_uri(invite_path)
    signup_url = request.build_absolute_uri(
        f"{reverse('account_signup')}?{urlencode({'next': invite_path, 'email': invite.email})}"
    )
    login_url = request.build_absolute_uri(f"{reverse('account_login')}?{urlencode({'next': invite_path})}")
    registered_user = User.objects.filter(email__iexact=invite.email).first() if invite.email else None

    subject = f'Invitation to join "{invite.space.title}"'
    body_lines = [
        f'You have been invited to join "{invite.space.title}" as {invite.role.label}.',
        f"Invitation sent by: {invite.created_by.name or invite.created_by.email}",
        f"Invitation expires: {invite.expires_at:%Y-%m-%d %H:%M UTC}",
        "",
    ]

    if invite.email:
        if registered_user is None:
            body_lines.extend(
                [
                    "This email address is not registered yet.",
                    "Register first, then return to the invitation link:",
                    signup_url,
                    "",
                    "Invitation link:",
                    invite_url,
                ]
            )
        else:
            body_lines.extend(["Sign in, then accept the invitation:", login_url, "", "Invitation link:", invite_url])
    else:
        body_lines.extend(["Invitation link:", invite_url])

    send_mail(
        subject,
        "\n".join(body_lines),
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@collective.local"),
        [invite.email] if invite.email else [],
        fail_silently=False,
    )


__all__ = [
    "InvitationBatchResult",
    "accept_invite",
    "create_invite",
    "create_or_refresh_email_invites",
    "invite_links_for_space",
    "normalize_invite_email",
    "pending_targeted_invite_for_space",
    "pending_targeted_invites_for_user",
    "refresh_invites",
    "reject_invite",
    "send_invitation_email",
    "split_invitation_emails",
    "targeted_invites_for_space",
]
