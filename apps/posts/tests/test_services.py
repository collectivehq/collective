from __future__ import annotations

import pytest

from apps.posts import services as post_services


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
