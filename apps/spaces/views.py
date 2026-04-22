from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.nodes.models import Node
from apps.spaces import services as space_services
from apps.spaces.constants import PERMISSION_LABELS
from apps.spaces.docx_import import DocxImportError, import_space_from_docx
from apps.spaces.forms import SpaceCreateForm, SpaceSettingsForm
from apps.spaces.markdown_import import MarkdownImportError, import_space_from_markdown
from apps.spaces.models import Role, Space, SpaceInvite, SpaceParticipant
from apps.spaces.permissions import can_view_space
from apps.users.models import User
from apps.users.utils import get_user


def _annotate_space_counts(qs: QuerySet[Space]) -> QuerySet[Space]:
    """Annotate a Space queryset with discussion, post, and participant counts."""
    return qs.defer("information").annotate(
        num_discussions=Count(
            "nodes",
            filter=Q(nodes__node_type=Node.NodeType.DISCUSSION, nodes__deleted_at__isnull=True),
            distinct=True,
        ),
        num_posts=Count(
            "nodes",
            filter=Q(nodes__node_type=Node.NodeType.POST, nodes__deleted_at__isnull=True),
            distinct=True,
        ),
        num_participants=Count("participants", distinct=True),
    )


def space_list(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        user = get_user(request)
        participating = (
            Space.objects.filter(
                participants__user=user,
                deleted_at__isnull=True,
            )
            .select_related("root_discussion", "default_role")
            .order_by("-updated_at", "-created_at")
            .distinct()
        )
        open_spaces = (
            Space.objects.filter(
                lifecycle=Space.Lifecycle.OPEN,
                deleted_at__isnull=True,
            )
            .select_related("root_discussion", "default_role")
            .order_by("-updated_at", "-created_at")
            .exclude(pk__in=participating)
        )
    else:
        participating = Space.objects.none()
        open_spaces = Space.objects.filter(
            lifecycle=Space.Lifecycle.OPEN,
            deleted_at__isnull=True,
        ).order_by("-updated_at", "-created_at")

    return render(
        request,
        "spaces/space_list.html",
        {
            "participating": _annotate_space_counts(participating),
            "open_spaces": _annotate_space_counts(open_spaces),
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
    space = get_object_or_404(
        Space.objects.select_related("created_by", "root_discussion"), pk=space_id, deleted_at__isnull=True
    )
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if not can_view_space(user, space, participant=participant):
        return redirect("spaces:join", space_id=space.pk)

    root_discussion = space.root_discussion
    participant_count = SpaceParticipant.objects.filter(space=space).count()

    return render(
        request,
        "spaces/space_detail.html",
        {
            "space": space,
            "participant": participant,
            "root_discussion": root_discussion,
            "participant_count": participant_count,
        },
    )


@login_required
def space_join(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)

    if space.lifecycle != Space.Lifecycle.OPEN:
        messages.error(request, "This space is not open for joining.")
        return redirect("spaces:list")

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
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
        messages.error(request, "Permission denied.")
        return redirect("spaces:detail", space_id=space.pk)

    if request.method == "POST":
        form = SpaceSettingsForm(request.POST, instance=space)
        if form.is_valid():
            new_lifecycle = form.cleaned_data.get("lifecycle")
            if new_lifecycle != space.lifecycle and new_lifecycle in ("closed", "archived"):
                if not participant.role.can_close_space:
                    messages.error(request, "You don't have permission to close or archive this space.")
                    return redirect("spaces:settings", space_id=space.pk)
            form.save()
            messages.success(request, "Settings updated.")
            return redirect("spaces:settings", space_id=space.pk)
    else:
        form = SpaceSettingsForm(instance=space)

    return render(request, "spaces/space_settings.html", {"space": space, "form": form})


@login_required
def space_participants(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None:
        raise PermissionDenied

    participants = SpaceParticipant.objects.filter(space=space).select_related("user", "role")
    can_manage = participant.role.can_moderate
    can_set_permissions = participant.role.can_set_permissions
    roles = Role.objects.filter(space=space) if (can_set_permissions or can_manage) else Role.objects.none()
    invites = SpaceInvite.objects.filter(space=space).select_related("role", "created_by") if can_manage else []

    return render(
        request,
        "spaces/space_participants.html",
        {
            "space": space,
            "participants": participants,
            "can_manage": can_manage,
            "can_set_permissions": can_set_permissions,
            "roles": roles,
            "invites": invites,
        },
    )


@require_POST
@login_required
def participant_remove(request: HttpRequest, space_id: str, participant_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    actor = space_services.get_participant(space=space, user=user)
    if actor is None or not actor.role.can_moderate:
        raise PermissionDenied

    target = get_object_or_404(SpaceParticipant, pk=participant_id, space=space)
    if target.user_id == user.pk:
        messages.error(request, "You cannot remove yourself from the space.")
        return redirect("spaces:participants", space_id=space.pk)
    target_user: User = target.user
    space_services.leave_space(space=space, user=target_user)
    messages.success(request, f'Removed "{target_user.name}" from space.')
    return redirect("spaces:participants", space_id=space.pk)


@require_POST
@login_required
def participant_role_update(request: HttpRequest, space_id: str, participant_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    actor = space_services.get_participant(space=space, user=user)
    if actor is None or not actor.role.can_set_permissions:
        raise PermissionDenied

    target = get_object_or_404(SpaceParticipant, pk=participant_id, space=space)
    role_id = request.POST.get("role_id")
    role = get_object_or_404(Role, pk=role_id, space=space)
    space_services.update_participant_role(participant=target, role=role)
    messages.success(request, f'Updated role for "{target.user.name}".')
    return redirect("spaces:participants", space_id=space.pk)


# ── Roles & Permissions ──────────────────────────────────────────


@login_required
def space_permissions(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
        raise PermissionDenied

    roles = Role.objects.filter(space=space).annotate(participant_count=Count("participants")).order_by("label")

    role_data = []
    for role in roles:
        perms = [(field, label, getattr(role, field)) for field, label in PERMISSION_LABELS.items()]
        role_data.append(
            {
                "role": role,
                "permissions": perms,
                "participant_count": role.participant_count,
            }
        )

    return render(
        request,
        "spaces/space_permissions.html",
        {"space": space, "role_data": role_data},
    )


@require_POST
@login_required
def role_create(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
        raise PermissionDenied

    label = (request.POST.get("label") or "").strip()
    try:
        space_services.create_role(space=space, label=label)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("spaces:permissions", space_id=space.pk)

    messages.success(request, f'Role "{label}" created.')
    return redirect("spaces:permissions", space_id=space.pk)


@require_POST
@login_required
def role_update(request: HttpRequest, space_id: str, role_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
        raise PermissionDenied

    role = get_object_or_404(Role, pk=role_id, space=space)

    label = (request.POST.get("label") or "").strip()
    permissions = {field: field in request.POST for field in PERMISSION_LABELS}
    try:
        space_services.update_role(role=role, label=label or None, permissions=permissions)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("spaces:permissions", space_id=space.pk)

    messages.success(request, f'Role "{role.label}" updated.')
    return redirect("spaces:permissions", space_id=space.pk)


@require_POST
@login_required
def role_delete(request: HttpRequest, space_id: str, role_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
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
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = space_services.get_participant(space=space, user=user)
    if participant is None or not participant.role.can_set_permissions:
        raise PermissionDenied

    role = get_object_or_404(Role, pk=role_id, space=space)
    space_services.set_default_role(space=space, role=role)
    messages.success(request, f'"{role.label}" is now the default role for new members.')
    return redirect("spaces:permissions", space_id=space.pk)


# ── Participant management ────────────────────────────────────────


@require_POST
@login_required
def participant_add(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    actor = space_services.get_participant(space=space, user=user)
    if actor is None or not actor.role.can_moderate:
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

    SpaceParticipant.objects.create(space=space, user=target_user, role=role)
    messages.success(request, f'Added "{target_user.name or target_user.email}".')
    return redirect("spaces:participants", space_id=space.pk)


# ── Invite links ──────────────────────────────────────────────────


@require_POST
@login_required
def invite_create(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    actor = space_services.get_participant(space=space, user=user)
    if actor is None or not actor.role.can_moderate:
        raise PermissionDenied

    role_id = request.POST.get("role_id")
    role = get_object_or_404(Role, pk=role_id, space=space) if role_id else space.default_role
    if role is None:
        messages.error(request, "No role selected and no default role configured.")
        return redirect("spaces:participants", space_id=space.pk)

    SpaceInvite.objects.create(space=space, role=role, created_by=user)
    messages.success(request, "Invite link created.")
    return redirect("spaces:participants", space_id=space.pk)


@require_POST
@login_required
def invite_delete(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    actor = space_services.get_participant(space=space, user=user)
    if actor is None or not actor.role.can_moderate:
        raise PermissionDenied

    invite = get_object_or_404(SpaceInvite, pk=invite_id, space=space)
    invite.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    messages.success(request, "Invite link deleted.")
    return redirect("spaces:participants", space_id=space.pk)


@login_required
def invite_accept(request: HttpRequest, space_id: str, invite_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    invite = get_object_or_404(SpaceInvite, pk=invite_id, space=space)
    user = get_user(request)

    if SpaceParticipant.objects.filter(space=space, user=user).exists():
        messages.info(request, "You are already a participant.")
        return redirect("spaces:detail", space_id=space.pk)

    if space.lifecycle != Space.Lifecycle.OPEN:
        messages.error(request, "This space is not open for joining.")
        return redirect("spaces:list")

    if request.method == "POST":
        try:
            space_services.join_space(space=space, user=user, role=invite.role)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("spaces:list")
        messages.success(request, f'Joined "{space.title}".')
        return redirect("spaces:detail", space_id=space.pk)

    return render(request, "spaces/invite_accept.html", {"space": space, "invite": invite})
