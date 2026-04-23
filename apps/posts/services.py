from __future__ import annotations

import uuid as uuid_mod
from functools import partial
from typing import cast

from django.db import models, transaction
from django.db.models import Case, Value, When
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.discussions.models import Discussion
from apps.discussions.ordering import next_sequence_index
from apps.discussions.signals import discussion_items_soft_deleted, discussion_posted
from apps.posts.models import Link, Post, PostRevision
from apps.spaces.models import SpaceParticipant
from apps.spaces.permissions import can_modify_space
from apps.spaces.services import touch_space
from apps.users.models import User


def _ordered_inline_children(
    discussion: Discussion,
    *,
    exclude_ids: set[uuid_mod.UUID] | None = None,
) -> list[Post | Link]:
    posts_qs = Post.objects.filter(discussion=discussion, deleted_at__isnull=True)
    links_qs = Link.objects.filter(discussion=discussion, deleted_at__isnull=True)
    if exclude_ids:
        posts_qs = posts_qs.exclude(pk__in=exclude_ids)
        links_qs = links_qs.exclude(pk__in=exclude_ids)
    posts = list(posts_qs.select_related("created_by"))
    links = list(links_qs.select_related("created_by", "target"))
    return sorted(
        [*posts, *links],
        key=lambda child: (child.sequence_index, child.created_at, str(child.pk)),
    )


def _reindex_inline_children(children: list[Post | Link]) -> None:
    post_cases = [When(pk=child.pk, then=Value(index)) for index, child in enumerate(children) if child.is_post]
    link_cases = [When(pk=child.pk, then=Value(index)) for index, child in enumerate(children) if child.is_link]

    if post_cases:
        Post.objects.filter(pk__in=[child.pk for child in children if child.is_post]).update(
            sequence_index=Case(*post_cases, output_field=models.IntegerField())
        )
    if link_cases:
        Link.objects.filter(pk__in=[child.pk for child in children if child.is_link]).update(
            sequence_index=Case(*link_cases, output_field=models.IntegerField())
        )


def _send_discussion_posted(
    *,
    discussion_id: uuid_mod.UUID,
    post_id: uuid_mod.UUID,
    actor_id: uuid_mod.UUID,
) -> None:
    discussion_posted.send(
        sender=Post,
        discussion_id=discussion_id,
        post_id=post_id,
        actor_id=actor_id,
    )


def create_post(
    *,
    discussion: Discussion,
    author: User,
    content: str,
    is_draft: bool = False,
    participant: SpaceParticipant | None = None,
) -> Post:
    if discussion.space.deleted_at is not None or discussion.space.lifecycle == discussion.space.Lifecycle.ARCHIVED:
        msg = "Discussion is locked"
        raise ValueError(msg)
    if not discussion.space.is_active and not can_modify_space(author, discussion.space, participant=participant):
        msg = "Discussion is locked"
        raise ValueError(msg)

    with transaction.atomic():
        sequence_index = next_sequence_index(discussion)
        post = Post.objects.create(
            discussion=discussion,
            created_by=author,
            is_draft=is_draft,
            sequence_index=sequence_index,
        )
        PostRevision.objects.create(post=post, content=content, created_by=author)
        touch_space(space=discussion.space)
        if not is_draft:
            transaction.on_commit(
                partial(_send_discussion_posted, discussion_id=discussion.pk, post_id=post.pk, actor_id=author.pk)
            )
    return post


def update_post(
    *,
    post: Post,
    content: str,
    is_draft: bool | None = None,
    actor: User | None = None,
) -> Post:
    target_is_draft = post.is_draft if is_draft is None else is_draft
    if not post.is_draft and target_is_draft:
        raise ValueError("Published posts cannot be converted back to drafts")

    published_from_draft = post.is_draft and not target_is_draft
    actor_user = actor or post.author

    with transaction.atomic():
        if post.is_draft:
            parent = post.get_parent()
            if not target_is_draft:
                post.is_draft = False
                post.created_at = timezone.now()
                post.sequence_index = next_sequence_index(parent)
            latest_revision = post.revisions.order_by("-created_at").first()
            if latest_revision is None:
                PostRevision.objects.create(post=post, content=content, created_by=actor_user)
            else:
                latest_revision.content = content
                latest_revision.created_by = actor_user
                latest_revision.save(update_fields=["content", "created_by"])
        else:
            PostRevision.objects.create(post=post, content=content, created_by=actor_user)
        update_fields = ["is_draft", "sequence_index", "updated_at"]
        if published_from_draft:
            update_fields.append("created_at")
        post.save(update_fields=update_fields)
        touch_space(space=post.space)
        if published_from_draft:
            parent = post.get_parent()
            transaction.on_commit(
                partial(_send_discussion_posted, discussion_id=parent.pk, post_id=post.pk, actor_id=actor_user.pk)
            )
    return post


