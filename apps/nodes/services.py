from __future__ import annotations

import uuid as uuid_mod

from django.db import models, transaction
from django.db.models import Case, F, Max, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.nodes.models import Node, PostRevision
from apps.spaces.models import Space
from apps.users.models import User


def _adjust_child_count(parent_pk: uuid_mod.UUID, delta: int) -> None:
    """Adjust the child_count of a node by a delta value."""
    Node.objects.filter(pk=parent_pk).update(child_count=F("child_count") + delta)


def _recount_children(parent_pk: uuid_mod.UUID) -> None:
    """Recompute child_count from the actual number of non-deleted children."""
    count = Node.objects.get(pk=parent_pk).get_children().filter(deleted_at__isnull=True).count()
    Node.objects.filter(pk=parent_pk).update(child_count=count)


def _next_sequence_index(parent: Node) -> int:
    """Get the next sequence_index for a child of the given parent.

    Must be called within a transaction.atomic() block.
    Locks the parent row to prevent concurrent duplicate indices.
    """
    Node.objects.select_for_update().filter(pk=parent.pk).first()
    children = parent.get_children().filter(deleted_at__isnull=True)
    result: int = (children.aggregate(max_idx=Coalesce(Max("sequence_index"), -1)))["max_idx"] + 1
    return result


def create_child_discussion(
    *,
    parent: Node,
    space: Space,
    label: str = "",
) -> Node:
    with transaction.atomic():
        seq = _next_sequence_index(parent)
        child: Node = parent.add_child(
            space=space,
            label=label,
            node_type=Node.NodeType.DISCUSSION,
            sequence_index=seq,
        )
        _adjust_child_count(parent.pk, 1)
    return child


def create_post(
    *,
    discussion: Node,
    author: User,
    content: str,
    reopens_discussion: bool = False,
) -> Node:
    if not discussion.space.is_active:
        msg = "Discussion is locked"
        raise ValueError(msg)

    with transaction.atomic():
        seq = _next_sequence_index(discussion)
        post: Node = discussion.add_child(
            space=discussion.space,
            node_type=Node.NodeType.POST,
            author=author,
            content=content,
            reopens_discussion=reopens_discussion,
            sequence_index=seq,
        )
        _adjust_child_count(discussion.pk, 1)
    return post


def _set_resolution(
    *,
    discussion: Node,
    resolution_type: str = "",
    resolved_by: User | None = None,
) -> Node:
    discussion.resolution_type = resolution_type
    discussion.resolved_by = resolved_by
    discussion.resolved_at = timezone.now() if resolution_type else None
    discussion.save(update_fields=["resolution_type", "resolved_by", "resolved_at"])
    return discussion


def resolve_discussion(
    *,
    discussion: Node,
    resolution_type: str,
    resolved_by: User,
) -> Node:
    return _set_resolution(discussion=discussion, resolution_type=resolution_type, resolved_by=resolved_by)


def reopen_discussion(*, discussion: Node) -> Node:
    return _set_resolution(discussion=discussion)


def update_post(*, post: Node, content: str) -> Node:
    with transaction.atomic():
        PostRevision.objects.create(post=post, content=post.content)
        post.content = content
        post.updated_at = timezone.now()
        post.save(update_fields=["content", "updated_at"])
    return post


def soft_delete_node(*, node: Node) -> Node:
    """Soft-delete a node and all its descendants."""
    from apps.opinions.models import Opinion, Reaction
    from apps.subscriptions.models import Subscription

    now = timezone.now()
    with transaction.atomic():
        parent = node.get_parent()
        descendant_ids = list(node.get_descendants().values_list("pk", flat=True))
        all_ids = [node.pk, *descendant_ids]
        Node.objects.filter(pk__in=descendant_ids).update(deleted_at=now)
        node.deleted_at = now
        node.save(update_fields=["deleted_at"])
        Subscription.objects.filter(node_id__in=all_ids).delete()
        Opinion.objects.filter(node_id__in=all_ids).delete()
        Reaction.objects.filter(post_id__in=all_ids).delete()
        if parent:
            _adjust_child_count(parent.pk, -1)
    return node


