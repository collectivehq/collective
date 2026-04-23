from __future__ import annotations

from typing import TypedDict
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import get_user
from apps.discussions.permissions import can_create_discussion, can_reorganise
from apps.invitations.models import SpaceInvite
from apps.invitations.presenters import (
    InvitationListItem,
    InvitedSpaceItem,
    build_invitation_items,
    build_invited_space_items,
)
from apps.invitations.services import (
    invite_links_for_space,
    pending_targeted_invite_for_space,
    pending_targeted_invites_for_user,
    targeted_invites_for_space,
)
from apps.spaces import services as space_services
from apps.spaces.constants import (
    EDIT_WINDOW_STEP_OPTIONS,
    PERMISSION_GROUPS,
    PERMISSION_LABELS,
    POST_HIGHLIGHT_COLOR_PRESETS,
)
from apps.spaces.forms import SpaceCreateForm, SpaceSettingsForm
from apps.spaces.importers.docx_import import DocxImportError, import_space_from_docx
from apps.spaces.importers.markdown_import import MarkdownImportError, import_space_from_markdown
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.spaces.permissions import (
    can_archive_space,
    can_close_space,
    can_manage_participants,
    can_set_permissions,
    can_unarchive_space,
    can_view_space,
)
from apps.spaces.presenters import build_space_recent_activity
from apps.spaces.request_context import get_space_request_context
from apps.users.models import User


class LifecycleAction(TypedDict):
    value: str
    label: str
    tone: str
    confirm_title: str
    confirm_message: str


def _updated_querystring(request: HttpRequest, **updates: object | None) -> str:
    query = request.GET.copy()
    for key, value in updates.items():
        if value in (None, ""):
            query.pop(key, None)
            continue
        query[key] = str(value)
    return query.urlencode()


def _lifecycle_actions_for(space: Space) -> list[LifecycleAction]:
    labels = {
        Space.Lifecycle.OPEN: "Open space",
        Space.Lifecycle.CLOSED: "Close space",
        Space.Lifecycle.ARCHIVED: "Archive space",
    }
    tones = {
        Space.Lifecycle.OPEN: "neutral",
        Space.Lifecycle.CLOSED: "warning",
        Space.Lifecycle.ARCHIVED: "danger",
    }
    allowed = space_services.VALID_LIFECYCLE_TRANSITIONS.get(space.lifecycle, set())
    ordered_actions = [Space.Lifecycle.OPEN, Space.Lifecycle.CLOSED, Space.Lifecycle.ARCHIVED]

    if space.lifecycle == Space.Lifecycle.ARCHIVED:
        labels[Space.Lifecycle.CLOSED] = "Unarchive space"
        tones[Space.Lifecycle.CLOSED] = "neutral"

    confirmation_copy = {
        Space.Lifecycle.OPEN: (
            "Open space?",
            "This will make the space active again so participants can join and contribute.",
        ),
        Space.Lifecycle.CLOSED: (
            "Close space?",
            "This will stop new participation while keeping the space available to review.",
        ),
        Space.Lifecycle.ARCHIVED: (
            "Archive space?",
            "This will move the space into long-term storage and remove it from active workflows.",
        ),
    }
    if space.lifecycle == Space.Lifecycle.ARCHIVED:
        confirmation_copy[Space.Lifecycle.CLOSED] = (
            "Unarchive space?",
            "This will restore the space to the closed state so it can be managed or reopened.",
        )

    return [
        {
            "value": lifecycle,
            "label": labels[lifecycle],
            "tone": tones[lifecycle],
            "confirm_title": confirmation_copy[lifecycle][0],
            "confirm_message": confirmation_copy[lifecycle][1],
        }
        for lifecycle in ordered_actions
        if lifecycle in allowed
    ]


def _can_transition_space_lifecycle(
    *,
    user: User,
    space: Space,
    target_lifecycle: str,
    participant: SpaceParticipant | None,
) -> bool:
    if target_lifecycle == Space.Lifecycle.CLOSED:
        if space.lifecycle == Space.Lifecycle.OPEN:
            return can_close_space(user, space, participant=participant)
        if space.lifecycle == Space.Lifecycle.ARCHIVED:
            return can_unarchive_space(user, space, participant=participant)
        return False

    if target_lifecycle == Space.Lifecycle.OPEN:
        return space.lifecycle == Space.Lifecycle.CLOSED and can_close_space(user, space, participant=participant)

    if target_lifecycle == Space.Lifecycle.ARCHIVED:
        return space.lifecycle == Space.Lifecycle.CLOSED and can_archive_space(user, space, participant=participant)

    return False


