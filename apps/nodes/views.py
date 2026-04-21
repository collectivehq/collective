from __future__ import annotations

import json
import uuid as uuid_mod
from typing import IO, TypedDict

import filetype
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.nodes import services as node_services
from apps.nodes.models import Node, PostRevision
from apps.opinions.services import (
    get_opinion_counts,
    get_opinion_counts_batch,
    get_participant_opinion_type,
    get_participant_reactions_batch,
    get_reaction_counts_batch,
)
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import (
    can_edit_post,
    can_moderate,
    can_post_to_discussion,
    can_react,
    can_reorganise,
    can_resolve_discussion,
    can_shape_tree,
    can_view_space,
)
from apps.spaces.services import get_active_space, get_participant
from apps.subscriptions.services import is_subscribed
from apps.users.models import User
from apps.users.utils import get_user

VALID_RESOLUTION_TYPES = set(dict(Node.ResolutionType.choices))


def _attach_link_previews(inline_children: list[Node]) -> None:
    """Attach first post of link targets to link nodes."""
    link_previews = node_services.get_link_previews(inline_children)
    for child in inline_children:
        if child.is_link and child.target_id in link_previews:
            child.link_preview_post = link_previews[child.target_id]
        elif child.is_link:
            child.link_preview_post = None


def _get_author_role_map(space: Space, children: list[Node]) -> dict[uuid_mod.UUID, str]:
    """Build a mapping of author user_id → role label for post author badges."""
    post_author_ids = {c.author_id for c in children if c.is_post and c.author_id}
    if not post_author_ids:
        return {}
    participants_qs = SpaceParticipant.objects.filter(space=space, user_id__in=post_author_ids).select_related("role")
    return {p.user_id: p.role.label for p in participants_qs}


def _attach_user_reactions(inline_children: list[Node], participant: SpaceParticipant | None) -> None:
    """Batch-fetch and attach user reaction types and reaction counts to posts."""
    post_ids = [c.pk for c in inline_children if c.is_post]
    if not post_ids:
        return
    reaction_map = (
        get_participant_reactions_batch(participant=participant, post_ids=post_ids) if participant is not None else {}
    )
    counts_map = get_reaction_counts_batch(post_ids)
    for child in inline_children:
        if child.is_post:
            child.user_reaction_type = reaction_map.get(child.pk, "")
            child.reaction_counts = counts_map.get(child.pk, {})


class TreeNodeEntry(TypedDict):
    node: Node
    resolution: str
    opinions: dict[str, int]
    children: list[TreeNodeEntry]


def _build_nested_tree(
    tree_nodes: list[Node], root_id: uuid_mod.UUID | str, *, include_opinions: bool = True
) -> list[TreeNodeEntry]:
    """Convert flat DFS-ordered discussion nodes into a nested tree structure.

    Nodes arrive in DFS order, so when we encounter a node at depth D,
    we pop the stack back to the entry whose depth is less than D —
    that entry's children list becomes the insertion point.
    """
    node_ids = [n.pk for n in tree_nodes]
    opinion_counts = get_opinion_counts_batch(node_ids) if include_opinions else {}

    root_entries: list[TreeNodeEntry] = []
    stack: list[tuple[int, list[TreeNodeEntry]]] = [(0, root_entries)]

    for node in tree_nodes:
        entry = TreeNodeEntry(
            node=node,
            resolution=node.resolution_type,
            opinions=opinion_counts.get(node.pk, {}),
            children=[],
        )
        while stack[-1][0] >= node.depth:
            stack.pop()
        stack[-1][1].append(entry)
        stack.append((node.depth, entry["children"]))

    return root_entries


