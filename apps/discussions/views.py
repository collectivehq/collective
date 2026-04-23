from __future__ import annotations

import json
import uuid as uuid_mod
from dataclasses import dataclass
from typing import TypedDict, cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.discussions import services as discussion_services
from apps.discussions.constants import VALID_RESOLUTION_TYPES
from apps.discussions.models import Discussion
from apps.discussions.permissions import (
    can_create_discussion,
    can_delete_discussion,
    can_rename_discussion,
    can_reopen_discussion,
    can_reorganise,
    can_resolve_discussion,
    can_restructure,
)
from apps.discussions.presenters import (
    DiscussionDetailInlineChild,
    DiscussionDetailLink,
    DiscussionDetailPost,
    DiscussionDetailSubDiscussion,
)
from apps.opinions.permissions import can_opine
from apps.opinions.services import (
    get_opinion_counts,
    get_opinion_counts_batch,
    get_user_opinion_type,
)
from apps.posts.models import Link, Post, PostRevision
from apps.posts.permissions import (
    can_create_draft,
    can_delete_post,
    can_edit_post,
    can_post_to_discussion,
    can_promote_post,
    can_upload_images,
    can_view_history,
    can_view_post,
)
from apps.reactions.permissions import can_react
from apps.reactions.services import get_reaction_counts_batch, get_user_reactions_batch
from apps.spaces.models import Space, SpaceParticipant
from apps.spaces.permissions import can_moderate_content, can_view_space, get_role_for_user
from apps.spaces.request_context import get_space_request_context
from apps.subscriptions.permissions import can_toggle_subscription
from apps.subscriptions.subscription_services import is_subscribed
from apps.users.models import User

type InlineChild = Post | Link


def _inline_children_for(discussion: Discussion) -> list[InlineChild]:
    return [
        child for child in discussion_services.get_discussion_children(discussion) if child.is_post or child.is_link
    ]


def _visible_posts_queryset(
    *,
    user: User,
    space: Space,
    participant: SpaceParticipant | None,
    discussion_ids: set[uuid_mod.UUID],
) -> QuerySet[Post]:
    role = get_role_for_user(user, space, participant)
    queryset = (
        Post.objects.filter(discussion_id__in=discussion_ids, deleted_at__isnull=True)
        .select_related("created_by")
        .prefetch_related(Prefetch("revisions", queryset=PostRevision.objects.order_by("-created_at")))
    )
    if role is not None and role.can_view_drafts:
        return queryset
    return queryset.filter(Q(is_draft=False) | Q(created_by=user))


def _get_visible_link_previews(
    inline_children: list[InlineChild],
    *,
    user: User,
    space: Space,
    participant: SpaceParticipant | None,
) -> dict[uuid_mod.UUID, Post]:
    link_target_ids = {cast(Link, child).target_id for child in inline_children if child.is_link}
    if not link_target_ids:
        return {}

    first_posts: dict[uuid_mod.UUID, Post] = {}
    for post in _visible_posts_queryset(
        user=user,
        space=space,
        participant=participant,
        discussion_ids=link_target_ids,
    ).order_by("discussion_id", "sequence_index", "created_at"):
        if post.discussion_id not in first_posts:
            first_posts[post.discussion_id] = post
    return first_posts


def _get_visible_active_child_counts(
    discussions: list[Discussion],
    *,
    user: User,
    space: Space,
    participant: SpaceParticipant | None,
) -> dict[uuid_mod.UUID, int]:
    counts = discussion_services.get_active_child_counts(discussions)
    discussion_ids = {discussion.pk for discussion in discussions}
    if not discussion_ids:
        return counts

    role = get_role_for_user(user, space, participant)
    if role is not None and role.can_view_drafts:
        return counts

    hidden_counts = {
        row["discussion_id"]: row["count"]
        for row in (
            Post.objects.filter(discussion_id__in=discussion_ids, deleted_at__isnull=True, is_draft=True)
            .exclude(created_by=user)
            .values("discussion_id")
            .annotate(count=Count("pk"))
        )
    }
    for discussion_id, hidden_count in hidden_counts.items():
        counts[discussion_id] -= hidden_count
    for discussion_id in discussion_ids:
        counts[discussion_id] = max(counts[discussion_id], 0)
    return counts


