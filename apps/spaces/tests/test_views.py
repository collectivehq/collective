from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.posts import services as post_services
from apps.spaces import services as space_services
from apps.spaces.constants import PERMISSION_LABELS
from apps.spaces.models import Role, Space, SpaceInvite, SpaceParticipant
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

    def test_hides_invite_only_spaces_from_open_spaces(self):
        creator = UserFactory()
        open_space = space_services.create_space(title="Open Space", created_by=creator)
        private_space = space_services.create_space(
            title="Private Space",
            created_by=creator,
            is_public=False,
        )
        space_services.open_space(space=open_space)
        space_services.open_space(space=private_space)
        c = Client()

        response = c.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"Open Space" in response.content
        assert b"Private Space" not in response.content

    def test_shows_closed_and_archived_public_spaces(self, client):
        creator = UserFactory()
        closed_space = space_services.create_space(title="Closed Space", created_by=creator)
        archived_space = space_services.create_space(title="Archived Space", created_by=creator)
        space_services.open_space(space=closed_space)
        space_services.open_space(space=archived_space)
        closed_space.lifecycle = Space.Lifecycle.CLOSED
        closed_space.save(update_fields=["lifecycle"])
        archived_space.lifecycle = Space.Lifecycle.ARCHIVED
        archived_space.save(update_fields=["lifecycle"])

        response = client.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"Public Spaces" in response.content
        assert b"Closed Space" in response.content
        assert b"Archived Space" in response.content

    def test_renders_empty_state_for_anonymous_user_when_no_spaces_exist(self, client):
        response = client.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"No spaces yet" in response.content
        assert b"Create account" in response.content

    def test_renders_empty_state_for_authenticated_user_when_no_spaces_exist(self, auth_client):
        c, user = auth_client

        response = c.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"No spaces yet" in response.content
        assert b"Use the Create Space button above to start the first one." in response.content
        assert b"Create the first space" not in response.content

    def test_renders_no_public_spaces_state_when_only_private_spaces_exist(self, client):
        creator = UserFactory()
        private_space = space_services.create_space(title="Private Space", created_by=creator, is_public=False)
        space_services.open_space(space=private_space)

        response = client.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"No public spaces available" in response.content
        assert b"No spaces yet" not in response.content
        assert b"Private Space" not in response.content

    def test_renders_simple_join_prompt_when_user_has_joined_nothing(self, auth_client):
        c, user = auth_client
        creator = UserFactory()
        open_space = space_services.create_space(title="Open Space", created_by=creator)
        space_services.open_space(space=open_space)

        response = c.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"You have not joined any spaces yet." in response.content
        assert b"Open Space" in response.content
        assert b"Pick your first space" not in response.content

    def test_does_not_render_extra_empty_state_when_only_participating_spaces_exist(self, open_space_with_client):
        c, creator, space = open_space_with_client

        response = c.get(reverse("spaces:list"))

        assert response.status_code == 200
        assert b"Your Spaces" in response.content
        assert b"Closed or Archived Public Spaces" not in response.content
        assert b"No public spaces yet" not in response.content


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
        response = c.post(reverse("spaces:create"), {"title": "New Space", "description": "Desc", "is_public": "on"})
        assert response.status_code == 302
        assert Space.objects.filter(title="New Space").exists()

    def test_create_private_space(self, auth_client):
        c, user = auth_client

        response = c.post(reverse("spaces:create"), {"title": "Private Space", "description": "Desc"})

        assert response.status_code == 302
        assert Space.objects.get(title="Private Space").is_public is False

    def test_create_space_with_information(self, auth_client):
        c, user = auth_client
        response = c.post(
            reverse("spaces:create"),
            {"title": "Rich Space", "description": "Desc", "information": "<p>Welcome</p>", "is_public": "on"},
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

    def test_space_sidebar_shows_about_this_space_action(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"About this space" in response.content

    def test_sidebar_title_selects_root_discussion(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert (
            f"window.selectTreeNode && window.selectTreeNode('{space.root_discussion.pk}')".encode() in response.content
        )

    def test_detail_from_outside_space_autoloads_about_modal(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(
            reverse("spaces:detail", kwargs={"space_id": space.pk}),
            HTTP_REFERER="http://testserver" + reverse("spaces:list"),
        )

        assert response.status_code == 200
        assert b'id="aboutSpaceModalAutoload"' in response.content

    def test_detail_from_within_space_does_not_autoload_about_modal(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(
            reverse("spaces:detail", kwargs={"space_id": space.pk}),
            HTTP_REFERER="http://testserver" + reverse("spaces:settings", kwargs={"space_id": space.pk}),
        )

        assert response.status_code == 200
        assert b"aboutSpaceModal" in response.content
        assert b'id="aboutSpaceModalAutoload"' not in response.content

    def test_non_participant_redirected_to_join(self, open_space_with_client):
        _, _, space = open_space_with_client
        outsider = UserFactory()
        c = Client()
        c.force_login(outsider)
        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))
        assert response.status_code == 302

    def test_non_participant_gets_404_for_private_space(self):
        creator = UserFactory()
        outsider = UserFactory()
        space = space_services.create_space(title="Private", created_by=creator, is_public=False)
        space_services.open_space(space=space)
        c = Client()
        c.force_login(outsider)

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 404

    def test_regular_participant_sees_participants_link(self):
        creator = UserFactory()
        space = space_services.create_space(title="Open", created_by=creator)
        space_services.open_space(space=space)
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        c = Client()
        c.force_login(joiner)

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Participants" in response.content

    def test_requires_login(self, client, open_space_with_client):
        _, _, space = open_space_with_client
        response = client.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))
        assert response.status_code == 302


@pytest.mark.django_db
class TestSpaceJoinView:
    def test_join_page_renders_simple_summary(self, open_space_with_client):
        _, _, space = open_space_with_client
        joiner = UserFactory()
        c = Client()
        c.force_login(joiner)

        response = c.get(reverse("spaces:join", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert space.title.encode() in response.content
        assert b"Public" in response.content
        assert b"discussions" in response.content
        assert b"participants" in response.content
        assert b"\xe2\x86\x90 Back to spaces" in response.content

    def test_join_page_shows_information(self, open_space_with_client):
        _, _, space = open_space_with_client
        space.information = "<p>Welcome</p><script>alert(1)</script>"
        space.save(update_fields=["information"])
        joiner = UserFactory()
        c = Client()
        c.force_login(joiner)

        response = c.get(reverse("spaces:join", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Welcome" in response.content
        assert b"<script>" not in response.content

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

    def test_private_space_join_returns_404(self):
        creator = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Private", created_by=creator, is_public=False)
        space_services.open_space(space=space)
        c = Client()
        c.force_login(joiner)

        response = c.post(reverse("spaces:join", kwargs={"space_id": space.pk}))

        assert response.status_code == 404
        assert not Space.objects.get(pk=space.pk).participants.filter(user=joiner).exists()


@pytest.mark.django_db
class TestSpaceSettingsView:
    def test_host_can_access_settings(self, open_space_with_client):
        c, _, space = open_space_with_client
        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))
        assert response.status_code == 200

    def test_settings_editor_includes_upload_url_for_information_field(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert reverse("posts:image_upload", kwargs={"space_id": space.pk}).encode() in response.content

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

    def test_host_can_disable_open_join(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.post(
            reverse("spaces:settings", kwargs={"space_id": space.pk}),
            {
                "title": space.title,
                "description": space.description,
                "information": space.information,
                "starts_at": "",
                "ends_at": "",
                "opinion_types": list(space.opinion_types),
                "reaction_types": list(space.reaction_types),
                "edit_window_minutes": "",
            },
        )

        assert response.status_code == 302
        space.refresh_from_db()
        assert space.is_public is False


@pytest.mark.django_db
class TestSpaceLifecycleUpdateView:
    def test_open_space_shows_confirmation_dialog_for_close(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b'id="lifecycleDialog-closed"' in response.content
        assert b"Close space?" in response.content

    def test_closed_space_shows_confirmation_dialogs_for_open_and_archive(self, open_space_with_client):
        c, _, space = open_space_with_client
        space_services.transition_space_lifecycle(space=space, lifecycle=Space.Lifecycle.CLOSED)

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b'id="lifecycleDialog-open"' in response.content
        assert b"Open space?" in response.content
        assert b'id="lifecycleDialog-archived"' in response.content
        assert b"Archive space?" in response.content

    def test_close_only_role_can_update_lifecycle(self):
        creator = UserFactory()
        closer = UserFactory()
        space = space_services.create_space(title="Closable", created_by=creator)
        space_services.open_space(space=space)
        close_role = Role.objects.create(
            space=space,
            created_by=creator,
            label="Closer",
            can_post=False,
            can_create_draft=False,
            can_delete_own_post=False,
            can_view_history=True,
            can_opine=False,
            can_react=False,
            can_close_space=True,
        )
        SpaceParticipant.objects.create(space=space, user=closer, role=close_role, created_by=creator)
        c = Client()
        c.force_login(closer)

        response = c.post(
            reverse("spaces:lifecycle_update", kwargs={"space_id": space.pk}),
            {"lifecycle": Space.Lifecycle.CLOSED},
        )

        assert response.status_code == 302
        space.refresh_from_db()
        assert space.lifecycle == Space.Lifecycle.CLOSED

    def test_close_only_role_cannot_access_settings(self):
        creator = UserFactory()
        closer = UserFactory()
        space = space_services.create_space(title="Closable", created_by=creator)
        close_role = Role.objects.create(
            space=space,
            created_by=creator,
            label="Closer",
            can_post=False,
            can_create_draft=False,
            can_delete_own_post=False,
            can_view_history=True,
            can_opine=False,
            can_react=False,
            can_close_space=True,
        )
        SpaceParticipant.objects.create(space=space, user=closer, role=close_role, created_by=creator)
        c = Client()
        c.force_login(closer)

        response = c.get(reverse("spaces:settings", kwargs={"space_id": space.pk}))

        assert response.status_code == 302

    def test_archived_space_shows_unarchive_action(self):
        creator = UserFactory()
        c = Client()
        c.force_login(creator)
        space = space_services.create_space(title="Archived", created_by=creator)
        space_services.open_space(space=space)
        space_services.transition_space_lifecycle(space=space, lifecycle=Space.Lifecycle.CLOSED)
        space_services.transition_space_lifecycle(space=space, lifecycle=Space.Lifecycle.ARCHIVED)

        response = c.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Unarchive space" in response.content
        assert b'id="lifecycleDialog-closed"' in response.content
        assert b"Unarchive space?" in response.content

    def test_can_unarchive_space(self):
        creator = UserFactory()
        c = Client()
        c.force_login(creator)
        space = space_services.create_space(title="Archived", created_by=creator)
        space_services.open_space(space=space)
        space_services.transition_space_lifecycle(space=space, lifecycle=Space.Lifecycle.CLOSED)
        space_services.transition_space_lifecycle(space=space, lifecycle=Space.Lifecycle.ARCHIVED)

        response = c.post(
            reverse("spaces:lifecycle_update", kwargs={"space_id": space.pk}),
            {"lifecycle": Space.Lifecycle.CLOSED},
        )

        assert response.status_code == 302
        space.refresh_from_db()
        assert space.lifecycle == Space.Lifecycle.CLOSED


@pytest.mark.django_db
class TestSpaceParticipantsView:
    def test_participant_can_view(self, open_space_with_client):
        c, _, space = open_space_with_client
        response = c.get(reverse("spaces:participants", kwargs={"space_id": space.pk}))
        assert response.status_code == 200

    def test_permission_manager_sees_role_save_button_for_other_participants(self, open_space_with_client):
        c, _, space = open_space_with_client
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        participant = space.participants.get(user=joiner)

        response = c.get(reverse("spaces:participants", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Save" in response.content
        assert (
            reverse(
                "spaces:participant_role_update",
                kwargs={"space_id": space.pk, "participant_id": participant.pk},
            ).encode()
            in response.content
        )

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

    def test_success_message_falls_back_to_email_when_name_blank(self, open_space_with_client):
        c, _, space = open_space_with_client
        joiner = UserFactory(name="")
        space_services.join_space(space=space, user=joiner)
        participant = Space.objects.get(pk=space.pk).participants.get(user=joiner)
        observer = Role.objects.get(space=space, label="Observer")

        response = c.post(
            reverse("spaces:participant_role_update", kwargs={"space_id": space.pk, "participant_id": participant.pk}),
            {"role_id": str(observer.pk)},
            follow=True,
        )

        assert response.status_code == 200
        messages = [message.message for message in get_messages(response.wsgi_request)]
        assert f'Updated role for "{joiner.email}".' in messages

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
class TestSpacePermissionsView:
    def test_permissions_page_shows_color_filter_presets(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:permissions", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b'class="filter"' in response.content
        assert b'aria-label="None"' in response.content
        assert b'aria-label="Amber"' in response.content
        assert b'aria-label="Lavender"' in response.content

    def test_permissions_page_groups_permissions(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:permissions", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b'class="fieldset bg-base-200 border border-base-300 rounded-box p-4"' in response.content
        assert b"Participation" in response.content
        assert b"Discussion Structure" in response.content
        assert b"Resolution" in response.content
        assert b"Moderation" in response.content
        assert b"Administration" in response.content

    def test_permissions_page_omits_upload_images_permission(self, open_space_with_client):
        c, _, space = open_space_with_client

        response = c.get(reverse("spaces:permissions", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Upload images" not in response.content

    def test_role_update_can_set_post_highlight_color(self, open_space_with_client):
        c, _, space = open_space_with_client
        role = Role.objects.get(space=space, label="Member")
        payload = {"label": role.label, "post_highlight_color": "#c4b5fd"}
        payload.update({field: "on" for field in PERMISSION_LABELS if getattr(role, field)})

        response = c.post(
            reverse("spaces:role_update", kwargs={"space_id": space.pk, "role_id": role.pk}),
            payload,
        )

        assert response.status_code == 302
        role.refresh_from_db()
        assert role.post_highlight_color == "#C4B5FD"

    def test_role_update_rejects_invalid_post_highlight_color(self, open_space_with_client):
        c, _, space = open_space_with_client
        role = Role.objects.get(space=space, label="Member")

        response = c.post(
            reverse("spaces:role_update", kwargs={"space_id": space.pk, "role_id": role.pk}),
            {"label": role.label, "post_highlight_color": "not-a-color"},
        )

        assert response.status_code == 302
        role.refresh_from_db()
        assert role.post_highlight_color == ""


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

    def test_invite_accept_get_uses_shared_join_page(self, open_space_with_client):
        _, creator, space = open_space_with_client
        joiner = UserFactory()
        invite = SpaceInvite.objects.create(
            space=space,
            role=space.default_role,
            created_by=creator,
        )
        c = Client()
        c.force_login(joiner)

        response = c.get(reverse("spaces:invite_accept", kwargs={"space_id": space.pk, "invite_id": invite.pk}))

        assert response.status_code == 200
        assert b"Accept & Join" in response.content
        assert f"Invite role: {invite.role.label}".encode() in response.content

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

    def test_invite_accept_allows_joining_invite_only_space(self, open_space_with_client):
        _, creator, space = open_space_with_client
        joiner = UserFactory()
        space.is_public = False
        space.save(update_fields=["is_public"])
        invite = SpaceInvite.objects.create(
            space=space,
            role=space.default_role,
            created_by=creator,
        )
        c = Client()
        c.force_login(joiner)

        response = c.post(reverse("spaces:invite_accept", kwargs={"space_id": space.pk, "invite_id": invite.pk}))

        assert response.status_code == 302
        assert response.url == reverse("spaces:detail", kwargs={"space_id": space.pk})
        assert Space.objects.get(pk=space.pk).participants.filter(user=joiner).exists()
