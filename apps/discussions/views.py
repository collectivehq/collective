from __future__ import annotations

import json
import uuid as uuid_mod
from dataclasses import dataclass
from typing import TypedDict, cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.discussions import services as discussion_services
from apps.discussions.constants import VALID_RESOLUTION_TYPES
from apps.discussions.models import Discussion
from apps.discussions.permissions import can_reorganise, can_resolve_discussion, can_shape_tree
from apps.discussions.presenters import (
    DiscussionDetailInlineChild,
    DiscussionDetailLink,
    DiscussionDetailPost,
    DiscussionDetailSubDiscussion,
)
from apps.opinions.services import (
    get_opinion_counts,
    get_opinion_counts_batch,
    get_user_opinion_type,
)
from apps.posts.models import Link, Post
from apps.posts.permissions import can_edit_post, can_post_to_discussion, can_view_post
from apps.reactions.services import get_reaction_counts_batch, get_user_reactions_batch
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import can_moderate, can_view_space
from apps.spaces.request_context import get_active_space_request_context, get_space_request_context
from apps.subscriptions.subscription_services import is_subscribed
from apps.users.models import User

type InlineChild = Post | Link


def _inline_children_for(discussion: Discussion) -> list[InlineChild]:
    return [
        child for child in discussion_services.get_discussion_children(discussion) if child.is_post or child.is_link
    ]


def _get_link_previews(inline_children: list[InlineChild]) -> dict[uuid_mod.UUID, Post]:
    """Fetch first post previews for linked discussions."""
    return discussion_services.get_link_previews(inline_children)


def _get_author_role_map(space: Space, children: list[InlineChild]) -> dict[uuid_mod.UUID, str]:
    """Build a mapping of author user_id to role label for post author badges."""
    post_author_ids = {
        post.author_id for post in (cast(Post, child) for child in children if child.is_post) if post.author_id
    }
    if not post_author_ids:
        return {}
    participants = SpaceParticipant.objects.filter(space=space, user_id__in=post_author_ids).select_related("role")
    return {participant.user_id: participant.role.label for participant in participants}


@dataclass(slots=True)
class ReactionDisplayData:
    user_reaction_type: str
    reaction_counts: dict[str, int]


def _get_user_reactions(
    inline_children: list[InlineChild], user: User | None
) -> dict[uuid_mod.UUID, ReactionDisplayData]:
    """Batch-fetch user reaction types and reaction counts for posts."""
    post_ids = [child.pk for child in inline_children if child.is_post]
    if not post_ids:
        return {}
    reaction_map = get_user_reactions_batch(user=user, post_ids=post_ids) if user is not None else {}
    counts_map = get_reaction_counts_batch(post_ids)
    return {
        post_id: ReactionDisplayData(
            user_reaction_type=reaction_map.get(post_id, ""),
            reaction_counts=counts_map.get(post_id, {}),
        )
        for post_id in post_ids
    }


class TreeNodeEntry(TypedDict):
    node: Discussion
    resolution: str
    opinions: dict[str, int]
    children: list[TreeNodeEntry]


def _build_nested_tree(
    tree_nodes: list[Discussion], root_id: uuid_mod.UUID | str, *, include_opinions: bool = True
) -> list[TreeNodeEntry]:
    """Convert flat DFS-ordered discussion nodes into a nested tree structure."""
    del root_id
    node_ids = [node.pk for node in tree_nodes]
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
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_view_space(user, space, participant=participant):
        raise PermissionDenied
    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


