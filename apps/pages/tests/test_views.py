from __future__ import annotations

from django.urls import reverse


class TestLandingView:
    def test_landing_route_uses_pages_namespace(self, client):
        response = client.get(reverse("pages:home"))

        assert response.status_code == 200
        assert any(template.name == "pages/landing.html" for template in response.templates)

    def test_authenticated_users_are_redirected_to_spaces_list(self, client, db, user):
        client.force_login(user)

        response = client.get(reverse("pages:home"))

        assert response.status_code == 302
        assert response.headers["Location"] == reverse("spaces:list")

    def test_landing_links_guests_to_public_spaces(self, client):
        response = client.get(reverse("pages:home"))

        assert response.status_code == 200
        assert reverse("spaces:list").encode() in response.content


class TestBaseTemplate:
    def test_brand_link_points_home_for_guests(self, client):
        response = client.get(reverse("pages:home"))

        assert response.status_code == 200
        assert f'href="{reverse("pages:home")}"'.encode() in response.content
