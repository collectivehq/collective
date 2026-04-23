from __future__ import annotations

import pytest

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.posts.models import Link


@pytest.mark.django_db
class TestPostServices:
    def test_create_post_creates_initial_revision(self, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users

        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Hello")

        assert post.revisions.count() == 1
        assert post.content == "Hello"

    def test_update_post_appends_revision_for_published_post(self, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="First")

        updated = post_services.update_post(post=post, content="Second", actor=participant)

        assert updated.revisions.count() == 2
        assert updated.content == "Second"

    def test_move_discussion_items_preserves_relative_order_in_same_discussion(self, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        discussion = space.root_discussion
        first = post_services.create_post(discussion=discussion, author=participant, content="First")
        second = post_services.create_post(discussion=discussion, author=participant, content="Second")
        third = post_services.create_post(discussion=discussion, author=participant, content="Third")
        fourth = post_services.create_post(discussion=discussion, author=participant, content="Fourth")

        moved = post_services.move_discussion_items(
            items=[fourth, second],
            target_discussion=discussion,
            position=1,
        )

        assert [item.pk for item in moved] == [second.pk, fourth.pk]
        assert [post.pk for post in discussion.posts.order_by("sequence_index")] == [
            first.pk,
            second.pk,
            fourth.pk,
            third.pk,
        ]

    def test_move_discussion_items_supports_posts_and_links(self, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        source = space.root_discussion
        target = DiscussionFactory(space=space, parent=source)
        post = post_services.create_post(discussion=source, author=participant, content="Movable post")
        linked = DiscussionFactory(space=space, parent=source)
        link = Link.objects.create(discussion=source, created_by=participant, target=linked, sequence_index=1)

        moved = post_services.move_discussion_items(items=[link, post], target_discussion=target, position=0)

        assert [item.pk for item in moved] == [post.pk, link.pk]
        post.refresh_from_db()
        link.refresh_from_db()
        assert post.discussion_id == target.pk
        assert link.discussion_id == target.pk

    def test_move_discussion_items_applies_explicit_target_order(self, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        source = space.root_discussion
        target = DiscussionFactory(space=space, parent=source)
        first = post_services.create_post(discussion=source, author=participant, content="First")
        second = post_services.create_post(discussion=source, author=participant, content="Second")
        existing = post_services.create_post(discussion=target, author=participant, content="Existing")
        trailing = post_services.create_post(discussion=target, author=participant, content="Trailing")

        moved = post_services.move_discussion_items(
            items=[first, second],
            target_discussion=target,
            target_order_ids=[existing.pk, second.pk, trailing.pk, first.pk],
        )

        assert [item.pk for item in moved] == [second.pk, first.pk]
        assert [post.pk for post in target.posts.order_by("sequence_index")] == [
            existing.pk,
            second.pk,
            trailing.pk,
            first.pk,
        ]
