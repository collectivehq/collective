from __future__ import annotations

import pytest
from django.urls import reverse

from apps.posts import services as post_services


@pytest.mark.django_db
class TestPostCreateView:
    def test_participant_can_create_post(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Hello world"},
        )

        assert response.status_code == 200

    def test_empty_content_is_rejected(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": ""},
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestPostPublishView:
    def test_unauthenticated_user_is_redirected(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )

        response = client.post(reverse("posts:post_publish", kwargs={"space_id": space.pk, "post_id": draft.pk}))

        assert response.status_code == 302
