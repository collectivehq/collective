from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse

from apps.discussions import services as discussion_services
from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.subscriptions.models import Notification
from apps.subscriptions.subscription_services import subscribe
from apps.users.tests.factories import UserFactory


@pytest.fixture
def participant_client():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    joiner = UserFactory()
    space_services.join_space(space=space, user=joiner)
    discussion = DiscussionFactory(space=space)
    c = Client()
    c.force_login(joiner)
    return c, space, discussion


@pytest.mark.django_db
class TestToggleSubscriptionView:
    def test_subscribe(self, participant_client):
        c, space, discussion = participant_client
        response = c.post(
            reverse(
                "subscriptions:toggle_subscription",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            ),
        )
        assert response.status_code == 200

    def test_unsubscribe(self, participant_client):
        c, space, discussion = participant_client
        # Subscribe first
        c.post(
            reverse(
                "subscriptions:toggle_subscription",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )
        # Unsubscribe
        response = c.post(
            reverse(
                "subscriptions:toggle_subscription",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            ),
        )
        assert response.status_code == 200

    def test_requires_login(self, participant_client):
        _, space, discussion = participant_client
        anon = Client()
        response = anon.post(
            reverse(
                "subscriptions:toggle_subscription",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            ),
        )
        assert response.status_code == 302

    def test_non_participant_denied(self, participant_client):
        _, space, discussion = participant_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.post(
            reverse(
                "subscriptions:toggle_subscription",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            ),
        )
        assert response.status_code == 403

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_subscription(self, participant_client):
        cache.clear()
        c, space, discussion = participant_client
        url = reverse(
            "subscriptions:toggle_subscription",
            kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
        )

        first = c.post(url)
        second = c.post(url)

        assert first.status_code == 200
        assert second.status_code == 429


@pytest.fixture
def notifications_client():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    author = UserFactory()
    space_services.join_space(space=space, user=author)
    subscriber = space.participants.select_related("role").filter(user=creator).first()
    assert subscriber is not None
    root = space.root_discussion
    subscribe(user=subscriber.user, discussion=root)
    post_services.create_post(discussion=root, author=author, content="Hello there")
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

    def test_resolution_notification_title_is_human_readable(self):
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

        c = Client()
        c.force_login(creator)
        response = c.get(reverse("subscriptions:notifications"))

        assert response.status_code == 200
        assert b"accepted" in response.content

    def test_post_notification_preview_uses_original_content_after_edit(self):
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
        post_services.update_post(post=post, content="Edited body", actor=author)

        c = Client()
        c.force_login(creator)
        response = c.get(reverse("subscriptions:notifications"))

        assert response.status_code == 200
        assert b"Original body" in response.content
        assert b"Edited body" not in response.content

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