def _get_author_role_maps(
    space: Space,
    children: list[InlineChild],
) -> tuple[dict[uuid_mod.UUID, str], dict[uuid_mod.UUID, str]]:
    post_author_ids = {
        post.author_id for post in (cast(Post, child) for child in children if child.is_post) if post.author_id
    }
    if not post_author_ids:
        return {}, {}
    participants = SpaceParticipant.objects.filter(space=space, user_id__in=post_author_ids).select_related("role")
    role_map: dict[uuid_mod.UUID, str] = {}
    role_highlight_map: dict[uuid_mod.UUID, str] = {}
    for participant in participants:
        role_map[participant.user_id] = participant.role.label
        if participant.role.post_highlight_color:
            role_highlight_map[participant.user_id] = participant.role.post_highlight_color
    return role_map, role_highlight_map


@dataclass(slots=True)
class ReactionDisplayData:
    user_reaction_type: str
    reaction_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class DiscussionDetailAccess:
    can_post: bool
    can_create_draft: bool
    can_upload_images: bool
    can_resolve: bool
    can_reopen: bool
    can_create_discussion: bool
    can_rename_discussion: bool
    can_delete_discussion: bool
    can_reorganise: bool
    can_view_history: bool
    can_opine: bool
    can_toggle_subscription: bool
    can_moderate_links: bool
    is_subscribed: bool

    @property
    def can_submit_post_form(self) -> bool:
        return self.can_post or self.can_create_draft

    @property
    def has_discussion_menu_actions(self) -> bool:
        return self.can_rename_discussion or self.can_delete_discussion or self.can_toggle_subscription


def _build_discussion_detail_access(
    *,
    user: User,
    space: Space,
    discussion: Discussion,
    participant: SpaceParticipant | None,
) -> DiscussionDetailAccess:
    can_toggle = can_toggle_subscription(user, discussion, participant=participant)
    can_delete = can_delete_discussion(user, space, participant=participant) and not discussion.is_root()
    return DiscussionDetailAccess(
        can_post=can_post_to_discussion(user, discussion, participant=participant),
        can_create_draft=can_create_draft(user, space, participant=participant),
        can_upload_images=can_upload_images(user, space, participant=participant),
        can_resolve=can_resolve_discussion(user, discussion, participant=participant),
        can_reopen=can_reopen_discussion(user, discussion, participant=participant),
        can_create_discussion=can_create_discussion(user, space, participant=participant),
        can_rename_discussion=can_rename_discussion(user, space, participant=participant),
        can_delete_discussion=can_delete,
        can_reorganise=can_reorganise(user, space, participant=participant),
        can_view_history=can_view_history(user, space, participant=participant),
        can_opine=can_opine(user, discussion, participant=participant),
        can_toggle_subscription=can_toggle,
        can_moderate_links=can_moderate_content(user, space, participant=participant),
        is_subscribed=is_subscribed(user=user, discussion=discussion) if can_toggle else False,
    )


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


def _post_is_edited(post: Post) -> bool:
    prefetched = getattr(post, "_prefetched_objects_cache", {}).get("revisions")
    if prefetched is not None:
        return len(prefetched) > 1
    return post.revisions.count() > 1


def _visible_inline_children(
    all_children: list[Post | Link | Discussion],
    *,
    user: User,
    participant: SpaceParticipant | None,
) -> list[InlineChild]:
    inline_children = [cast(InlineChild, child) for child in all_children if child.is_post or child.is_link]
    return [
        child
        for child in inline_children
        if not child.is_post or can_view_post(user, cast(Post, child), participant=participant)
    ]


def _build_sub_discussions(
    all_children: list[Post | Link | Discussion],
    *,
    user: User,
    space: Space,
    participant: SpaceParticipant | None,
) -> list[DiscussionDetailSubDiscussion]:
    link_target_ids = {cast(Link, child).target_id for child in all_children if child.is_link}
    raw_sub_discussions = [
        cast(Discussion, child) for child in all_children if child.is_discussion and child.pk not in link_target_ids
    ]
    active_child_counts = _get_visible_active_child_counts(
        raw_sub_discussions,
        user=user,
        space=space,
        participant=participant,
    )
    return [
        DiscussionDetailSubDiscussion(
            discussion=sub_discussion,
            active_child_count=active_child_counts.get(sub_discussion.pk, 0),
        )
        for sub_discussion in raw_sub_discussions
    ]


