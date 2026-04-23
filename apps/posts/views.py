from __future__ import annotations

import json
import uuid as uuid_mod
from typing import IO, cast

import filetype
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.views.decorators.http import require_GET, require_POST

from apps.discussions import services as discussion_services
from apps.discussions.constants import VALID_RESOLUTION_TYPES
from apps.discussions.models import Discussion
from apps.discussions.permissions import can_reopen_discussion, can_reorganise, can_resolve_discussion
from apps.discussions.views import discussion_detail
from apps.posts import services as post_services
from apps.posts.models import Link, Post, PostRevision
from apps.posts.permissions import (
    can_create_draft,
    can_delete_post,
    can_post_to_discussion,
    can_promote_post,
    can_upload_images,
    can_view_history,
    can_view_post,
    get_post_edit_denial_reason,
)
from apps.spaces.models import Space
from apps.spaces.permissions import can_moderate_content
from apps.spaces.request_context import get_space_request_context

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
EXT_FOR_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


def _read_limited(file: IO[bytes], max_bytes: int) -> bytes | None:
    """Read up to max_bytes from a file-like object.

    Reads one extra byte past the limit so that an exactly-at-limit file
    is accepted while an oversized one is detected without buffering it
    entirely. Returns None if the stream exceeds max_bytes.
    """
    data = file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return None
    return data


def _public_media_url(path: str) -> str:
    """Return the public media URL for a stored file path."""
    return f"{settings.MEDIA_URL.rstrip('/')}/{path.lstrip('/')}"


def _get_content_item(pk: str, space: Space) -> Post | Link | None:
    post = Post.objects.filter(pk=pk, discussion__space=space, deleted_at__isnull=True).first()
    if post is not None:
        return post
    return Link.objects.filter(pk=pk, discussion__space=space, deleted_at__isnull=True).first()


def _get_content_items(item_ids: list[str], space: Space) -> list[Post | Link]:
    items = [_get_content_item(item_id, space) for item_id in item_ids]
    if any(item is None for item in items):
        raise Http404
    return [cast(Post | Link, item) for item in items]


def _move_item_card_label(item: Post | Link) -> str:
    if item.is_post:
        return Truncator(strip_tags(cast(Post, item).content).strip() or "Post").chars(40)
    return cast(Link, item).target.label or "Link"


def _parse_target_order_ids(raw_ids: list[str]) -> list[uuid_mod.UUID] | None:
    if not raw_ids:
        return None

    parsed_ids: list[uuid_mod.UUID] = []
    for raw_id in raw_ids:
        try:
            parsed_ids.append(uuid_mod.UUID(raw_id))
        except ValueError as error:
            raise Http404 from error
    return parsed_ids


def _render_discussion_items_move_positions(
    request: HttpRequest,
    *,
    space_id: str,
    item_ids: list[str],
) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    if not item_ids:
        return HttpResponse("No items selected", status=400)

    items = _get_content_items(item_ids, space)
    for item in items:
        if item.is_post and not can_view_post(user, cast(Post, item), participant=participant):
            raise PermissionDenied

    discussion_id = request.GET.get("discussion_id")
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    excluded_ids = {str(item.pk) for item in items}
    children = [
        child
        for child in discussion_services.get_discussion_children(discussion)
        if (child.is_post or child.is_link)
        and str(child.pk) not in excluded_ids
        and (not child.is_post or can_view_post(user, cast(Post, child), participant=participant))
    ]
    return render(
        request,
        "posts/move_post_positions.html",
        {
            "children": children,
            "discussion": discussion,
            "moved_item_token": str(items[0].pk) if len(items) == 1 else "batch",
            "moved_items": [{"id": str(item.pk), "label": _move_item_card_label(item)} for item in items],
        },
    )


