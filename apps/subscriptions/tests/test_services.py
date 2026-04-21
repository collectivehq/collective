from __future__ import annotations

import pytest

from apps.nodes.tests.factories import NodeFactory
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.subscriptions import services as sub_services
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
