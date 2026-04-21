from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.nodes.tests.factories import NodeFactory
from apps.spaces.tests.factories import SpaceParticipantFactory
from apps.subscriptions.models import Subscription


@pytest.mark.django_db
class TestSubscription:
    def test_create_subscription(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        sub = Subscription.objects.create(participant=participant, node=node)
        assert sub.pk is not None

    def test_str(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        sub = Subscription.objects.create(participant=participant, node=node)
        assert "subscribed" in str(sub)

    def test_unique_participant_node(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        Subscription.objects.create(participant=participant, node=node)
        with pytest.raises(IntegrityError):
            Subscription.objects.create(participant=participant, node=node)
