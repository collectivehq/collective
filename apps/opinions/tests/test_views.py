from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.nodes import services as node_services
from apps.nodes.tests.factories import NodeFactory
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def participant_client():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    joiner = UserFactory()
    participant = space_services.join_space(space=space, user=joiner)
    node = NodeFactory(space=space)
    c = Client()
    c.force_login(joiner)
    return c, space, participant, node


@pytest.mark.django_db
class TestCastOpinionView:
    def test_toggle_opinion(self, participant_client):
        c, space, participant, node = participant_client
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "node_id": node.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 200

    def test_missing_type(self, participant_client):
        c, space, _, node = participant_client
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "node_id": node.pk}),
            {},
        )
        assert response.status_code == 400

    def test_non_participant_denied(self, participant_client):
        _, space, _, node = participant_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "node_id": node.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 403

    def test_requires_login(self, participant_client):
        _, space, _, node = participant_client
        anon = Client()
        response = anon.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "node_id": node.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 302

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_opinion(self, participant_client):
        cache.clear()
        c, space, _, node = participant_client
        url = reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "node_id": node.pk})

        first = c.post(url, {"type": "agree"})
        second = c.post(url, {"type": "disagree"})

        assert first.status_code == 200
        assert second.status_code == 429


@pytest.mark.django_db
class TestToggleReactionView:
    def test_toggle_reaction(self, participant_client):
        c, space, participant, node = participant_client
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        response = c.post(
            reverse("opinions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 200

    def test_non_participant_denied(self, participant_client):
        _, space, participant, node = participant_client
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.post(
            reverse("opinions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 403

    def test_requires_login(self, participant_client):
        _, space, participant, node = participant_client
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        anon = Client()
        response = anon.post(
            reverse("opinions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 302

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_reaction(self, participant_client):
        cache.clear()
        c, space, participant, node = participant_client
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        url = reverse("opinions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk})

        first = c.post(url, {"type": "like"})
        second = c.post(url, {"type": "dislike"})

        assert first.status_code == 200
        assert second.status_code == 429
