from __future__ import annotations

import uuid as uuid_mod
from functools import partial
from typing import cast

from django.db import models, transaction
from django.db.models import Case, Count, Prefetch, Q, Value, When
from django.utils import timezone

from apps.discussions.models import Discussion
from apps.discussions.ordering import next_sequence_index
from apps.discussions.signals import discussion_items_soft_deleted, discussion_status_changed
from apps.posts.models import Link, Post, PostRevision
from apps.spaces.models import Space
from apps.spaces.services import touch_space
from apps.users.models import User

InlineChild = Discussion | Post | Link


def _discussion_children(parent: Discussion) -> list[InlineChild]:
    sub_discussions = list(parent.get_children().filter(deleted_at__isnull=True))
    posts = list(
        Post.objects.filter(discussion=parent, deleted_at__isnull=True)
        .select_related("created_by")
        .prefetch_related(Prefetch("revisions", queryset=PostRevision.objects.order_by("-created_at")))
    )
    links = list(Link.objects.filter(discussion=parent, deleted_at__isnull=True).select_related("target", "created_by"))
    return sorted(
        [*sub_discussions, *posts, *links],
        key=lambda child: (child.sequence_index, child.created_at, str(child.pk)),
    )


def _reindex_children(parent: Discussion, children: list[InlineChild]) -> None:
    discussion_cases: list[When] = []
    post_cases: list[When] = []
    link_cases: list[When] = []
    for index, child in enumerate(children):
        if child.is_discussion:
            discussion_cases.append(When(pk=child.pk, then=Value(index)))
        elif child.is_post:
            post_cases.append(When(pk=child.pk, then=Value(index)))
        else:
            link_cases.append(When(pk=child.pk, then=Value(index)))

    if discussion_cases:
        Discussion.objects.filter(pk__in=[child.pk for child in children if child.is_discussion]).update(
            sequence_index=Case(*discussion_cases, output_field=models.IntegerField())
        )
    if post_cases:
        Post.objects.filter(pk__in=[child.pk for child in children if child.is_post]).update(
            sequence_index=Case(*post_cases, output_field=models.IntegerField())
        )
    if link_cases:
        Link.objects.filter(pk__in=[child.pk for child in children if child.is_link]).update(
            sequence_index=Case(*link_cases, output_field=models.IntegerField())
        )
    touch_space(space=parent.space)


def _send_discussion_status_changed(
    *,
    discussion_id: uuid_mod.UUID,
    actor_id: uuid_mod.UUID,
    event_type: str,
    resolution_type: str,
) -> None:
    discussion_status_changed.send(
        sender=Discussion,
        discussion_id=discussion_id,
        actor_id=actor_id,
        event_type=event_type,
        resolution_type=resolution_type,
    )


def create_child_discussion(
    *,
    parent: Discussion,
    space: Space,
    label: str = "",
    created_by: User | None = None,
) -> Discussion:
    with transaction.atomic():
        sequence_index = next_sequence_index(parent)
        child = parent.add_child(
            space=space,
            created_by=created_by or space.created_by,
            label=label,
            sequence_index=sequence_index,
        )
        touch_space(space=space)
    return Discussion.objects.get(pk=child.pk)


def _set_resolution(
    *,
    discussion: Discussion,
    resolution_type: str = "",
    resolved_by: User | None = None,
) -> Discussion:
    discussion.resolution_type = resolution_type
    discussion.resolved_by = resolved_by
    discussion.resolved_at = timezone.now() if resolution_type else None
    discussion.save(update_fields=["resolution_type", "resolved_by", "resolved_at"])
    touch_space(space=discussion.space)
    return discussion


def resolve_discussion(*, discussion: Discussion, resolution_type: str, resolved_by: User) -> Discussion:
    resolved = _set_resolution(discussion=discussion, resolution_type=resolution_type, resolved_by=resolved_by)
    transaction.on_commit(
        partial(
            _send_discussion_status_changed,
            discussion_id=discussion.pk,
            actor_id=resolved_by.pk,
            event_type="resolved",
            resolution_type=resolution_type,
        )
    )
    return resolved


def reopen_discussion(*, discussion: Discussion, actor: User | None = None) -> Discussion:
    reopened = _set_resolution(discussion=discussion)
    if actor is not None:
        transaction.on_commit(
            partial(
                _send_discussion_status_changed,
                discussion_id=discussion.pk,
                actor_id=actor.pk,
                event_type="reopened",
                resolution_type="",
            )
        )
    return reopened