@login_required
def discussion_detail(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_view_space(user, space, participant=participant):
        raise PermissionDenied

    all_children = discussion_services.get_discussion_children(discussion)
    inline_children = [cast(InlineChild, child) for child in all_children if child.is_post or child.is_link]
    inline_children = [
        child
        for child in inline_children
        if not child.is_post or can_view_post(user, cast(Post, child), participant=participant)
    ]
    link_target_ids = {cast(Link, child).target_id for child in all_children if child.is_link}
    raw_sub_discussions = [
        cast(Discussion, child) for child in all_children if child.is_discussion and child.pk not in link_target_ids
    ]
    active_child_counts = discussion_services.get_active_child_counts(raw_sub_discussions)
    sub_discussions = [
        DiscussionDetailSubDiscussion(
            discussion=sub_discussion,
            active_child_count=active_child_counts.get(sub_discussion.pk, 0),
        )
        for sub_discussion in raw_sub_discussions
    ]

    link_previews = _get_link_previews(inline_children)

    opinions = get_opinion_counts(discussion)
    user_opinion = get_user_opinion_type(user=user, discussion=discussion) if participant is not None else None

    user_can_post = can_post_to_discussion(user, discussion, participant=participant)
    user_can_resolve = can_resolve_discussion(user, discussion, participant=participant)
    user_can_shape = can_shape_tree(user, space, participant=participant)
    user_can_moderate = can_moderate(user, space, participant=participant)
    user_can_reorganise = can_reorganise(user, space, participant=participant)
    user_is_subscribed = is_subscribed(user=user, discussion=discussion) if participant is not None else False

    all_discussions = discussion_services.get_all_discussions_with_levels(space) if user_can_reorganise else []

    role_map = _get_author_role_map(space, inline_children)
    reaction_data = _get_user_reactions(inline_children, user if participant is not None else None)
    inline_child_cards: list[DiscussionDetailInlineChild] = []
    for child in inline_children:
        if child.is_post:
            post = cast(Post, child)
            post_reactions = reaction_data.get(
                post.pk,
                ReactionDisplayData(user_reaction_type="", reaction_counts={}),
            )
            inline_child_cards.append(
                DiscussionDetailPost(
                    post=post,
                    user_can_edit=can_edit_post(user, post, space, participant=participant),
                    user_reaction_type=post_reactions.user_reaction_type,
                    reaction_counts=post_reactions.reaction_counts,
                )
            )
            continue

        link = cast(Link, child)
        inline_child_cards.append(
            DiscussionDetailLink(
                link=link,
                link_preview_post=link_previews.get(link.target_id),
            )
        )

    return render(
        request,
        "discussions/discussion_detail.html",
        {
            "space": space,
            "discussion": discussion,
            "participant": participant,
            "inline_children": inline_child_cards,
            "sub_discussions": sub_discussions,
            "resolution": discussion.resolution_type,
            "opinions": opinions,
            "user_opinion": user_opinion,
            "can_post": user_can_post,
            "can_resolve": user_can_resolve,
            "can_shape": user_can_shape,
            "can_moderate": user_can_moderate,
            "can_reorganise": user_can_reorganise,
            "is_subscribed": user_is_subscribed,
            "all_discussions": all_discussions,
            "role_map": role_map,
        },
    )


@require_POST
@login_required
def discussion_edit(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    label = request.POST.get("label", "").strip()
    if not label:
        return HttpResponse("Label is required", status=400)
    if len(label) > 255:
        return HttpResponse("Label is too long", status=400)

    discussion_services.update_discussion(discussion=discussion, label=label)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_create(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    parent_id = request.POST.get("parent_id")
    label = request.POST.get("label", "").strip()
    if not label:
        return HttpResponse("Label is required", status=400)
    if len(label) > 255:
        return HttpResponse("Label is too long", status=400)
    parent = get_object_or_404(
        Discussion,
        pk=parent_id,
        space=space,
        deleted_at__isnull=True,
    )
    new_discussion = discussion_services.create_child_discussion(parent=parent, space=space, label=label)

    response = _render_tree(request, space, user=user, can_shape=True)
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(new_discussion.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def discussion_resolve(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_resolve_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    resolution = request.POST.get("resolution", "")
    if resolution not in VALID_RESOLUTION_TYPES:
        return HttpResponse("Invalid resolution type", status=400)

    discussion_services.resolve_discussion(discussion=discussion, resolution_type=resolution, resolved_by=user)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_reopen(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_resolve_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    discussion_services.reopen_discussion(discussion=discussion, actor=user)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_delete(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    if discussion.is_root():
        return HttpResponse("Cannot delete the root discussion", status=403)

    parent = discussion.get_parent()
    discussion_services.delete_discussion(discussion=discussion)
    response = _render_tree(request, space, user=user, can_shape=True)
    if parent:
        response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(parent.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def discussion_children_reorder(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    node_ids = request.POST.getlist("node_ids")
    if not node_ids:
        return HttpResponse("No items provided", status=400)

    inline_children = _inline_children_for(discussion)
    valid_ids = {child.pk for child in inline_children if str(child.pk) in node_ids}
    if len(valid_ids) != len(node_ids):
        return HttpResponse("Invalid node IDs", status=400)

    inline_child_count = len(inline_children)
    if len(node_ids) != inline_child_count:
        return HttpResponse("All inline children must be included in reorder", status=400)

    discussion_services.reorder_children(node_ids=node_ids)
    return discussion_detail(request, space_id, discussion_id)


@require_POST
@login_required
def discussion_move(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    new_parent_id = request.POST.get("new_parent_id")
    new_parent = get_object_or_404(
        Discussion,
        pk=new_parent_id,
        space=space,
        deleted_at__isnull=True,
    )
    discussion_services.move_discussion(discussion=discussion, new_parent=new_parent)

    return _render_tree(request, space, user=user, can_shape=True)


@require_POST
@login_required
def tree_reorder(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_shape_tree(user, space, participant=participant):
        raise PermissionDenied

    node_ids = request.POST.getlist("node_ids")
    if not node_ids:
        return HttpResponse("No discussions provided", status=400)

    valid_ids = set(
        Discussion.objects.filter(pk__in=node_ids, space=space, deleted_at__isnull=True).values_list("pk", flat=True)
    )
    if len(valid_ids) != len(node_ids):
        return HttpResponse("Invalid node IDs", status=400)

    nodes = Discussion.objects.filter(pk__in=node_ids).only("path", "depth")
    parents = {node.path[: Discussion.steplen * (node.depth - 1)] for node in nodes}
    if len(parents) != 1:
        return HttpResponse("All nodes must be siblings", status=400)

    discussion_services.reorder_children(node_ids=node_ids)
    return _render_tree(request, space, user=user, can_shape=True)


@require_POST
@login_required
def discussion_merge(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    source = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    target_id = request.POST.get("target_id")
    target = get_object_or_404(
        Discussion,
        pk=target_id,
        space=space,
        deleted_at__isnull=True,
    )
    discussion_services.merge_discussions(source=source, target=target)

    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


@require_POST
@login_required
def discussion_split(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_active_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    discussion = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    child_ids = request.POST.getlist("child_ids")
    if not child_ids:
        return HttpResponse("No items selected", status=400)

    try:
        discussion_services.split_discussion(discussion=discussion, child_ids=child_ids)
    except ValueError as error:
        return HttpResponse(str(error), status=400)

    can_shape = can_shape_tree(user, space, participant=participant)
    return _render_tree(request, space, user=user, can_shape=can_shape)


def _render_tree(request: HttpRequest, space: Space, *, user: User, can_shape: bool) -> HttpResponse:
    root = space.root_discussion
    tree_nodes = discussion_services.get_ordered_discussions(root) if root else []
    nested_nodes = _build_nested_tree(tree_nodes, root.pk if root else "")
    return render(
        request,
        "discussions/tree.html",
        {"nodes": nested_nodes, "space": space, "root_discussion": root, "can_shape": can_shape},
    )


__all__ = [
    "discussion_children_reorder",
    "discussion_create",
    "discussion_delete",
    "discussion_detail",
    "discussion_edit",
    "discussion_merge",
    "discussion_move",
    "discussion_reopen",
    "discussion_resolve",
    "discussion_split",
    "discussion_tree",
    "tree_reorder",
]