def _should_show_about_modal(request: HttpRequest, space: Space) -> bool:
    referer = request.META.get("HTTP_REFERER", "").strip()
    if not referer:
        return True

    referer_path = urlparse(referer).path
    return not referer_path.startswith(f"/spaces/{space.pk}/")


def _public_space_list_queryset() -> QuerySet[Space]:
    public_visibility = Q(lifecycle__in=[Space.Lifecycle.CLOSED, Space.Lifecycle.ARCHIVED]) | Q(
        lifecycle=Space.Lifecycle.OPEN
    )
    now = timezone.now()
    return (
        Space.objects.filter(is_public=True, deleted_at__isnull=True)
        .with_summary_counts()
        .filter(public_visibility)
        .select_related("root_discussion", "default_role")
        .order_by("-updated_at", "-created_at")
        .exclude(
            lifecycle=Space.Lifecycle.OPEN,
            starts_at__isnull=False,
            starts_at__gt=now,
        )
        .exclude(
            lifecycle=Space.Lifecycle.OPEN,
            ends_at__isnull=False,
            ends_at__lte=now,
        )
    )


def space_list(request: HttpRequest) -> HttpResponse:
    invited_spaces: list[InvitedSpaceItem] = []
    if request.user.is_authenticated:
        user = get_user(request)
        participating = (
            Space.objects.for_user(user)
            .with_summary_counts()
            .select_related("root_discussion", "default_role")
            .order_by("-updated_at", "-created_at")
        )
        pending_invites = list(pending_targeted_invites_for_user(user))
        invited_queryset = (
            Space.objects.filter(invites__in=pending_invites)
            .with_summary_counts()
            .select_related("root_discussion", "default_role")
            .distinct()
            .exclude(pk__in=participating)
        )
        invited_spaces = build_invited_space_items(list(invited_queryset), pending_invites)
        public_spaces = (
            _public_space_list_queryset()
            .exclude(pk__in=participating)
            .exclude(pk__in=[item["space"].pk for item in invited_spaces])
        )
        total_visible_spaces = participating.count() + len(invited_spaces) + public_spaces.count()
    else:
        participating = Space.objects.none()
        public_spaces = _public_space_list_queryset()
        total_visible_spaces = public_spaces.count()

    return render(
        request,
        "spaces/space_list.html",
        {
            "participating": participating,
            "invited_spaces": invited_spaces,
            "public_spaces": public_spaces,
            "has_any_spaces": Space.objects.filter(deleted_at__isnull=True).exists(),
            "total_visible_spaces": total_visible_spaces,
        },
    )


@login_required
def space_create(request: HttpRequest) -> HttpResponse:
    user = get_user(request)
    if request.method == "POST":
        form = SpaceCreateForm(request.POST, request.FILES)
        if form.is_valid():
            source_docx = form.cleaned_data["source_docx"]
            source_markdown = form.cleaned_data["source_markdown"]
            docx_bytes = source_docx.read() if source_docx is not None else None
            markdown_bytes = source_markdown.read() if source_markdown is not None else None
            error_field = "source_docx" if docx_bytes is not None else "source_markdown"
            try:
                with transaction.atomic():
                    space = space_services.create_space(
                        title=form.cleaned_data["title"],
                        description=form.cleaned_data["description"],
                        information=form.cleaned_data["information"],
                        is_public=bool(form.cleaned_data["is_public"]),
                        created_by=user,
                    )
                    space_services.open_space(space=space)
                    if docx_bytes is not None:
                        import_space_from_docx(space=space, author=user, docx_bytes=docx_bytes)
                    if markdown_bytes is not None:
                        import_space_from_markdown(space=space, author=user, markdown_bytes=markdown_bytes)
            except (DocxImportError, MarkdownImportError) as exc:
                form.add_error(error_field, str(exc))
            else:
                messages.success(request, f'Space "{space.title}" created.')
                return redirect("spaces:detail", space_id=space.pk)
    else:
        form = SpaceCreateForm()
    return render(request, "spaces/space_create.html", {"form": form})