def delete_discussion(*, discussion: Discussion) -> Discussion:
    now = timezone.now()
    with transaction.atomic():
        descendant_ids = list(discussion.get_descendants().values_list("pk", flat=True))
        discussion_ids = [discussion.pk, *descendant_ids]
        post_ids = list(Post.objects.filter(discussion_id__in=discussion_ids).values_list("pk", flat=True))
        Discussion.objects.filter(pk__in=discussion_ids).update(deleted_at=now)
        Post.objects.filter(discussion_id__in=discussion_ids).update(deleted_at=now)
        Link.objects.filter(discussion_id__in=discussion_ids).update(deleted_at=now)
        discussion.deleted_at = now
        discussion_items_soft_deleted.send(sender=Discussion, item_ids=[*discussion_ids, *post_ids])
        touch_space(space=discussion.space)
    return discussion


def update_discussion(*, discussion: Discussion, label: str) -> Discussion:
    discussion.label = label
    discussion.save(update_fields=["label"])
    touch_space(space=discussion.space)
    return discussion


def move_discussion(*, discussion: Discussion, new_parent: Discussion) -> Discussion:
    with transaction.atomic():
        old_parent = discussion.get_parent()
        if old_parent and old_parent.pk == new_parent.pk:
            return discussion
        if new_parent.pk == discussion.pk or new_parent.is_descendant_of(discussion):
            msg = "Cannot move a discussion into its own subtree"
            raise ValueError(msg)
        sequence_index = next_sequence_index(new_parent)
        Discussion.objects.filter(pk=discussion.pk).update(sequence_index=sequence_index)
        discussion.sequence_index = sequence_index
        discussion.move(new_parent, pos="sorted-child")
        discussion.refresh_from_db()
        touch_space(space=discussion.space)
    return discussion


def reorder_children(*, node_ids: list[str]) -> None:
    if not node_ids:
        return

    with transaction.atomic():
        discussion_ids = set(Discussion.objects.filter(pk__in=node_ids).values_list("pk", flat=True))
        post_ids = set(Post.objects.filter(pk__in=node_ids).values_list("pk", flat=True))
        link_ids = set(Link.objects.filter(pk__in=node_ids).values_list("pk", flat=True))
        matched_count = len(discussion_ids) + len(post_ids) + len(link_ids)
        if matched_count != len(node_ids):
            raise ValueError("Unknown child ids passed to reorder_children")

        if discussion_ids:
            discussion = Discussion.objects.filter(pk=node_ids[0]).select_related("space").first()
            cases = [When(pk=node_id, then=Value(index)) for index, node_id in enumerate(node_ids)]
            Discussion.objects.filter(pk__in=node_ids).update(
                sequence_index=Case(*cases, output_field=models.IntegerField())
            )
            if discussion is not None:
                touch_space(space=discussion.space)
            return

        posts = {
            str(post.pk): post for post in Post.objects.filter(pk__in=node_ids).select_related("discussion__space")
        }
        links = {
            str(link.pk): link for link in Link.objects.filter(pk__in=node_ids).select_related("discussion__space")
        }
        first_child = posts.get(node_ids[0]) or links.get(node_ids[0])
        if first_child is None:
            return
        children: list[InlineChild] = []
        for node_id in node_ids:
            child = posts.get(node_id) or links.get(node_id)
            if child is not None:
                children.append(child)
        _reindex_children(first_child.discussion, children)


def get_ordered_discussions(root: Discussion) -> list[Discussion]:
    descendants = list(root.get_descendants().filter(deleted_at__isnull=True))
    if not descendants:
        return []

    steplen = root.steplen
    children_map: dict[str, list[Discussion]] = {}
    for node in descendants:
        parent_path = node.path[: len(node.path) - steplen]
        children_map.setdefault(parent_path, []).append(node)

    for siblings in children_map.values():
        siblings.sort(key=lambda node: (node.sequence_index, node.created_at))

    result: list[Discussion] = []

    def _dfs(path: str) -> None:
        for child in children_map.get(path, []):
            result.append(child)
            _dfs(child.path)

    _dfs(root.path)
    return result


def get_discussion_children(discussion: Discussion) -> list[Discussion | Post | Link]:
    return _discussion_children(discussion)


