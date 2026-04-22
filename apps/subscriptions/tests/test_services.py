from __future__ import annotations

import pytest

from apps.discussions import services as discussion_services
from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.subscriptions.models import Notification
from apps.subscriptions.notification_services import get_notifications_for_user
from apps.subscriptions.subscription_services import is_subscribed, subscribe, unsubscribe
from apps.users.tests.factories import UserFactory


@pytest.fixture
def space_participant_node():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    joiner = UserFactory()
    participant = space_services.join_space(space=space, user=joiner)
    discussion = DiscussionFactory(space=space)
    return space, participant, discussion


@pytest.mark.django_db
class TestSubscribe:
    def test_subscribe(self, space_participant_node):
        _, participant, discussion = space_participant_node
        sub = subscribe(user=participant.user, discussion=discussion)
        assert sub.pk is not None

    def test_subscribe_idempotent(self, space_participant_node):
        _, participant, discussion = space_participant_node
        sub1 = subscribe(user=participant.user, discussion=discussion)
        sub2 = subscribe(user=participant.user, discussion=discussion)
        assert sub1.pk == sub2.pk


@pytest.mark.django_db
class TestUnsubscribe:
    def test_unsubscribe(self, space_participant_node):
        _, participant, discussion = space_participant_node
        subscribe(user=participant.user, discussion=discussion)
        unsubscribe(user=participant.user, discussion=discussion)
        assert not is_subscribed(user=participant.user, discussion=discussion)


@pytest.mark.django_db
class TestIsSubscribed:
    def test_not_subscribed(self, space_participant_node):
        _, participant, discussion = space_participant_node
        assert not is_subscribed(user=participant.user, discussion=discussion)

    def test_subscribed(self, space_participant_node):
        _, participant, discussion = space_participant_node
        subscribe(user=participant.user, discussion=discussion)
        assert is_subscribed(user=participant.user, discussion=discussion)


@pytest.mark.django_db(transaction=True)
class TestNotifications:
    def test_creates_notification_for_subscribed_participant_when_new_post_is_added(self):
        creator = UserFactory()
        author = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space.participants.select_related("role").filter(user=creator).first()
        assert subscriber is not None
        space_services.join_space(space=space, user=author)
        root = space.root_discussion
        subscribe(user=subscriber.user, discussion=root)

        post_services.create_post(discussion=root, author=author, content="Hello subscribers")

        notification = Notification.objects.get(recipient=subscriber.user)
        assert notification.event_type == Notification.EventType.POST_CREATED

    def test_draft_post_does_not_create_notification(self):
        creator = UserFactory()
        author = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space.participants.select_related("role").filter(user=creator).first()
        assert subscriber is not None
        space_services.join_space(space=space, user=author)
        root = space.root_discussion
        subscribe(user=subscriber.user, discussion=root)

        post_services.create_post(discussion=root, author=author, content="Secret", is_draft=True)

        assert not Notification.objects.exists()

    def test_resolve_discussion_creates_notification(self):
        creator = UserFactory()
        resolver = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space.participants.select_related("role").filter(user=creator).first()
        assert subscriber is not None
        space_services.join_space(space=space, user=resolver)
        root = space.root_discussion
        subscribe(user=subscriber.user, discussion=root)

        discussion_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=resolver)

        notification = Notification.objects.get(recipient=subscriber.user)
        assert notification.event_type == Notification.EventType.DISCUSSION_RESOLVED
        assert notification.resolution_type == "accept"

    def test_resolution_notification_title_uses_human_readable_past_tense(self):
        creator = UserFactory()
        resolver = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space.participants.select_related("role").filter(user=creator).first()
        assert subscriber is not None
        space_services.join_space(space=space, user=resolver)
        root = space.root_discussion
        subscribe(user=subscriber.user, discussion=root)

        discussion_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=resolver)

        notification = Notification.objects.get(recipient=subscriber.user)
        expected_actor_name = resolver.name or resolver.email
        assert notification.title() == f"{expected_actor_name} accepted {root.label}"

    def test_post_created_notification_preview_uses_original_content_after_edit(self):
        creator = UserFactory()
        author = UserFactory()
        space = space_services.create_space(title="Test", created_by=creator)
        space_services.open_space(space=space)
        subscriber = space.participants.select_related("role").filter(user=creator).first()
        assert subscriber is not None
        space_services.join_space(space=space, user=author)
        root = space.root_discussion
        subscribe(user=subscriber.user, discussion=root)

        post = post_services.create_post(discussion=root, author=author, content="Original body")
        notification = Notification.objects.get(recipient=subscriber.user)

        post_services.update_post(post=post, content="Edited body", actor=author)

        notification = get_notifications_for_user(user=creator).get(pk=notification.pk)
        assert notification.preview() == "Original body"
