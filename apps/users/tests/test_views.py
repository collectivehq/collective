from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestProfileView:
    def test_profile_requires_login(self, client) -> None:
        response = client.get(reverse("users:profile"))

        assert response.status_code == 302

    def test_profile_renders_for_authenticated_user(self, client, user) -> None:
        client.force_login(user)

        response = client.get(reverse("users:profile"))

        assert response.status_code == 200