def _build_inline_child_cards(
    *,
    inline_children: list[InlineChild],
    space: Space,
    user: User,
    participant: SpaceParticipant | None,
    access: DiscussionDetailAccess,
    role_highlight_map: dict[uuid_mod.UUID, str],
    reaction_data: dict[uuid_mod.UUID, ReactionDisplayData],
) -> list[DiscussionDetailInlineChild]:
    link_previews = _get_visible_link_previews(
        inline_children,
        user=user,
        space=space,
        participant=participant,
    )
    cards: list[DiscussionDetailInlineChild] = []
    for child in inline_children:
        if child.is_post:
            post = cast(Post, child)
            post_reactions = reaction_data.get(
                post.pk,
                ReactionDisplayData(user_reaction_type="", reaction_counts={}),
            )
            user_can_edit = can_edit_post(user, post, space, participant=participant)
            user_can_delete = can_delete_post(user, post, space, participant=participant)
            post_show_history = access.can_view_history and not post.is_draft and _post_is_edited(post)
            cards.append(
                DiscussionDetailPost(
                    post=post,
                    author_role_highlight_color=role_highlight_map.get(post.author_id, ""),
                    user_can_edit=user_can_edit,
                    can_publish_draft=post.is_draft and user_can_edit and access.can_post,
                    user_can_react=can_react(user, post, participant=participant),
                    user_reaction_type=post_reactions.user_reaction_type,
                    reaction_counts=post_reactions.reaction_counts,
                    can_delete=user_can_delete,
                    can_move=access.can_reorganise,
                    can_promote=can_promote_post(user, space, participant=participant),
                    can_view_history=access.can_view_history,
                    show_history=post_show_history,
                    show_actions=user_can_edit or user_can_delete or access.can_reorganise or post_show_history,
                )
            )
            continue

        link = cast(Link, child)
        cards.append(
            DiscussionDetailLink(
                link=link,
                link_preview_post=link_previews.get(link.target_id),
                can_delete=access.can_moderate_links,
                can_move=access.can_reorganise,
                show_actions=access.can_moderate_links or access.can_reorganise,
            )
        )
    return cards


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


def _build_root_tree_entry(
    root: Discussion,
    children: list[TreeNodeEntry],
    *,
    include_opinions: bool = True,
) -> TreeNodeEntry:
    opinion_counts = get_opinion_counts_batch([root.pk]) if include_opinions else {}
    return TreeNodeEntry(
        node=root,
        resolution=root.resolution_type,
        opinions=opinion_counts.get(root.pk, {}),
        children=children,
    )


@login_required
def discussion_tree(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_view_space(user, space, participant=participant):
        raise PermissionDenied
    return _render_tree(request, space, user=user, participant=participant)


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
    inline_children = _visible_inline_children(all_children, user=user, participant=participant)
    sub_discussions = _build_sub_discussions(
        all_children,
        user=user,
        space=space,
        participant=participant,
    )

    opinions = get_opinion_counts(discussion)
    user_opinion = get_user_opinion_type(user=user, discussion=discussion) if participant is not None else None

    access = _build_discussion_detail_access(user=user, space=space, discussion=discussion, participant=participant)
    all_discussions = discussion_services.get_all_discussions_with_levels(space) if access.can_reorganise else []

    role_map, role_highlight_map = _get_author_role_maps(space, inline_children)
    reaction_data = _get_user_reactions(inline_children, user if participant is not None else None)
    inline_child_cards = _build_inline_child_cards(
        inline_children=inline_children,
        space=space,
        user=user,
        participant=participant,
        access=access,
        role_highlight_map=role_highlight_map,
        reaction_data=reaction_data,
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
            "can_post": access.can_post,
            "can_create_draft": access.can_create_draft,
            "can_upload_images": access.can_upload_images,
            "can_submit_post_form": access.can_submit_post_form,
            "can_resolve": access.can_resolve,
            "can_reopen": access.can_reopen,
            "can_opine": access.can_opine,
            "can_toggle_subscription": access.can_toggle_subscription,
            "has_discussion_menu_actions": access.has_discussion_menu_actions,
            "can_create_discussion": access.can_create_discussion,
            "can_rename_discussion": access.can_rename_discussion,
            "can_delete_discussion": access.can_delete_discussion,
            "can_reorganise": access.can_reorganise,
            "is_subscribed": access.is_subscribed,
            "all_discussions": all_discussions,
            "role_map": role_map,
        },
    )


