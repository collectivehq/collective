from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestCastOpinionView:
    def test_toggle_opinion(self, participant_client):
        c, space, participant, discussion = participant_client
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "discussion_id": discussion.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 200

    def test_missing_type(self, participant_client):
        c, space, _, discussion = participant_client
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "discussion_id": discussion.pk}),
            {},
        )
        assert response.status_code == 400

    def test_non_participant_denied(self, participant_client):
        _, space, _, discussion = participant_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "discussion_id": discussion.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 403

    def test_requires_login(self, participant_client):
        _, space, _, discussion = participant_client
        anon = Client()
        response = anon.post(
            reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "discussion_id": discussion.pk}),
            {"type": "agree"},
        )
        assert response.status_code == 302

    @override_settings(TOGGLE_RATE_LIMIT_MAX_ATTEMPTS=1, TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_rate_limits_toggle_opinion(self, participant_client):
        cache.clear()
        c, space, _, discussion = participant_client
        url = reverse("opinions:toggle_opinion", kwargs={"space_id": space.pk, "discussion_id": discussion.pk})

        first = c.post(url, {"type": "agree"})
        second = c.post(url, {"type": "disagree"})

        assert first.status_code == 200
        assert second.status_code == 429
