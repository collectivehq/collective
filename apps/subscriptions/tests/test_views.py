from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.nodes import services as node_services
from apps.nodes.tests.factories import NodeFactory
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.subscriptions import services as sub_services
from apps.subscriptions.models import Notification
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


@pytest.fixture
def notifications_client():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    author = UserFactory()
    space_services.join_space(space=space, user=author)
    subscriber = space_services.get_participant(space=space, user=creator)
    assert subscriber is not None
    root = space.root_discussion
    sub_services.subscribe(participant=subscriber, node=root)
    node_services.create_post(discussion=root, author=author, content="Hello there")
    c = Client()
    c.force_login(creator)
    return c, creator, space, root


@pytest.mark.django_db(transaction=True)
class TestNotificationsCenterView:
    def test_lists_notifications(self, notifications_client):
        c, _, _, _ = notifications_client

        response = c.get(reverse("subscriptions:notifications"))

        assert response.status_code == 200
        assert b"posted in" in response.content

    def test_open_marks_notification_read(self, notifications_client):
        c, _, space, root = notifications_client
        notification = Notification.objects.get()

        response = c.get(reverse("subscriptions:notification_open", kwargs={"notification_id": notification.pk}))

        assert response.status_code == 302
        notification.refresh_from_db()
        assert notification.read_at is not None
        assert str(space.pk) in response.url
        assert str(root.pk) in response.url

    def test_mark_all_read(self, notifications_client):
        c, _, _, _ = notifications_client

        response = c.post(reverse("subscriptions:notification_mark_all_read"))

        assert response.status_code == 302
        assert Notification.objects.filter(read_at__isnull=True).count() == 0