@require_POST
@login_required
def discussion_edit(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_rename_discussion(user, space, participant=participant):
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
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_create_discussion(user, space, participant=participant):
        if space.lifecycle == Space.Lifecycle.ARCHIVED:
            return HttpResponse("This space is archived and cannot be modified.", status=403)
        return HttpResponse("Permission denied.", status=403)

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

    response = _render_tree(request, space, user=user, participant=participant)
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(new_discussion.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def discussion_resolve(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_reopen_discussion(user, discussion, participant=participant):
        raise PermissionDenied

    discussion_services.reopen_discussion(discussion=discussion, actor=user)
    response = discussion_detail(request, space_id, discussion_id)
    response["HX-Trigger"] = "refreshTree"
    return response


@require_POST
@login_required
def discussion_delete(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_delete_discussion(user, space, participant=participant):
        raise PermissionDenied

    if discussion.is_root():
        return HttpResponse("Cannot delete the root discussion", status=403)

    parent = discussion.get_parent()
    discussion_services.delete_discussion(discussion=discussion)
    response = _render_tree(request, space, user=user, participant=participant)
    response["HX-Trigger"] = json.dumps({"selectDiscussion": {"id": str(parent.pk), "spaceId": str(space.pk)}})
    return response


@require_POST
@login_required
def discussion_children_reorder(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_reorganise(user, space, participant=participant):
        raise PermissionDenied

    new_parent_id = request.POST.get("new_parent_id")
    new_parent = get_object_or_404(
        Discussion,
        pk=new_parent_id,
        space=space,
        deleted_at__isnull=True,
    )
    discussion_services.move_discussion(discussion=discussion, new_parent=new_parent)

    return _render_tree(request, space, user=user, participant=participant)


@require_POST
@login_required
def tree_reorder(request: HttpRequest, space_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    if not can_reorganise(user, space, participant=participant):
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
    return _render_tree(request, space, user=user, participant=participant)


@require_POST
@login_required
def discussion_merge(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
    context = get_space_request_context(request, space_id)
    space = context.space
    user = context.user
    participant = context.participant
    source = get_object_or_404(
        Discussion,
        pk=discussion_id,
        space=space,
        deleted_at__isnull=True,
    )
    if not can_restructure(user, space, participant=participant):
        raise PermissionDenied

    target_id = request.POST.get("target_id")
    target = get_object_or_404(
        Discussion,
        pk=target_id,
        space=space,
        deleted_at__isnull=True,
    )
    discussion_services.merge_discussions(source=source, target=target)

    return _render_tree(request, space, user=user, participant=participant)


@require_POST
@login_required
def discussion_split(request: HttpRequest, space_id: str, discussion_id: str) -> HttpResponse:
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
    if not can_restructure(user, space, participant=participant):
        raise PermissionDenied

    child_ids = request.POST.getlist("child_ids")
    if not child_ids:
        return HttpResponse("No items selected", status=400)

    try:
        discussion_services.split_discussion(discussion=discussion, child_ids=child_ids)
    except ValueError as error:
        return HttpResponse(str(error), status=400)

    return _render_tree(request, space, user=user, participant=participant)


def _render_tree(
    request: HttpRequest,
    space: Space,
    *,
    user: User,
    participant: SpaceParticipant | None,
) -> HttpResponse:
    root = space.root_discussion
    tree_nodes = discussion_services.get_ordered_discussions(root) if root else []
    nested_nodes = _build_nested_tree(tree_nodes, root.pk if root else "")
    root_node = _build_root_tree_entry(root, nested_nodes) if root else None
    user_can_create_discussion = can_create_discussion(user, space, participant=participant)
    user_can_reorganise = can_reorganise(user, space, participant=participant)
    return render(
        request,
        "discussions/tree.html",
        {
            "root_node": root_node,
            "space": space,
            "root_discussion": root,
            "can_create_discussion": user_can_create_discussion,
            "can_reorganise": user_can_reorganise,
        },
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