def move_post(*, post: Node, target_discussion: Node, position: int = -1) -> Node:
    """Move a post to a different discussion (or reorder within the same one).

    *position* is the 0-based index of the post in the final child list
    (i.e. the index it should occupy after the move, counting itself).
    ``-1`` means append at the bottom.
    """
    with transaction.atomic():
        old_parent = post.get_parent()
        same_parent = old_parent is not None and old_parent.pk == target_discussion.pk

        post.move(target_discussion, pos="last-child")
        post.refresh_from_db()

        # Collect siblings in the desired order, excluding the moved post.
        other_children = list(
            target_discussion.get_children()
            .filter(deleted_at__isnull=True)
            .exclude(pk=post.pk)
            .order_by("sequence_index", "created_at")
        )

        # Insert the moved post at the requested position.
        if position < 0 or position > len(other_children):
            other_children.append(post)
        else:
            other_children.insert(position, post)

        # Reindex all children using a two-pass bulk UPDATE to avoid
        # transient unique-constraint violations on (path, sequence_index)
        # when shifting nodes to higher indices.
        if other_children:
            pks = [c.pk for c in other_children]

            # Pass 1 – move every node to a safe temporary range (offset
            # by 100 000) so no two non-deleted siblings share an index.
            Node.objects.filter(pk__in=pks).update(
                sequence_index=Case(
                    *[When(pk=c.pk, then=Value(100_000 + i)) for i, c in enumerate(other_children)],
                    output_field=models.IntegerField(),
                )
            )

            # Pass 2 – assign the real, compact indices.
            Node.objects.filter(pk__in=pks).update(
                sequence_index=Case(
                    *[When(pk=c.pk, then=Value(i)) for i, c in enumerate(other_children)],
                    output_field=models.IntegerField(),
                )
            )

        post.refresh_from_db()

        if not same_parent:
            if old_parent:
                _adjust_child_count(old_parent.pk, -1)
            _adjust_child_count(target_discussion.pk, 1)

    return post


def update_discussion(*, discussion: Node, label: str) -> Node:
    discussion.label = label
    discussion.save(update_fields=["label"])
    return discussion


def move_discussion(*, discussion: Node, new_parent: Node) -> None:
    with transaction.atomic():
        old_parent = discussion.get_parent()
        if old_parent and old_parent.pk == new_parent.pk:
            return
        if new_parent.pk == discussion.pk or new_parent.is_descendant_of(discussion):
            msg = "Cannot move a discussion into its own subtree"
            raise ValueError(msg)
        discussion.move(new_parent, pos="last-child")
        discussion.refresh_from_db()
        if old_parent:
            _adjust_child_count(old_parent.pk, -1)
        _adjust_child_count(new_parent.pk, 1)


def reorder_children(*, node_ids: list[str]) -> None:
    with transaction.atomic():
        cases = [When(pk=node_id, then=Value(i)) for i, node_id in enumerate(node_ids)]
        Node.objects.filter(pk__in=node_ids).update(sequence_index=Case(*cases, output_field=models.IntegerField()))


def get_ordered_discussions(root: Node) -> list[Node]:
    """Get discussion descendants in DFS order for the tree view.

    Uses a single query via get_descendants(), then sorts in Python
    to respect sequence_index ordering within sibling groups.
    """
    descendants = list(
        root.get_descendants()
        .filter(deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION)
        .order_by("depth", "path")
    )
    if not descendants:
        return []

    # Build children map keyed by parent path
    steplen = root.steplen
    children_map: dict[str, list[Node]] = {}
    for node in descendants:
        parent_path = node.path[: len(node.path) - steplen]
        children_map.setdefault(parent_path, []).append(node)

    # Sort each sibling group by sequence_index, then created_at
    for siblings in children_map.values():
        siblings.sort(key=lambda n: (n.sequence_index, n.created_at))

    # DFS traversal using the sorted children map
    result: list[Node] = []

    def _dfs(path: str) -> None:
        for child in children_map.get(path, []):
            result.append(child)
            _dfs(child.path)

    _dfs(root.path)
    return result


def get_discussion_children(discussion: Node) -> list[Node]:
    """Get the ordered children (posts, links, discussions) of a discussion."""
    return list(
        discussion.get_children()
        .filter(deleted_at__isnull=True)
        .select_related("target", "author")
        .order_by("sequence_index", "created_at")
    )


def merge_discussions(*, source: Node, target: Node) -> Node:
    if source.pk == target.pk:
        raise ValueError("Cannot merge a discussion into itself")
    with transaction.atomic():
        source.refresh_from_db()
        target_max_index = _next_sequence_index(target)

        children = list(source.get_children().filter(deleted_at__isnull=True).order_by("sequence_index"))
        for i, child in enumerate(children):
            child.move(target, pos="last-child")
            child.refresh_from_db()
            child.sequence_index = target_max_index + i
            child.save(update_fields=["sequence_index"])

        _recount_children(target.pk)

        source.deleted_at = timezone.now()
        source.child_count = 0
        source.save(update_fields=["deleted_at", "child_count"])

        # Clean up subscriptions and opinions on the soft-deleted source
        from apps.opinions.models import Opinion
        from apps.subscriptions.models import Subscription

        Subscription.objects.filter(node=source).delete()
        Opinion.objects.filter(node=source).delete()

        source_parent = source.get_parent()
        if source_parent:
            _adjust_child_count(source_parent.pk, -1)

    return target