def delete_post(*, post: Post) -> Post:
    now = timezone.now()
    with transaction.atomic():
        post.deleted_at = now
        post.save(update_fields=["deleted_at"])
        discussion_items_soft_deleted.send(sender=Post, item_ids=[post.pk])
        touch_space(space=post.space)
    return post


def delete_link(*, link: Link) -> Link:
    now = timezone.now()
    with transaction.atomic():
        link.deleted_at = now
        link.save(update_fields=["deleted_at"])
        touch_space(space=link.space)
    return link


def _sorted_items_for_move(items: list[Post | Link]) -> list[Post | Link]:
    return sorted(
        items,
        key=lambda child: (str(child.discussion_id), child.sequence_index, child.created_at, str(child.pk)),
    )


def move_discussion_items(
    *,
    items: list[Post | Link],
    target_discussion: Discussion,
    position: int = -1,
    target_order_ids: list[uuid_mod.UUID] | None = None,
) -> list[Post | Link]:
    if not items:
        return []

    item_ids = {item.pk for item in items}
    item_map = {item.pk: item for item in items}
    ordered_items = _sorted_items_for_move(items)
    if target_order_ids is not None:
        ordered_items = [item_map[item_id] for item_id in target_order_ids if item_id in item_map]

    with transaction.atomic():
        source_discussions = {item.discussion for item in ordered_items}
        for item in ordered_items:
            item.discussion = target_discussion
            item.sequence_index = next_sequence_index(target_discussion)
            item.save(update_fields=["discussion", "sequence_index"])

        existing_target_children = _ordered_inline_children(target_discussion, exclude_ids=item_ids)
        if target_order_ids is not None:
            children_by_id = {child.pk: child for child in [*existing_target_children, *ordered_items]}
            if set(children_by_id) != set(target_order_ids):
                msg = "Target ordering did not match the selected destination discussion"
                raise ValueError(msg)
            target_children = [children_by_id[item_id] for item_id in target_order_ids]
        else:
            target_children = existing_target_children
            if position < 0 or position > len(target_children):
                target_children.extend(ordered_items)
            else:
                target_children[position:position] = ordered_items
        _reindex_inline_children(target_children)

        for source_discussion in source_discussions:
            if source_discussion.pk == target_discussion.pk:
                continue
            _reindex_inline_children(_ordered_inline_children(source_discussion))

        touch_space(space=target_discussion.space)

    for item in ordered_items:
        item.refresh_from_db()

    return ordered_items


def move_discussion_item(
    *,
    item: Post | Link,
    target_discussion: Discussion,
    position: int = -1,
) -> Post | Link:
    return move_discussion_items(items=[item], target_discussion=target_discussion, position=position)[0]


def promote_post_to_discussion(*, post: Post) -> tuple[Discussion, Link]:
    with transaction.atomic():
        parent = post.get_parent()
        original_sequence_index = post.sequence_index
        new_discussion = parent.add_child(
            space=post.space,
            created_by=post.created_by,
            label=Truncator(strip_tags(post.content).strip()).chars(80),
            sequence_index=next_sequence_index(parent),
        )

        link = Link.objects.create(
            discussion=parent,
            created_by=post.created_by,
            target=new_discussion,
            sequence_index=original_sequence_index,
        )
        post.discussion = cast(Discussion, new_discussion)
        post.sequence_index = 0
        post.save(update_fields=["discussion", "sequence_index"])

        touch_space(space=post.space)

    return (
        Discussion.objects.get(pk=new_discussion.pk),
        link,
    )


__all__ = [
    "create_post",
    "delete_link",
    "delete_post",
    "move_discussion_item",
    "move_discussion_items",
    "promote_post_to_discussion",
    "update_post",
]