def _perform_discussion_items_move(
    request: HttpRequest,
    *,
    space_id: str,
    space: Space,
    items: list[Post | Link],
) -> HttpResponse:
    target_id = request.POST.get("target_discussion_id")
    target = get_object_or_404(
        Discussion,
        pk=target_id,
        space=space,
        deleted_at__isnull=True,
    )
    try:
        position = int(request.POST.get("position", -1))
    except TypeError, ValueError:
        position = -1
    target_order_ids = _parse_target_order_ids(request.POST.getlist("ordered_target_ids"))

    post_services.move_discussion_items(
        items=items,
        target_discussion=target,
        position=position,
        target_order_ids=target_order_ids,
    )

    response = discussion_detail(request, space_id, str(target.pk))
    response["HX-Trigger"] = json.dumps(
        {
            "selectDiscussion": {"id": str(target.pk), "spaceId": str(space.pk)},
            "refreshTree": {},
        }
    )
    return response


@require_POST
@login_required
def post_create(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    content = request.POST.get("content", "").strip()
    if not content:
        return HttpResponse("Content is required", status=400)

    save_as_draft = "save_draft" in request.POST
    if save_as_draft:
        if not can_create_draft(user, space, participant=participant):
            raise PermissionDenied
    elif not can_post_to_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    resolution = request.POST.get("resolution", "")
    if resolution and resolution not in VALID_RESOLUTION_TYPES:
        resolution = ""
    if resolution and (save_as_draft or not can_resolve_discussion(user, discussion, participant=participant)):
        resolution = ""

    try:
        with transaction.atomic():
            post_services.create_post(
                discussion=discussion,
                author=user,
                content=content,
                is_draft=save_as_draft,
                participant=participant,
            )

            if not save_as_draft and resolution:
                discussion_services.resolve_discussion(
                    discussion=discussion, resolution_type=resolution, resolved_by=user
                )
            elif (
                not save_as_draft
                and discussion.resolution_type
                and can_reopen_discussion(user, discussion, participant=participant)
            ):
                discussion_services.reopen_discussion(discussion=discussion, actor=user)
    except ValueError as error:
        return HttpResponse(str(error), status=400)

    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def post_edit(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)
    if not can_view_post(user, post, participant=participant):
        raise PermissionDenied
    edit_error = get_post_edit_denial_reason(user, post, space, participant=participant)
    if edit_error is not None:
        if edit_error == "Permission denied":
            raise PermissionDenied
        return HttpResponse(edit_error, status=403)

    content = request.POST.get("content", "").strip()
    if not content:
        return HttpResponse("Content is required", status=400)

    parent = post.get_parent()
    publish_draft = post.is_draft and "publish" in request.POST
    keep_as_draft = post.is_draft and not publish_draft
    if publish_draft and not can_post_to_discussion(user, parent, participant=participant):
        raise PermissionDenied

    with transaction.atomic():
        post_services.update_post(
            post=post,
            content=content,
            is_draft=keep_as_draft,
            actor=user,
        )
        if publish_draft and parent.resolution_type and can_reopen_discussion(user, parent, participant=participant):
            discussion_services.reopen_discussion(discussion=parent, actor=user)

    return discussion_detail(request, space_id, str(parent.pk))


@require_POST
@login_required
def post_publish(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)
    if not can_view_post(user, post, participant=participant):
        raise PermissionDenied
    edit_error = get_post_edit_denial_reason(user, post, space, participant=participant)
    if edit_error is not None:
        if edit_error == "Permission denied":
            raise PermissionDenied
        return HttpResponse(edit_error, status=403)

    if not post.is_draft:
        return HttpResponse("Post is already published", status=400)

    parent = post.get_parent()
    if not can_post_to_discussion(user, parent, participant=participant):
        raise PermissionDenied

    with transaction.atomic():
        post_services.update_post(
            post=post,
            content=post.content,
            is_draft=False,
            actor=user,
        )
        if parent.resolution_type and can_reopen_discussion(user, parent, participant=participant):
            discussion_services.reopen_discussion(discussion=parent, actor=user)

    response = discussion_detail(request, space_id, str(parent.pk))
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def post_delete(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)
    if not can_view_post(user, post, participant=participant):
        raise PermissionDenied
    if not can_delete_post(user, post, space, participant=participant):
        raise PermissionDenied

    parent = post.get_parent()
    post_services.delete_post(post=post)
    response = discussion_detail(request, space_id, str(parent.pk))
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def link_delete(request: HttpRequest, space_id: str, link_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    link = get_object_or_404(Link, pk=link_id, discussion__space=space, deleted_at__isnull=True)
    if not can_moderate_content(user, space, participant=participant):
        raise PermissionDenied

    parent = link.get_parent()
    post_services.delete_link(link=link)
    response = discussion_detail(request, space_id, str(parent.pk))
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_item_move(request: HttpRequest, space_id: str, item_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant

    item = _get_content_item(item_id, space)
    if item is None:
        raise Http404

    if item.is_post and not can_view_post(user, cast(Post, item), participant=participant):
        raise PermissionDenied
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    return _perform_discussion_items_move(request, space_id=space_id, space=space, items=[item])


@require_POST
@login_required
def discussion_items_move(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    item_ids = request.POST.getlist("item_ids")
    if not item_ids:
        return HttpResponse("No items selected", status=400)

    items = _get_content_items(item_ids, space)
    for item in items:
        if item.is_post and not can_view_post(user, cast(Post, item), participant=participant):
            raise PermissionDenied

    return _perform_discussion_items_move(request, space_id=space_id, space=space, items=items)


@require_GET
@login_required
def discussion_items_move_positions(request: HttpRequest, space_id: str) -> HttpResponse:
    item_ids = request.GET.getlist("item_ids")
    return _render_discussion_items_move_positions(request, space_id=space_id, item_ids=item_ids)


@require_POST
@login_required
def post_promote(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)
    if not can_view_post(user, post, participant=participant):
        raise PermissionDenied
    if not can_promote_post(user, space, participant=participant):
        raise PermissionDenied
    if post.is_draft:
        return HttpResponse("Draft posts cannot be promoted", status=400)

    parent = post.get_parent()
    new_discussion, _link = post_services.promote_post_to_discussion(post=post)

    response = discussion_detail(request, space_id, str(parent.pk))
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(new_discussion.pk), "spaceId": str(space.pk)}})
    return response


@require_GET
@login_required
def post_revisions(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if participant is None:
        raise PermissionDenied
    post = get_object_or_404(Post, pk=post_id, discussion__space=space, deleted_at__isnull=True)
    if not can_view_post(user, post, participant=participant):
        raise PermissionDenied
    if not can_view_history(user, space, participant=participant):
        raise PermissionDenied
    revisions = PostRevision.objects.filter(post=post).order_by("-created_at") if not post.is_draft else []
    return render(request, "posts/post_revisions.html", {"post": post, "revisions": revisions, "space": space})


@require_POST
@login_required
def image_upload(request: HttpRequest, space_id: str) -> HttpResponse:
    """Handle image uploads from TinyMCE editor. Returns JSON with location."""
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if participant is None:
        raise PermissionDenied
    if not can_upload_images(user, space, participant=participant):
        raise PermissionDenied

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file provided"}, status=400)

    data = _read_limited(uploaded, MAX_UPLOAD_SIZE)
    if data is None:
        return JsonResponse({"error": "File too large (max 5MB)"}, status=400)

    detected = filetype.guess(data)
    if detected is None or detected.mime not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({"error": "Invalid image file"}, status=400)

    ext = EXT_FOR_TYPE[detected.mime]
    filename = f"uploads/{space_id}/{uuid_mod.uuid4().hex}.{ext}"
    saved_path = default_storage.save(filename, ContentFile(data))
    url = _public_media_url(saved_path)
    return JsonResponse({"location": url})


__all__ = [
    "image_upload",
    "link_delete",
    "post_create",
    "post_delete",
    "post_edit",
    "post_promote",
    "post_publish",
    "post_revisions",
    "discussion_item_move",
    "discussion_items_move",
    "discussion_items_move_positions",
]