def split_discussion(*, discussion: Node, child_ids: list[str]) -> Node:
    with transaction.atomic():
        parent = discussion.get_parent()
        if parent is None:
            msg = "Cannot split a root discussion"
            raise ValueError(msg)

        new_discussion: Node = parent.add_child(
            space=discussion.space,
            label=f"{discussion.label} (split)",
            node_type=Node.NodeType.DISCUSSION,
            sequence_index=_next_sequence_index(parent),
        )

        children = list(
            discussion.get_children().filter(pk__in=child_ids, deleted_at__isnull=True).order_by("sequence_index")
        )
        for i, child in enumerate(children):
            child.move(new_discussion, pos="last-child")
            child.refresh_from_db()
            child.sequence_index = i
            child.save(update_fields=["sequence_index"])

        moved_count = len(children)
        _adjust_child_count(discussion.pk, -moved_count)
        Node.objects.filter(pk=new_discussion.pk).update(child_count=moved_count)
        _adjust_child_count(parent.pk, 1)

        remaining = list(
            discussion.get_children().filter(deleted_at__isnull=True).order_by("sequence_index", "created_at")
        )
        if remaining:
            remaining_ids = [c.pk for c in remaining]
            # Two-pass bulk update to avoid unique constraint violations
            Node.objects.filter(pk__in=remaining_ids).update(
                sequence_index=Case(
                    *[When(pk=c.pk, then=Value(100000 + i)) for i, c in enumerate(remaining)],
                    output_field=models.IntegerField(),
                )
            )
            Node.objects.filter(pk__in=remaining_ids).update(
                sequence_index=Case(
                    *[When(pk=c.pk, then=Value(i)) for i, c in enumerate(remaining)],
                    output_field=models.IntegerField(),
                )
            )

    return new_discussion


def promote_post(*, post: Node) -> tuple[Node, Node]:
    """Promote a Post into a Discussion. Returns (new_discussion, link)."""
    with transaction.atomic():
        parent = post.get_parent()
        if parent is None:
            msg = "Cannot promote a root post"
            raise ValueError(msg)

        original_seq = post.sequence_index

        # Create new Discussion as child of the same parent
        new_discussion: Node = parent.add_child(
            space=post.space,
            label=Truncator(strip_tags(post.content).strip()).chars(80),
            node_type=Node.NodeType.DISCUSSION,
            sequence_index=_next_sequence_index(parent),
        )

        # Move the original post into the new discussion as its seed
        post.move(new_discussion, pos="last-child")
        post.refresh_from_db()
        post.sequence_index = 0
        post.save(update_fields=["sequence_index"])

        _adjust_child_count(new_discussion.pk, 1)

        # Create a Link at the original post's position in the parent
        link: Node = parent.add_child(
            space=post.space,
            node_type=Node.NodeType.LINK,
            target=new_discussion,
            sequence_index=original_seq,
        )

        # Update parent child count
        _recount_children(parent.pk)

    return new_discussion, link


def get_link_previews(children: list[Node]) -> dict[uuid_mod.UUID, Node]:
    """Return a mapping of link target_id → first post Node for link nodes."""
    link_target_ids = {c.target_id for c in children if c.is_link and c.target_id}
    if not link_target_ids:
        return {}

    target_nodes = list(Node.objects.filter(pk__in=link_target_ids))
    child_q = Q()
    for tn in target_nodes:
        child_q |= Q(path__startswith=tn.path, depth=tn.depth + 1)
    if not child_q:
        return {}

    first_posts: dict[uuid_mod.UUID, Node] = {}
    for post in (
        Node.objects.filter(child_q)
        .filter(node_type=Node.NodeType.POST, deleted_at__isnull=True)
        .select_related("author")
        .order_by("path", "sequence_index", "created_at")
    ):
        parent_path = post.path[: len(post.path) - post.steplen]
        parent_node = next((tn for tn in target_nodes if tn.path == parent_path), None)
        if parent_node and parent_node.pk not in first_posts:
            first_posts[parent_node.pk] = post
    return first_posts


def get_all_discussions_with_levels(space: Space) -> list[Node]:
    """Return all discussions in a space with computed `level` and `parent_id` attributes."""
    root = space.root_discussion
    if not root:
        return []
    discussions = [
        root,
        *root.get_descendants().filter(deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION),
    ]
    root_depth = root.depth
    depth_to_parent: dict[int, str] = {}
    for d in discussions:
        d.level = d.depth - root_depth
        d.parent_id_str = depth_to_parent.get(d.depth - 1, "")
        depth_to_parent[d.depth] = str(d.pk)
    return discussions
