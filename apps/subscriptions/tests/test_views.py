from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

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
    space_services.join_space(space=space, user=joiner)
    node = NodeFactory(space=space)
    c = Client()
    c.force_login(joiner)
    return c, space, node


@pytest.mark.django_db
class TestToggleSubscriptionView:
    def test_subscribe(self, participant_client):
        c, space, node = participant_client
        response = c.post(
            reverse("subscriptions:toggle_subscription", kwargs={"space_id": space.pk, "node_id": node.pk}),
        )
        assert response.status_code == 200

    def test_unsubscribe(self, participant_client):
        c, space, node = participant_client
        # Subscribe first
        c.post(reverse("subscriptions:toggle_subscription", kwargs={"space_id": space.pk, "node_id": node.pk}))
        # Unsubscribe
        response = c.post(
            reverse("subscriptions:toggle_subscription", kwargs={"space_id": space.pk, "node_id": node.pk}),
        )
        assert response.status_code == 200

    def test_requires_login(self, participant_client):
        _, space, node = participant_client
        anon = Client()
        response = anon.post(
            reverse("subscriptions:toggle_subscription", kwargs={"space_id": space.pk, "node_id": node.pk}),
        )
        assert response.status_code == 302

    def test_non_participant_denied(self, participant_client):
        _, space, node = participant_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.post(
            reverse("subscriptions:toggle_subscription", kwargs={"space_id": space.pk, "node_id": node.pk}),
        )
        assert response.status_code == 403
