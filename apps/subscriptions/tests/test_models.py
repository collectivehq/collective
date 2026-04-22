from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.discussions.tests.factories import DiscussionFactory
from apps.subscriptions.models import Subscription
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestSubscription:
    def test_create_subscription(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        sub = Subscription.objects.create(created_by=user, discussion=discussion)
        assert sub.pk is not None

    def test_str(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        sub = Subscription.objects.create(created_by=user, discussion=discussion)
        assert "subscribed" in str(sub)

    def test_unique_participant_node(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        Subscription.objects.create(created_by=user, discussion=discussion)
        with pytest.raises(IntegrityError):
            Subscription.objects.create(created_by=user, discussion=discussion)