def get_active_child_counts(discussions: list[Discussion]) -> dict[uuid_mod.UUID, int]:
    if not discussions:
        return {}

    counts = {discussion.pk: 0 for discussion in discussions}

    discussion_query = Q()
    for discussion in discussions:
        discussion_query |= Q(path__startswith=discussion.path, depth=discussion.depth + 1)

    if discussion_query:
        path_to_id = {discussion.path: discussion.pk for discussion in discussions}
        direct_discussions = Discussion.objects.filter(discussion_query, deleted_at__isnull=True).only("path")
        for child in direct_discussions:
            parent_path = child.path[: len(child.path) - Discussion.steplen]
            parent_id = path_to_id.get(parent_path)
            if parent_id is not None:
                counts[parent_id] += 1

    for row in (
        Post.objects.filter(discussion_id__in=counts, deleted_at__isnull=True)
        .values("discussion_id")
        .annotate(count=Count("pk"))
    ):
        counts[row["discussion_id"]] += row["count"]

    for row in (
        Link.objects.filter(discussion_id__in=counts, deleted_at__isnull=True)
        .values("discussion_id")
        .annotate(count=Count("pk"))
    ):
        counts[row["discussion_id"]] += row["count"]

    return counts


def merge_discussions(*, source: Discussion, target: Discussion) -> Discussion:
    if source.pk == target.pk:
        raise ValueError("Cannot merge a discussion into itself")
    with transaction.atomic():
        next_index = next_sequence_index(target)
        for offset, child in enumerate(_discussion_children(source)):
            if child.is_discussion:
                moved_child = cast(Discussion, child)
                Discussion.objects.filter(pk=moved_child.pk).update(sequence_index=next_index + offset)
                moved_child.sequence_index = next_index + offset
                moved_child.move(target, pos="sorted-child")
            elif child.is_post:
                Post.objects.filter(pk=child.pk).update(discussion=target, sequence_index=next_index + offset)
            else:
                Link.objects.filter(pk=child.pk).update(discussion=target, sequence_index=next_index + offset)

        source.deleted_at = timezone.now()
        source.save(update_fields=["deleted_at"])
        discussion_items_soft_deleted.send(sender=Discussion, item_ids=[source.pk])
        touch_space(space=source.space)

    return target


def split_discussion(*, discussion: Discussion, child_ids: list[str]) -> Discussion:
    with transaction.atomic():
        parent = discussion.get_parent()
        if parent is None:
            msg = "Cannot split a root discussion"
            raise ValueError(msg)

        new_discussion = parent.add_child(
            space=discussion.space,
            created_by=discussion.created_by,
            label=f"{discussion.label} (split)",
            sequence_index=next_sequence_index(parent),
        )
        children = [child for child in _discussion_children(discussion) if str(child.pk) in child_ids]
        for index, child in enumerate(children):
            if child.is_discussion:
                moved_child = cast(Discussion, child)
                Discussion.objects.filter(pk=moved_child.pk).update(sequence_index=index)
                moved_child.sequence_index = index
                moved_child.move(new_discussion, pos="sorted-child")
            elif child.is_post:
                Post.objects.filter(pk=child.pk).update(discussion=new_discussion, sequence_index=index)
            else:
                Link.objects.filter(pk=child.pk).update(discussion=new_discussion, sequence_index=index)

        remaining = [child for child in _discussion_children(discussion) if str(child.pk) not in child_ids]
        _reindex_children(discussion, remaining)

        touch_space(space=discussion.space)

    return Discussion.objects.get(pk=new_discussion.pk)


def get_link_previews(children: list[Discussion | Post | Link]) -> dict[uuid_mod.UUID, Post]:
    link_target_ids = {
        cast(Link, child).target_id for child in children if child.is_link and cast(Link, child).target_id
    }
    if not link_target_ids:
        return {}

    first_posts: dict[uuid_mod.UUID, Post] = {}
    for post in (
        Post.objects.filter(discussion_id__in=link_target_ids, deleted_at__isnull=True)
        .select_related("created_by")
        .prefetch_related(Prefetch("revisions", queryset=PostRevision.objects.order_by("-created_at")))
        .order_by("discussion_id", "sequence_index", "created_at")
    ):
        if post.discussion_id not in first_posts:
            first_posts[post.discussion_id] = post
    return first_posts


def get_all_discussions_with_levels(space: Space) -> list[Discussion]:
    root = space.root_discussion
    if root is None:
        return []
    discussions = [
        root,
        *root.get_descendants().filter(deleted_at__isnull=True),
    ]
    root_depth = root.depth
    depth_to_parent: dict[int, str] = {}
    for discussion in discussions:
        discussion.level = discussion.depth - root_depth
        discussion.parent_id_str = depth_to_parent.get(discussion.depth - 1, "")
        depth_to_parent[discussion.depth] = str(discussion.pk)
    return discussions


__all__ = [
    "create_child_discussion",
    "delete_discussion",
    "get_all_discussions_with_levels",
    "get_discussion_children",
    "get_link_previews",
    "get_ordered_discussions",
    "merge_discussions",
    "move_discussion",
    "reopen_discussion",
    "reorder_children",
    "resolve_discussion",
    "split_discussion",
    "update_discussion",
]
