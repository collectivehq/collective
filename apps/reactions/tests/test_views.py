from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.posts import services as post_services
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestToggleReactionView:
    def test_toggle_reaction(self, participant_client):
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 200

    def test_non_participant_denied(self, participant_client):
        _, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        outsider = UserFactory()
        client = Client()
        client.force_login(outsider)
        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 403

    def test_requires_login(self, participant_client):
        _, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        anon = Client()
        response = anon.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 302

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_reaction(self, participant_client):
        cache.clear()
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        url = reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk})

        first = client.post(url, {"type": "like"})
        second = client.post(url, {"type": "dislike"})

        assert first.status_code == 200
        assert second.status_code == 429
