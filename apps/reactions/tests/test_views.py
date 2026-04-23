from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.posts import services as post_services
from apps.reactions import services as reaction_services
from apps.spaces import services as space_services
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestToggleReactionView:
    def test_toggle_reaction(self, participant_client):
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 200
        assert b'data-role="visible-like-reaction"' in response.content
        assert b'data-role="reaction-trigger"' in response.content
        assert b'data-role="visible-dislike-reaction"' not in response.content

    def test_discussion_detail_shows_only_trigger_when_no_reactions(self, participant_client):
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": node.pk},
            )
        )

        assert response.status_code == 200
        assert b'id="reactions-' + str(post.pk).encode() + b'"' in response.content
        assert b'data-role="reaction-trigger"' in response.content
        assert b'data-role="visible-like-reaction"' not in response.content
        assert b'data-role="visible-dislike-reaction"' not in response.content

    def test_toggle_reaction_hides_trigger_when_like_and_dislike_are_visible(self, participant_client):
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        reactor = UserFactory()
        space_services.join_space(space=space, user=reactor)
        reaction_services.toggle_reaction(user=reactor, post=post, reaction_type="dislike")

        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )

        assert response.status_code == 200
        assert b'data-role="visible-like-reaction"' in response.content
        assert b'data-role="visible-dislike-reaction"' in response.content
        assert b'data-role="reaction-trigger"' not in response.content

    def test_non_participant_denied(self, participant_client):
        _, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        outsider = UserFactory()
        client = Client()
        client.force_login(outsider)
        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 403

    def test_facilitator_can_toggle_reaction_in_closed_space(self, participant_client):
        _, space, participant, node = participant_client
        client = Client()
        client.force_login(space.created_by)
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        response = client.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )

        assert response.status_code == 200

    def test_requires_login(self, participant_client):
        _, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        anon = Client()
        response = anon.post(
            reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"type": "like"},
        )
        assert response.status_code == 302

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_reaction(self, participant_client):
        cache.clear()
        client, space, participant, node = participant_client
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        url = reverse("reactions:toggle_reaction", kwargs={"space_id": space.pk, "post_id": post.pk})

        first = client.post(url, {"type": "like"})
        second = client.post(url, {"type": "dislike"})

        assert first.status_code == 200
        assert second.status_code == 429
