from __future__ import annotations

import pytest
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.posts import services as post_services
from apps.spaces import services as space_services
from apps.spaces.models import Space, SpaceInvite
from apps.users.tests.factories import UserFactory


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

        post_services.create_post(discussion=older.root_discussion, author=creator, content="Recent activity")

        response = c.get(reverse("spaces:list"))
        html = response.content.decode()

        assert html.index("Older Space") < html.index("Newer Space")

    def test_hides_not_yet_active_open_spaces(self):
        creator = UserFactory()
        active_space = space_services.create_space(title="Active Space", created_by=creator)
        space_services.open_space(space=active_space)
        future_space = space_services.create_space(
            title="Future Space",
            created_by=creator,
            starts_at=timezone.now() + timezone.timedelta(hours=1),
        )
        space_services.open_space(space=future_space)
        c = Client()

        response = c.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"Active Space" in response.content
        assert b"Future Space" not in response.content


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
        assert Space.objects.get(pk=space.pk).participants.filter(user=joiner).exists()

    def test_already_participant_redirects(self, open_space_with_client):
        c, creator, space = open_space_with_client
        response = c.post(reverse("spaces:join", kwargs={"space_id": space.pk}))
        assert response.status_code == 302

    def test_closed_space_redirects(self, open_space_with_client):
        _, _, space = open_space_with_client
        space.lifecycle = Space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        joiner = UserFactory()
        c = Client()
        c.force_login(joiner)
        response = c.get(reverse("spaces:join", kwargs={"space_id": space.pk}))
        assert response.status_code == 302

    def test_future_space_redirects(self):
        creator = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(
            title="Scheduled",
            created_by=creator,
            starts_at=timezone.now() + timezone.timedelta(hours=1),
        )
        space_services.open_space(space=space)
        c = Client()
        c.force_login(joiner)

        response = c.post(reverse("spaces:join", kwargs={"space_id": space.pk}))

        assert response.status_code == 302
        assert response.url == reverse("spaces:list")
        assert not Space.objects.get(pk=space.pk).participants.filter(user=joiner).exists()


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
        participant = Space.objects.get(pk=space.pk).participants.filter(user=joiner).first()
        response = c.post(
            reverse("spaces:participant_remove", kwargs={"space_id": space.pk, "participant_id": participant.pk})
        )
        assert response.status_code == 302
        assert not Space.objects.get(pk=space.pk).participants.filter(user=joiner).exists()

    def test_non_moderator_denied(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        joiner2 = UserFactory()
        space_services.join_space(space=space, user=joiner2)
        participant = Space.objects.get(pk=space.pk).participants.filter(user=joiner2).first()
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
        participant = Space.objects.get(pk=space.pk).participants.filter(user=joiner).first()
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
        participant = Space.objects.get(pk=space.pk).participants.filter(user=joiner2).first()
        c = Client()
        c.force_login(joiner)
        from apps.spaces.models import Role

        observer = Role.objects.filter(space=space, label="Observer").first()
        response = c.post(
            reverse("spaces:participant_role_update", kwargs={"space_id": space.pk, "participant_id": participant.pk}),
            {"role_id": str(observer.pk)},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestInviteViews:
    @override_settings(INVITE_DEFAULT_EXPIRY_DAYS=3)
    def test_invite_create_sets_expiry_from_settings(self, open_space_with_client):
        c, creator, space = open_space_with_client

        response = c.post(reverse("spaces:invite_create", kwargs={"space_id": space.pk}), {})

        assert response.status_code == 302
        invite = SpaceInvite.objects.get(space=space, created_by=creator)
        expected_date = (invite.created_at + timezone.timedelta(days=3)).date()
        assert invite.expires_at.date() == expected_date

    def test_invite_accept_rejects_expired_invite(self, open_space_with_client):
        _, creator, space = open_space_with_client
        joiner = UserFactory()
        invite = SpaceInvite.objects.create(
            space=space,
            role=space.default_role,
            created_by=creator,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        c = Client()
        c.force_login(joiner)

        response = c.post(reverse("spaces:invite_accept", kwargs={"space_id": space.pk, "invite_id": invite.pk}))

        assert response.status_code == 302
        assert response.url == reverse("spaces:list")
        assert not space.participants.filter(user=joiner).exists()

    def test_invite_accept_rejects_not_yet_active_space(self):
        creator = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(
            title="Scheduled",
            created_by=creator,
            starts_at=timezone.now() + timezone.timedelta(hours=1),
        )
        space_services.open_space(space=space)
        invite = SpaceInvite.objects.create(
            space=space,
            role=space.default_role,
            created_by=creator,
        )
        c = Client()
        c.force_login(joiner)

        response = c.post(reverse("spaces:invite_accept", kwargs={"space_id": space.pk, "invite_id": invite.pk}))

        assert response.status_code == 302
        assert response.url == reverse("spaces:list")
        assert not space.participants.filter(user=joiner).exists()
