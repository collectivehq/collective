from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.nodes import services as node_services
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def auth_client():
    user = UserFactory()
    c = Client()
    c.force_login(user)
    return c, user


@pytest.fixture
def open_space_with_client():
    creator = UserFactory()
    space = space_services.create_space(title="Test Space", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    c = Client()
    c.force_login(creator)
    return c, creator, space


@pytest.mark.django_db
class TestSpaceListView:
    def test_anonymous_user(self, client):
        response = client.get(reverse("spaces:list"))
        assert response.status_code == 200

    def test_authenticated_user(self, auth_client):
        c, user = auth_client
        response = c.get(reverse("spaces:list"))
        assert response.status_code == 200

    def test_shows_participating_spaces(self, open_space_with_client):
        c, creator, space = open_space_with_client
        response = c.get(reverse("spaces:list"))
        assert space.title.encode() in response.content

    def test_orders_spaces_by_updated_at(self):
        creator = UserFactory()
        c = Client()
        c.force_login(creator)

        older = space_services.create_space(title="Older Space", created_by=creator)
        space_services.open_space(space=older)
        newer = space_services.create_space(title="Newer Space", created_by=creator)
        space_services.open_space(space=newer)

        node_services.create_post(discussion=older.root_discussion, author=creator, content="Recent activity")

        response = c.get(reverse("spaces:list"))
        html = response.content.decode()

        assert html.index("Older Space") < html.index("Newer Space")


@pytest.mark.django_db
class TestSpaceCreateView:
    def test_get_form(self, auth_client):
        c, user = auth_client
        response = c.get(reverse("spaces:create"))
        assert response.status_code == 200

    def test_get_form_shows_example_import_links(self, auth_client):
        c, user = auth_client
        response = c.get(reverse("spaces:create"))

        assert response.status_code == 200
        assert b"Download DOCX example" in response.content
        assert b"Download Markdown example" in response.content

    def test_create_space(self, auth_client):
        c, user = auth_client
        response = c.post(reverse("spaces:create"), {"title": "New Space", "description": "Desc"})
        assert response.status_code == 302
        assert Space.objects.filter(title="New Space").exists()

    def test_create_space_with_information(self, auth_client):
        c, user = auth_client
        response = c.post(
            reverse("spaces:create"),
            {"title": "Rich Space", "description": "Desc", "information": "<p>Welcome</p>"},
        )

        assert response.status_code == 302
        assert Space.objects.get(title="Rich Space").information == "<p>Welcome</p>"

    def test_requires_login(self, client):
        response = client.get(reverse("spaces:create"))
        assert response.status_code == 302
        assert "login" in response.url or "account" in response.url


@pytest.mark.django_db
class TestSpaceDetailView:
    def test_participant_sees_detail(self, open_space_with_client):
        c, creator, space = open_space_with_client
        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))
        assert response.status_code == 200

    def test_renders_information_and_modal_autoload(self, open_space_with_client):
        c, _, space = open_space_with_client
        space.information = "<p>Welcome</p><script>alert(1)</script>"
        space.save(update_fields=["information"])

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"aboutSpaceModal" in response.content
        assert b"showModal" in response.content
        assert b"Welcome" in response.content

    def test_non_participant_redirected_to_join(self, open_space_with_client):
        _, _, space = open_space_with_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))
        assert response.status_code == 302

    def test_requires_login(self, client, open_space_with_client):
        _, _, space = open_space_with_client
        response = client.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))
        assert response.status_code == 302


@pytest.mark.django_db
class TestSpaceJoinView:
    def test_join_space(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        c = Client()
        c.force_login(joiner)
        response = c.post(reverse("spaces:join", kwargs={"space_id": space.pk}))
        assert response.status_code == 302
        assert space_services.get_participant(space=space, user=joiner) is not None

    def test_already_participant_redirects(self, open_space_with_client):
        c, creator, space = open_space_with_client
        response = c.post(reverse("spaces:join", kwargs={"space_id": space.pk}))
        assert response.status_code == 302

    def test_closed_space_redirects(self, open_space_with_client):
        _, _, space = open_space_with_client
        space_services.close_space(space=space)
        joiner = UserFactory()
        c = Client()
        c.force_login(joiner)
        response = c.get(reverse("spaces:join", kwargs={"space_id": space.pk}))
        assert response.status_code == 302


@pytest.mark.django_db
class TestSpaceSettingsView:
    def test_host_can_access_settings(self, open_space_with_client):
        c, _, space = open_space_with_client
        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))
        assert response.status_code == 200

    def test_settings_uses_filter_reset_buttons_and_full_width_range(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b'aria-label="Reset Opinion types"' in response.content
        assert b'aria-label="Reset Reaction types"' in response.content
        assert b'id="edit-window-range"' in response.content
        assert b"range range-sm range-primary w-full" in response.content

    def test_participant_denied(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        c = Client()
        c.force_login(joiner)
        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))
        assert response.status_code == 302


@pytest.mark.django_db
class TestSpaceParticipantsView:
    def test_participant_can_view(self, open_space_with_client):
        c, _, space = open_space_with_client
        response = c.get(reverse("spaces:participants", kwargs={"space_id": space.pk}))
        assert response.status_code == 200

    def test_non_participant_denied(self, open_space_with_client):
        _, _, space = open_space_with_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.get(reverse("spaces:participants", kwargs={"space_id": space.pk}))
        assert response.status_code == 403

    def test_requires_login(self, open_space_with_client):
        _, _, space = open_space_with_client
        anon = Client()
        response = anon.get(reverse("spaces:participants", kwargs={"space_id": space.pk}))
        assert response.status_code == 302


@pytest.mark.django_db
class TestParticipantRemoveView:
    def test_moderator_can_remove(self, open_space_with_client):
        c, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        participant = space_services.get_participant(space=space, user=joiner)
        response = c.post(
            reverse("spaces:participant_remove", kwargs={"space_id": space.pk, "participant_id": participant.pk})
        )
        assert response.status_code == 302
        assert space_services.get_participant(space=space, user=joiner) is None

    def test_non_moderator_denied(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        joiner2 = UserFactory()
        space_services.join_space(space=space, user=joiner2)
        participant = space_services.get_participant(space=space, user=joiner2)
        c = Client()
        c.force_login(joiner)
        response = c.post(
            reverse("spaces:participant_remove", kwargs={"space_id": space.pk, "participant_id": participant.pk})
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestParticipantRoleUpdateView:
    def test_host_can_update_role(self, open_space_with_client):
        c, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        participant = space_services.get_participant(space=space, user=joiner)
        from apps.spaces.models import Role

        observer = Role.objects.filter(space=space, label="Observer").first()
        response = c.post(
            reverse("spaces:participant_role_update", kwargs={"space_id": space.pk, "participant_id": participant.pk}),
            {"role_id": str(observer.pk)},
        )
        assert response.status_code == 302
        participant.refresh_from_db()
        assert participant.role.label == "Observer"

    def test_non_permission_user_denied(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        joiner2 = UserFactory()
        space_services.join_space(space=space, user=joiner2)
        participant = space_services.get_participant(space=space, user=joiner2)
        c = Client()
        c.force_login(joiner)
        from apps.spaces.models import Role

        observer = Role.objects.filter(space=space, label="Observer").first()
        response = c.post(
            reverse("spaces:participant_role_update", kwargs={"space_id": space.pk, "participant_id": participant.pk}),
            {"role_id": str(observer.pk)},
        )
        assert response.status_code == 403