@login_required
def discussion_tree(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if not can_view_space(user, space, participant=participant):
        raise PermissionDenied
    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


@login_required
def discussion_detail(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if not can_view_space(user, space, participant=participant):
        raise PermissionDenied

    # Get all children (posts, links, discussions) in order
    all_children = node_services.get_discussion_children(discussion)

    # Separate by type for template rendering
    inline_children = [c for c in all_children if c.node_type in (Node.NodeType.POST, Node.NodeType.LINK)]
    # Sub-discussions: child discussions that are NOT link-backed
    link_target_ids = {c.target_id for c in all_children if c.is_link}
    sub_discussions = [c for c in all_children if c.is_discussion and c.pk not in link_target_ids]

    # Prefetch first post for each link target to show preview
    _attach_link_previews(inline_children)

    opinions = get_opinion_counts(discussion)
    user_opinion = (
        get_participant_opinion_type(participant=participant, node=discussion) if participant is not None else None
    )

    user_can_post = can_post_to_discussion(user, discussion, participant=participant)
    user_can_resolve = can_resolve_discussion(user, discussion, participant=participant)
    user_can_shape = can_shape_tree(user, space, participant=participant)
    user_can_moderate = can_moderate(user, space, participant=participant)
    user_can_reorganise = can_reorganise(user, space, participant=participant)
    user_is_subscribed = is_subscribed(participant=participant, node=discussion) if participant is not None else False

    all_discussions: list[Node] = []
    if user_can_shape or user_can_moderate or user_can_reorganise:
        all_discussions = node_services.get_all_discussions_with_levels(space)

    role_map = _get_author_role_map(space, all_children)
    # Attaches both user_reaction_type and reaction_counts to each post node
    _attach_user_reactions(inline_children, participant)

    # Pre-compute per-post edit permission
    for child in inline_children:
        if child.is_post:
            child.user_can_edit = can_edit_post(user, child, space, participant=participant) is True

    user_can_react = (
        can_react(user, discussion, participant=participant) if participant is not None and space.is_active else False
    )

    return render(
        request,
        "nodes/discussion_detail.html",
        {
            "space": space,
            "discussion": discussion,
            "participant": participant,
            "inline_children": inline_children,
            "sub_discussions": sub_discussions,
            "resolution": discussion.resolution_type,
            "opinions": opinions,
            "user_opinion": user_opinion,
            "can_post": user_can_post,
            "can_resolve": user_can_resolve,
            "can_shape": user_can_shape,
            "can_moderate": user_can_moderate,
            "can_reorganise": user_can_reorganise,
            "can_react": user_can_react,
            "is_subscribed": user_is_subscribed,
            "all_discussions": all_discussions,
            "role_map": role_map,
        },
    )


@require_POST
@login_required
def discussion_edit(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    label = request.POST.get("label", "").strip()
    if not label:
        return HttpResponse("Label is required", status=400)
    if len(label) > 255:
        return HttpResponse("Label is too long", status=400)

    node_services.update_discussion(discussion=discussion, label=label)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_create(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    parent_id = request.POST.get("parent_id")
    label = request.POST.get("label", "").strip()
    if not label:
        return HttpResponse("Label is required", status=400)
    if len(label) > 255:
        return HttpResponse("Label is too long", status=400)
    parent = get_object_or_404(
        Node, pk=parent_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    new_discussion = node_services.create_child_discussion(parent=parent, space=space, label=label)

    response = _render_tree(request, space, user=user, can_shape=True)
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(new_discussion.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def post_create(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_post_to_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    content = request.POST.get("content", "").strip()
    if not content:
        return HttpResponse("Content is required", status=400)

    # Handle resolution on the discussion
    resolution = request.POST.get("resolution", "")
    if resolution and resolution not in VALID_RESOLUTION_TYPES:
        resolution = ""
    if resolution and not can_resolve_discussion(user, discussion, participant=participant):
        resolution = ""

    reopens = request.POST.get("reopens_discussion", "") == "true"
    if discussion.resolution_type and not reopens and not resolution:
        return HttpResponse("This discussion is resolved. Check 'I want to reopen' to post.", status=400)

    try:
        with transaction.atomic():
            node_services.create_post(
                discussion=discussion,
                author=user,
                content=content,
                reopens_discussion=reopens,
            )

            # Apply resolution/reopen to discussion
            if resolution:
                node_services.resolve_discussion(discussion=discussion, resolution_type=resolution, resolved_by=user)
            elif reopens and discussion.resolution_type:
                node_services.reopen_discussion(discussion=discussion)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def post_edit(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    edit_check = can_edit_post(user, post, space, participant=participant)
    if edit_check is not True:
        if edit_check == "Permission denied":
            raise PermissionDenied
        return HttpResponse(edit_check, status=403)

    content = request.POST.get("content", "").strip()
    if not content:
        return HttpResponse("Content is required", status=400)

    node_services.update_post(post=post, content=content)

    parent = post.get_parent()
    return discussion_detail(request, space_id, str(parent.pk) if parent else str(post.pk))


@require_POST
@login_required
def discussion_resolve(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_resolve_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    resolution = request.POST.get("resolution", "")
    if resolution not in VALID_RESOLUTION_TYPES:
        return HttpResponse("Invalid resolution type", status=400)

    node_services.resolve_discussion(discussion=discussion, resolution_type=resolution, resolved_by=user)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_reopen(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_resolve_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    node_services.reopen_discussion(discussion=discussion)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_delete(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    if discussion.is_root():
        return HttpResponse("Cannot delete the root discussion", status=403)

    parent = discussion.get_parent()
    node_services.soft_delete_node(node=discussion)
    response = _render_tree(request, space, user=user, can_shape=True)
    if parent:
        response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(parent.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def post_delete(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if post.author != user and not can_moderate(user, space, participant=participant):
        raise PermissionDenied

    parent = post.get_parent()
    node_services.soft_delete_node(node=post)
    response = discussion_detail(request, space_id, str(parent.pk) if parent else post_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def link_delete(request: HttpRequest, space_id: str, link_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    link = get_object_or_404(Node, pk=link_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.LINK)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_moderate(user, space, participant=participant):
        raise PermissionDenied

    parent = link.get_parent()
    node_services.soft_delete_node(node=link)
    response = discussion_detail(request, space_id, str(parent.pk) if parent else link_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def post_move(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    target_id = request.POST.get("target_discussion_id")
    target = get_object_or_404(
        Node, pk=target_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    try:
        position = int(request.POST.get("position", -1))
    except (TypeError, ValueError):
        position = -1
    node_services.move_post(post=post, target_discussion=target, position=position)

    parent = post.get_parent()
    response = discussion_detail(request, space_id, str(parent.pk) if parent else str(target.pk))
    response["HX-Trigger"] = "refreshTree"
    return response


@require_GET
@login_required
def post_move_positions(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    """Return sortable post list for the move-post dialog (step 2)."""
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    discussion_id = request.GET.get("discussion_id")
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    children = list(
        discussion.get_children()
        .filter(deleted_at__isnull=True, node_type__in=[Node.NodeType.POST, Node.NodeType.LINK])
        .exclude(pk=post_id)
        .select_related("author")
        .order_by("sequence_index", "created_at")
    )
    # Append the moved post at the bottom
    children.append(post)
    return render(
        request,
        "nodes/move_post_positions.html",
        {"children": children, "discussion": discussion, "moved_post_id": str(post.pk)},
    )


@require_POST
@login_required
def post_promote(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    """Promote a Post to a Discussion."""
    space = get_active_space(space_id)
    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    parent = post.get_parent()
    new_discussion, _link = node_services.promote_post(post=post)

    response = discussion_detail(request, space_id, str(parent.pk) if parent else str(post.pk))
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(new_discussion.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def discussion_children_reorder(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    node_ids = request.POST.getlist("node_ids")
    if not node_ids:
        return HttpResponse("No items provided", status=400)

    valid_ids = set(
        discussion.get_children()
        .filter(pk__in=node_ids, deleted_at__isnull=True, node_type__in=[Node.NodeType.POST, Node.NodeType.LINK])
        .values_list("pk", flat=True)
    )
    if len(valid_ids) != len(node_ids):
        return HttpResponse("Invalid node IDs", status=400)

    # Ensure all inline children (posts + links) are included
    inline_child_count = (
        discussion.get_children()
        .filter(deleted_at__isnull=True, node_type__in=[Node.NodeType.POST, Node.NodeType.LINK])
        .count()
    )
    if len(node_ids) != inline_child_count:
        return HttpResponse("All inline children must be included in reorder", status=400)

    node_services.reorder_children(node_ids=node_ids)
    return discussion_detail(request, space_id, discussion_id)


@require_POST
@login_required
def discussion_move(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    new_parent_id = request.POST.get("new_parent_id")
    new_parent = get_object_or_404(
        Node, pk=new_parent_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    node_services.move_discussion(discussion=discussion, new_parent=new_parent)

    return _render_tree(request, space, user=user, can_shape=True)


@require_POST
@login_required
def tree_reorder(request: HttpRequest, space_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    node_ids = request.POST.getlist("node_ids")
    if not node_ids:
        return HttpResponse("No discussions provided", status=400)

    valid_ids = set(
        Node.objects.filter(pk__in=node_ids, space=space, deleted_at__isnull=True).values_list("pk", flat=True)
    )
    if len(valid_ids) != len(node_ids):
        return HttpResponse("Invalid node IDs", status=400)

    # Validate all nodes share the same parent
    nodes = Node.objects.filter(pk__in=node_ids).only("path", "depth")
    parents = {n.path[: Node.steplen * (n.depth - 1)] for n in nodes}
    if len(parents) != 1:
        return HttpResponse("All nodes must be siblings", status=400)

    node_services.reorder_children(node_ids=node_ids)
    return _render_tree(request, space, user=user, can_shape=True)


@require_POST
@login_required
def discussion_merge(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    source = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    target_id = request.POST.get("target_id")
    target = get_object_or_404(
        Node, pk=target_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    node_services.merge_discussions(source=source, target=target)

    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


@require_POST
@login_required
def discussion_split(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    space = get_active_space(space_id)
    discussion = get_object_or_404(
        Node, pk=discussion_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
    )
    user = get_user(request)

    participant = get_participant(space=space, user=user)
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    child_ids = request.POST.getlist("child_ids")
    if not child_ids:
        return HttpResponse("No items selected", status=400)

    try:
        node_services.split_discussion(discussion=discussion, child_ids=child_ids)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


def _render_tree(request: HttpRequest, space: Space, *, user: User, can_shape: bool) -> HttpResponse:
    root = space.root_discussion
    tree_nodes = node_services.get_ordered_discussions(root) if root else []
    nested_nodes = _build_nested_tree(tree_nodes, root.pk if root else "")
    return render(
        request,
        "nodes/tree.html",
        {"nodes": nested_nodes, "space": space, "root_discussion": root, "can_shape": can_shape},
    )


@login_required
def post_revisions(request: HttpRequest, space_id: str, post_id: str) -> HttpResponse:
    space = get_object_or_404(Space, pk=space_id, deleted_at__isnull=True)
    user = get_user(request)
    if get_participant(space=space, user=user) is None:
        raise PermissionDenied
    post = get_object_or_404(Node, pk=post_id, space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
    revisions = PostRevision.objects.filter(post=post).order_by("-created_at")
    return render(request, "nodes/post_revisions.html", {"post": post, "revisions": revisions, "space": space})


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


@require_POST
@login_required
def image_upload(request: HttpRequest, space_id: str) -> HttpResponse:
    """Handle image uploads from TinyMCE editor. Returns JSON with location."""
    space = get_active_space(space_id)
    user = get_user(request)
    participant = get_participant(space=space, user=user)
    if participant is None:
        raise PermissionDenied
    if not participant.role.can_post:
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
    url = default_storage.url(saved_path)
    return JsonResponse({"location": url})
