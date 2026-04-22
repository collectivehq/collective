from __future__ import annotations

import pytest
from django.urls import reverse

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services


@pytest.mark.django_db
class TestDiscussionDetailView:
    def test_authenticated_participant_can_view_discussion(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200

    def test_unauthenticated_user_is_redirected(self, client, open_space_with_users) -> None:
        space, _, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 302

    def test_renders_subdiscussion_child_count(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        sub_discussion = DiscussionFactory(space=space, parent=discussion)
        nested = DiscussionFactory(space=space, parent=sub_discussion)
        post_services.create_post(discussion=sub_discussion, author=participant, content="Hello")
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert nested.label.encode() not in response.content
        assert b"2 children" in response.content
