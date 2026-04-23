from __future__ import annotations

from urllib.parse import urlencode

from apps.core.utils import get_user
from apps.invitations.models import SpaceInvite
from apps.invitations.services import (
    accept_invite,
    create_invite,
    create_or_refresh_email_invites,
    refresh_invites,
    reject_invite,
    send_invitation_email,
    split_invitation_emails,
    targeted_invites_for_space,
)
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.spaces.permissions import can_manage_participants
from apps.spaces.request_context import get_space_request_context
from apps.users.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST


def _participants_tab_url(space_id: str) -> str:
    return f"{reverse('spaces:participants', kwargs={'space_id': space_id})}?tab=invitations"


@require_POST
@login_required
def invitation_bulk_create(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    role_id = request.POST.get("role_id")
    role = get_object_or_404(Role, pk=role_id, space=space) if role_id else space.default_role
    if role is None:
        messages.error(request, "No role selected and no default role configured.")
        return redirect(_participants_tab_url(str(space.pk)))

    emails = split_invitation_emails(request.POST.get("emails") or "")
    if not emails:
        messages.error(request, "Enter at least one email address.")
        return redirect(_participants_tab_url(str(space.pk)))

    result = create_or_refresh_email_invites(space=space, role=role, created_by=user, emails=emails)
    for invite in result.invites:
        send_invitation_email(request, invite)

    if result.invites:
        messages.success(request, f"Sent {len(result.invites)} invitation(s).")
    if result.skipped_participants:
        messages.info(request, "Already participants: " + ", ".join(result.skipped_participants))
    if result.invalid_emails:
        messages.error(request, "Invalid email addresses: " + ", ".join(result.invalid_emails))

    return redirect(_participants_tab_url(str(space.pk)))


@require_POST
@login_required
def invitation_resend_pending(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    invitation_query = (request.POST.get("invitation_q") or "").strip()
    invite_list = list(
        targeted_invites_for_space(space=space, query=invitation_query).filter(
            rejected_at__isnull=True, accepted_at__isnull=True
        )
    )
    if not invite_list:
        messages.info(request, "No pending invitations to resend.")
        return redirect(_participants_tab_url(str(space.pk)))

    refreshed_invites = refresh_invites(invites=invite_list, created_by=user)
    for invite in refreshed_invites:
        send_invitation_email(request, invite)

    messages.success(request, f"Resent {len(refreshed_invites)} pending invitation(s).")
    return redirect(_participants_tab_url(str(space.pk)))


@require_POST
@login_required
def invitation_reinvite(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    invite = get_object_or_404(SpaceInvite, pk=invite_id, space=space)
    refreshed_invite = refresh_invites(invites=[invite], created_by=user)[0]
    send_invitation_email(request, refreshed_invite)
    messages.success(request, f'Resent invitation to "{refreshed_invite.email}".')
    return redirect(_participants_tab_url(str(space.pk)))


@require_POST
@login_required
def invite_create(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    role_id = request.POST.get("role_id")
    role = get_object_or_404(Role, pk=role_id, space=space) if role_id else space.default_role
    if role is None:
        messages.error(request, "No role selected and no default role configured.")
        return redirect(_participants_tab_url(str(space.pk)))

    create_invite(space=space, role=role, created_by=user)
    messages.success(request, "Invite link created.")
    return redirect(_participants_tab_url(str(space.pk)))


@require_POST
@login_required
def invite_delete(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    invite = get_object_or_404(SpaceInvite, pk=invite_id, space=space)
    invite.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    messages.success(request, "Invitation deleted.")
    return redirect(_participants_tab_url(str(space.pk)))


def invite_accept(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    invite = get_object_or_404(
        SpaceInvite.objects.select_related("space", "role", "created_by", "accepted_by"),
        pk=invite_id,
        space_id=space_id,
        space__deleted_at__isnull=True,
    )
    space = (
        Space.objects.with_summary_counts().select_related("root_discussion", "default_role").get(pk=invite.space_id)
    )

    if not request.user.is_authenticated:
        target_path = reverse("invitations:invite_accept", kwargs={"space_id": space.pk, "invite_id": invite.pk})
        if invite.email and not User.objects.filter(email__iexact=invite.email).exists():
            messages.info(request, f'This invitation was sent to "{invite.email}". Register first to accept it.')
            return redirect(f"{reverse('account_signup')}?{urlencode({'next': target_path, 'email': invite.email})}")
        return redirect(f"{reverse('account_login')}?{urlencode({'next': target_path})}")

    user = get_user(request)

    if SpaceParticipant.objects.filter(space=space, user=user).exists():
        messages.info(request, "You are already a participant.")
        return redirect("spaces:detail", space_id=space.pk)

    if invite.email and invite.accepted_at is not None:
        messages.info(request, "This invitation has already been accepted.")
        return redirect("spaces:list")

    if invite.email and invite.rejected_at is not None:
        messages.info(request, "This invitation has already been declined.")
        return redirect("spaces:list")

    if invite.email and invite.email.casefold() != user.email.casefold():
        messages.error(request, "This invitation was sent to a different email address.")
        return redirect("spaces:list")

    if invite.is_expired:
        messages.error(request, "This invite link has expired.")
        return redirect("spaces:list")

    if not space.is_active:
        messages.error(request, "This space is not open for joining.")
        return redirect("spaces:list")

    if request.method == "POST":
        try:
            accept_invite(invite=invite, user=user)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("spaces:list")
        messages.success(request, f'Joined "{space.title}".')
        return redirect("spaces:detail", space_id=space.pk)

    return render(
        request,
        "spaces/space_join.html",
        {
            "space": space,
            "invite": invite,
            "can_reject_invite": bool(invite.email),
        },
    )


@require_POST
@login_required
def invite_reject(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    invite = get_object_or_404(
        SpaceInvite.objects.select_related("space", "role", "created_by", "accepted_by", "rejected_by"),
        pk=invite_id,
        space_id=space_id,
        space__deleted_at__isnull=True,
    )
    user = get_user(request)

    try:
        reject_invite(invite=invite, user=user)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f'Declined invitation to "{invite.space.title}".')
    return redirect("spaces:list")


__all__ = [
    "invitation_bulk_create",
    "invitation_reinvite",
    "invitation_resend_pending",
    "invite_accept",
    "invite_create",
    "invite_delete",
    "invite_reject",
]