@login_required
def space_detail(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(
        request,
        space_id,
        select_related=("created_by", "root_discussion"),
    )
    space = context.space
    user = context.user
    participant = context.participant
    if not can_view_space(user, space, participant=participant):
        pending_invite = pending_targeted_invite_for_space(space=space, user=user)
        if pending_invite is not None:
            return redirect("invitations:invite_accept", space_id=space.pk, invite_id=pending_invite.pk)
        if not space.is_public:
            raise Http404
        return redirect("spaces:join", space_id=space.pk)

    root_discussion = space.root_discussion
    participant_count = SpaceParticipant.objects.filter(space=space).count()
    user_can_create_discussion = can_create_discussion(user, space, participant=participant)
    user_can_reorganise = can_reorganise(user, space, participant=participant)
    user_can_manage_participants = can_manage_participants(user, space, participant=participant)
    user_can_set_permissions = can_set_permissions(user, space, participant=participant)
    user_can_view_participants = participant is not None
    lifecycle_actions = [
        action
        for action in _lifecycle_actions_for(space)
        if _can_transition_space_lifecycle(
            user=user,
            space=space,
            target_lifecycle=str(action["value"]),
            participant=participant,
        )
    ]

    return render(
        request,
        "spaces/space_detail.html",
        {
            "space": space,
            "participant": participant,
            "root_discussion": root_discussion,
            "participant_count": participant_count,
            "can_shape": user_can_create_discussion,
            "can_reorganise": user_can_reorganise,
            "can_view_participants": user_can_view_participants,
            "can_manage_participants": user_can_manage_participants,
            "can_set_permissions": user_can_set_permissions,
            "lifecycle_actions": lifecycle_actions,
            "recent_activity_items": build_space_recent_activity(space),
            "show_about_modal": _should_show_about_modal(request, space),
        },
    )


@login_required
def space_join(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = (
        Space.objects.with_summary_counts().select_related("root_discussion", "default_role").get(pk=context.space.pk)
    )
    user = context.user

    if not space.is_active:
        messages.error(request, "This space is not open for joining.")
        return redirect("spaces:list")
    if not space.is_public:
        pending_invite = pending_targeted_invite_for_space(space=space, user=user)
        if pending_invite is None:
            raise Http404
        return redirect("invitations:invite_accept", space_id=space.pk, invite_id=pending_invite.pk)

    existing = SpaceParticipant.objects.filter(space=space, user=user).first()
    if existing:
        return redirect("spaces:detail", space_id=space.pk)

    if request.method == "POST":
        try:
            space_services.join_space(space=space, user=user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("spaces:list")
        messages.success(request, f'Joined "{space.title}".')
        return redirect("spaces:detail", space_id=space.pk)

    return render(request, "spaces/space_join.html", {"space": space})


@login_required
def space_settings(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_set_permissions(user, space, participant=participant):
        messages.error(request, "Permission denied.")
        return redirect("spaces:detail", space_id=space.pk)

    if request.method == "POST":
        form = SpaceSettingsForm(request.POST, instance=space, allow_image_uploads=True)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings updated.")
            return redirect("spaces:settings", space_id=space.pk)
    else:
        form = SpaceSettingsForm(instance=space, allow_image_uploads=True)

    edit_window_options = [
        {
            "value": "" if minutes is None else str(minutes),
            "label": label,
            "measure_label": measure_label,
        }
        for minutes, label, measure_label in EDIT_WINDOW_STEP_OPTIONS
    ]

    return render(
        request,
        "spaces/space_settings.html",
        {"space": space, "form": form, "edit_window_options": edit_window_options},
    )


@require_POST
@login_required
def space_delete(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_set_permissions(user, space, participant=participant):
        messages.error(request, "Permission denied.")
        return redirect("spaces:detail", space_id=space.pk)

    space_services.delete_space(space=space)
    messages.success(request, f'Deleted "{space.title}".')
    return redirect("spaces:list")


@login_required
def space_participants(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if participant is None:
        raise PermissionDenied

    active_tab = (request.GET.get("tab") or "participants").strip() or "participants"
    can_manage = can_manage_participants(user, space, participant=participant)
    can_set_roles = can_set_permissions(user, space, participant=participant)
    if active_tab == "invitations" and not can_manage:
        active_tab = "participants"

    roles = Role.objects.filter(space=space).order_by("label") if (can_set_roles or can_manage) else Role.objects.none()

    participant_query = (request.GET.get("participant_q") or "").strip()
    participants = SpaceParticipant.objects.filter(space=space).select_related("user", "role")
    if participant_query:
        participants = participants.filter(
            Q(user__name__icontains=participant_query)
            | Q(user__email__icontains=participant_query)
            | Q(role__label__icontains=participant_query)
        )
    participant_page_obj = Paginator(participants.order_by("created_at", "user__email"), 10).get_page(
        request.GET.get("participants_page")
    )

    invitation_query = (request.GET.get("invitation_q") or "").strip()
    invitation_items: list[InvitationListItem] = []
    invitation_page_obj = None
    invite_links = SpaceInvite.objects.none()
    if can_manage:
        targeted_invites = targeted_invites_for_space(space=space, query=invitation_query)
        invitation_page_obj = Paginator(
            targeted_invites.order_by("-accepted_at", "-rejected_at", "-last_sent_at", "-created_at"),
            10,
        ).get_page(request.GET.get("invitations_page"))
        invitation_items = build_invitation_items(list(invitation_page_obj.object_list))
        invite_links = invite_links_for_space(space=space)

    return render(
        request,
        "spaces/space_participants.html",
        {
            "space": space,
            "active_tab": active_tab,
            "participant_query": participant_query,
            "participant_page_obj": participant_page_obj,
            "participant_prev_query": _updated_querystring(
                request,
                tab="participants",
                participants_page=(
                    participant_page_obj.previous_page_number() if participant_page_obj.has_previous() else None
                ),
            ),
            "participant_next_query": _updated_querystring(
                request,
                tab="participants",
                participants_page=participant_page_obj.next_page_number() if participant_page_obj.has_next() else None,
            ),
            "can_manage": can_manage,
            "can_set_permissions": can_set_roles,
            "roles": roles,
            "invitation_query": invitation_query,
            "invitation_items": invitation_items,
            "invitation_page_obj": invitation_page_obj,
            "invitation_prev_query": (
                _updated_querystring(
                    request,
                    tab="invitations",
                    invitations_page=(
                        invitation_page_obj.previous_page_number()
                        if invitation_page_obj and invitation_page_obj.has_previous()
                        else None
                    ),
                )
                if invitation_page_obj is not None
                else ""
            ),
            "invitation_next_query": (
                _updated_querystring(
                    request,
                    tab="invitations",
                    invitations_page=(
                        invitation_page_obj.next_page_number()
                        if invitation_page_obj and invitation_page_obj.has_next()
                        else None
                    ),
                )
                if invitation_page_obj is not None
                else ""
            ),
            "invite_links": invite_links,
        },
    )


@require_POST
@login_required
def participant_remove(request: HttpRequest, space_id: str, participant_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    target = get_object_or_404(SpaceParticipant, pk=participant_id, space=space)
    if target.user_id == user.pk:
        messages.error(request, "You cannot remove yourself from the space.")
        return redirect("spaces:participants", space_id=space.pk)
    target_user: User = target.user
    space_services.leave_space(space=space, user=target_user)
    messages.success(request, f'Removed "{target_user.name or target_user.email}" from space.')
    return redirect("spaces:participants", space_id=space.pk)


@require_POST
@login_required
def participant_role_update(request: HttpRequest, space_id: str, participant_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_set_permissions(user, space, participant=actor):
        raise PermissionDenied

    target = get_object_or_404(SpaceParticipant, pk=participant_id, space=space)
    role_id = request.POST.get("role_id")
    role = get_object_or_404(Role, pk=role_id, space=space)
    space_services.update_participant_role(participant=target, role=role)
    messages.success(request, f'Updated role for "{target.user.name or target.user.email}".')
    return redirect("spaces:participants", space_id=space.pk)


# ── Roles & Permissions ──────────────────────────────────────────


@login_required
def space_permissions(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    participant = context.participant
    if not can_set_permissions(context.user, space, participant=participant):
        raise PermissionDenied

    roles = Role.objects.filter(space=space).annotate(participant_count=Count("participants")).order_by("label")

    role_data = []
    for role in roles:
        permission_groups = [
            {
                "title": title,
                "permissions": [(field, PERMISSION_LABELS[field], getattr(role, field)) for field in fields],
            }
            for title, fields in PERMISSION_GROUPS
        ]
        role_data.append(
            {
                "role": role,
                "post_highlight_color": role.post_highlight_color,
                "permission_groups": permission_groups,
                "participant_count": role.participant_count,
            }
        )

    return render(
        request,
        "spaces/space_permissions.html",
        {
            "space": space,
            "role_data": role_data,
            "post_highlight_color_presets": POST_HIGHLIGHT_COLOR_PRESETS,
        },
    )


@require_POST
@login_required
def role_create(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_set_permissions(context.user, space, participant=participant):
        raise PermissionDenied

    label = (request.POST.get("label") or "").strip()
    try:
        space_services.create_role(
            space=space,
            label=label,
            created_by=user,
            post_highlight_color=(request.POST.get("post_highlight_color") or "").strip(),
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("spaces:permissions", space_id=space.pk)

    messages.success(request, f'Role "{label}" created.')
    return redirect("spaces:permissions", space_id=space.pk)


@require_POST
@login_required
def role_update(request: HttpRequest, space_id: str, role_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    participant = context.participant
    if not can_set_permissions(context.user, space, participant=participant):
        raise PermissionDenied

    role = get_object_or_404(Role, pk=role_id, space=space)

    label = (request.POST.get("label") or "").strip()
    permissions = {field: field in request.POST for field in PERMISSION_LABELS}
    post_highlight_color = (request.POST.get("post_highlight_color") or "").strip()
    try:
        space_services.update_role(
            role=role,
            label=label or None,
            permissions=permissions,
            post_highlight_color=post_highlight_color,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("spaces:permissions", space_id=space.pk)

    messages.success(request, f'Role "{role.label}" updated.')
    return redirect("spaces:permissions", space_id=space.pk)


@require_POST
@login_required
def role_delete(request: HttpRequest, space_id: str, role_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    participant = context.participant
    if not can_set_permissions(context.user, space, participant=participant):
        raise PermissionDenied

    role = get_object_or_404(Role, pk=role_id, space=space)

    try:
        label = space_services.delete_role(role=role)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("spaces:permissions", space_id=space.pk)

    if request.headers.get("HX-Request"):
        return HttpResponse("")

    messages.success(request, f'Role "{label}" deleted.')
    return redirect("spaces:permissions", space_id=space.pk)


@require_POST
@login_required
def role_set_default(request: HttpRequest, space_id: str, role_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    participant = context.participant
    if not can_set_permissions(context.user, space, participant=participant):
        raise PermissionDenied

    role = get_object_or_404(Role, pk=role_id, space=space)
    space_services.set_default_role(space=space, role=role)
    messages.success(request, f'"{role.label}" is now the default role for new members.')
    return redirect("spaces:permissions", space_id=space.pk)


# ── Participant management ────────────────────────────────────────


@require_POST
@login_required
def participant_add(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    actor = context.participant
    if not can_manage_participants(user, space, participant=actor):
        raise PermissionDenied

    email = (request.POST.get("email") or "").strip()
    if not email:
        messages.error(request, "Email is required.")
        return redirect("spaces:participants", space_id=space.pk)

    try:
        target_user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, f'No user found with email "{email}".')
        return redirect("spaces:participants", space_id=space.pk)

    if SpaceParticipant.objects.filter(space=space, user=target_user).exists():
        messages.info(request, f'"{target_user.name or target_user.email}" is already a participant.')
        return redirect("spaces:participants", space_id=space.pk)

    role = space.default_role
    if role is None:
        messages.error(request, "No default role configured for this space.")
        return redirect("spaces:participants", space_id=space.pk)

    SpaceParticipant.objects.create(space=space, user=target_user, role=role, created_by=user)
    messages.success(request, f'Added "{target_user.name or target_user.email}".')
    return redirect("spaces:participants", space_id=space.pk)


@require_POST
@login_required
def space_lifecycle_update(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    target_lifecycle = (request.POST.get("lifecycle") or "").strip()
    if not _can_transition_space_lifecycle(
        user=user,
        space=space,
        target_lifecycle=target_lifecycle,
        participant=participant,
    ):
        raise PermissionDenied

    try:
        space_services.transition_space_lifecycle(space=space, lifecycle=target_lifecycle)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Space status updated.")
    return redirect("spaces:detail", space_id=space.pk)
