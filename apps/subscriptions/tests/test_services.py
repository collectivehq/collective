from __future__ import annotations

import pytest

from apps.nodes import services as node_services
from apps.nodes.tests.factories import NodeFactory
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.subscriptions import services as sub_services
from apps.subscriptions.models import Notification
from apps.users.tests.factories import UserFactory


@pytest.fixture
def space_participant_node():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    joiner = UserFactory()
    participant = space_services.join_space(space=space, user=joiner)
    node = NodeFactory(space=space)
    return space, participant, node


@pytest.mark.django_db
class TestSubscribe:
    def test_subscribe(self, space_participant_node):
        _, participant, node = space_participant_node
        sub = sub_services.subscribe(participant=participant, node=node)
        assert sub.pk is not None

    def test_subscribe_idempotent(self, space_participant_node):
        _, participant, node = space_participant_node
        sub1 = sub_services.subscribe(participant=participant, node=node)
        sub2 = sub_services.subscribe(participant=participant, node=node)
        assert sub1.pk == sub2.pk


@pytest.mark.django_db
class TestUnsubscribe:
    def test_unsubscribe(self, space_participant_node):
        _, participant, node = space_participant_node
        sub_services.subscribe(participant=participant, node=node)
        sub_services.unsubscribe(participant=participant, node=node)
        assert not sub_services.is_subscribed(participant=participant, node=node)


@pytest.mark.django_db
class TestIsSubscribed:
    def test_not_subscribed(self, space_participant_node):
        _, participant, node = space_participant_node
        assert not sub_services.is_subscribed(participant=participant, node=node)

    def test_subscribed(self, space_participant_node):
        _, participant, node = space_participant_node
        sub_services.subscribe(participant=participant, node=node)
        assert sub_services.is_subscribed(participant=participant, node=node)


@pytest.mark.django_db(transaction=True)
class TestNotifications:
    def test_creates_notification_for_subscribed_participant_when_new_post_is_added(self):
        creator = UserFactory()
        author = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space_services.get_participant(space=space, user=creator)
        assert subscriber is not None
        space_services.join_space(space=space, user=author)
        root = space.root_discussion
        sub_services.subscribe(participant=subscriber, node=root)

        node_services.create_post(discussion=root, author=author, content="Hello subscribers")

        notification = Notification.objects.get(participant=subscriber)
        assert notification.event_type == Notification.EventType.POST_CREATED

    def test_draft_post_does_not_create_notification(self):
        creator = UserFactory()
        author = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space_services.get_participant(space=space, user=creator)
        assert subscriber is not None
        space_services.join_space(space=space, user=author)
        root = space.root_discussion
        sub_services.subscribe(participant=subscriber, node=root)

        node_services.create_post(discussion=root, author=author, content="Secret", is_draft=True)

        assert not Notification.objects.exists()

    def test_resolve_discussion_creates_notification(self):
        creator = UserFactory()
        resolver = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space_services.get_participant(space=space, user=creator)
        assert subscriber is not None
        space_services.join_space(space=space, user=resolver)
        root = space.root_discussion
        sub_services.subscribe(participant=subscriber, node=root)

        node_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=resolver)

        notification = Notification.objects.get(participant=subscriber)
        assert notification.event_type == Notification.EventType.DISCUSSION_RESOLVED
        assert notification.resolution_type == "accept"
