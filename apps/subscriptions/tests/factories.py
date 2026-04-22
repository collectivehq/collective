from __future__ import annotations

import factory

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts.tests.factories import PostFactory
from apps.subscriptions.models import Notification, Subscription
from apps.users.tests.factories import UserFactory


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    created_by = factory.SubFactory(UserFactory)
    discussion = factory.SubFactory(DiscussionFactory)


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    created_by = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    discussion = factory.SubFactory(DiscussionFactory)
    post = factory.SubFactory(PostFactory, discussion=factory.SelfAttribute("..discussion"))
    event_type = Notification.EventType.POST_CREATED
    resolution_type = ""
