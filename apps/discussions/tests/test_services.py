from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.discussions import services as discussion_services
from apps.posts import services as post_services
from apps.posts.models import Link
from apps.spaces import services as space_services
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_get_discussion_children_prefetches_post_revisions() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Query Audit", created_by=user)
    space_services.open_space(space=space)
    discussion = discussion_services.create_child_discussion(
        parent=space.root_discussion,
        space=space,
        label="Topic",
        created_by=user,
    )
    post_services.create_post(discussion=discussion, author=user, content="<p>First</p>")
    post_services.create_post(discussion=discussion, author=user, content="<p>Second</p>")

    with CaptureQueriesContext(connection) as queries:
        children = discussion_services.get_discussion_children(discussion)
        contents = [child.content for child in children if child.is_post]

    assert contents == ["<p>First</p>", "<p>Second</p>"]
    assert len(queries) == 3


@pytest.mark.django_db
def test_get_link_previews_prefetches_preview_post_revisions() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Preview Audit", created_by=user)
    space_services.open_space(space=space)
    root = space.root_discussion
    source = discussion_services.create_child_discussion(parent=root, space=space, label="Source", created_by=user)
    target = discussion_services.create_child_discussion(parent=root, space=space, label="Target", created_by=user)
    post_services.create_post(discussion=target, author=user, content="<p>Preview body</p>")
    Link.objects.create(
        discussion=source,
        created_by=user,
        target=target,
        sequence_index=0,
    )
    children = discussion_services.get_discussion_children(source)

    with CaptureQueriesContext(connection) as queries:
        previews = discussion_services.get_link_previews(children)
        preview_contents = [post.content for post in previews.values()]

    assert preview_contents == ["<p>Preview body</p>"]
    assert len(queries) == 2


@pytest.mark.django_db
def test_get_active_child_counts_batches_discussion_post_and_link_counts() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Child Count Audit", created_by=user)
    space_services.open_space(space=space)
    root = space.root_discussion
    first = discussion_services.create_child_discussion(parent=root, space=space, label="First", created_by=user)
    second = discussion_services.create_child_discussion(parent=root, space=space, label="Second", created_by=user)
    discussion_services.create_child_discussion(parent=first, space=space, label="Nested", created_by=user)
    post_services.create_post(discussion=first, author=user, content="<p>First post</p>")
    post_services.create_post(discussion=second, author=user, content="<p>Second post</p>")
    Link.objects.create(
        discussion=second,
        created_by=user,
        target=first,
        sequence_index=1,
    )

    with CaptureQueriesContext(connection) as queries:
        counts = discussion_services.get_active_child_counts([first, second])

    assert counts == {first.pk: 2, second.pk: 2}
    assert len(queries) == 3


@pytest.mark.django_db
def test_move_discussion_moves_to_new_parent_in_ordered_tree() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Move Audit", created_by=user)
    space_services.open_space(space=space)
    root = space.root_discussion
    assert root is not None
    source_parent = discussion_services.create_child_discussion(
        parent=root,
        space=space,
        label="Source",
        created_by=user,
    )
    target_parent = discussion_services.create_child_discussion(
        parent=root,
        space=space,
        label="Target",
        created_by=user,
    )
    existing_child = discussion_services.create_child_discussion(
        parent=target_parent,
        space=space,
        label="Existing child",
        created_by=user,
    )
    moved = discussion_services.create_child_discussion(
        parent=source_parent,
        space=space,
        label="Move me",
        created_by=user,
    )

    discussion_services.move_discussion(discussion=moved, new_parent=target_parent)

    moved.refresh_from_db()
    assert moved.get_parent().pk == target_parent.pk
    assert moved.sequence_index > existing_child.sequence_index


@pytest.mark.django_db
def test_merge_discussions_moves_subdiscussion_children_in_ordered_tree() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Merge Audit", created_by=user)
    space_services.open_space(space=space)
    root = space.root_discussion
    assert root is not None
    source = discussion_services.create_child_discussion(parent=root, space=space, label="Source", created_by=user)
    target = discussion_services.create_child_discussion(parent=root, space=space, label="Target", created_by=user)
    existing_child = discussion_services.create_child_discussion(
        parent=target,
        space=space,
        label="Existing child",
        created_by=user,
    )
    moved_child = discussion_services.create_child_discussion(
        parent=source,
        space=space,
        label="Moved child",
        created_by=user,
    )

    discussion_services.merge_discussions(source=source, target=target)

    moved_child.refresh_from_db()
    assert moved_child.get_parent().pk == target.pk
    assert moved_child.sequence_index > existing_child.sequence_index


@pytest.mark.django_db
def test_split_discussion_moves_subdiscussion_children_in_ordered_tree() -> None:
    user = UserFactory()
    space = space_services.create_space(title="Split Audit", created_by=user)
    space_services.open_space(space=space)
    root = space.root_discussion
    assert root is not None
    discussion = discussion_services.create_child_discussion(parent=root, space=space, label="Topic", created_by=user)
    moved_child = discussion_services.create_child_discussion(
        parent=discussion,
        space=space,
        label="Moved child",
        created_by=user,
    )

    split = discussion_services.split_discussion(discussion=discussion, child_ids=[str(moved_child.pk)])

    moved_child.refresh_from_db()
    assert split.get_parent().pk == root.pk
    assert moved_child.get_parent().pk == split.pk
