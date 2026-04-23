from __future__ import annotations

import pytest
from django.urls import reverse

from apps.posts import services as post_services
from apps.spaces import services as space_services
from apps.spaces.models import Role


@pytest.mark.django_db
class TestPostCreateView:
    def test_participant_can_create_post(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Hello world"},
        )

        assert response.status_code == 200

    def test_facilitator_can_create_post_in_closed_space(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Closed post"},
        )

        assert response.status_code == 200
        assert b"Closed post" in response.content

    def test_member_cannot_create_post_in_closed_space(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Closed post"},
        )

        assert response.status_code == 403

    def test_empty_content_is_rejected(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": ""},
        )

        assert response.status_code == 400

    def test_save_draft_requires_create_draft_permission(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)
        Role.objects.filter(space=space, label="Member").update(can_create_draft=False)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Draft body", "save_draft": "true"},
        )

        assert response.status_code == 403

    def test_facilitator_can_save_draft_in_closed_space(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Closed draft", "save_draft": "true"},
        )

        assert response.status_code == 200
        assert b"Closed draft" in response.content

    def test_member_cannot_save_draft_in_closed_space(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(participant)

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk}),
            {"content": "Closed draft", "save_draft": "true"},
        )

        assert response.status_code == 403

    def test_posting_to_resolved_discussion_without_reopen_permission_leaves_resolution(
        self, client, open_space_with_users
    ) -> None:
        space, creator, participant, _ = open_space_with_users
        client.force_login(participant)
        discussion = space.root_discussion
        discussion.resolution_type = "close"
        discussion.resolved_by = creator
        discussion.save(update_fields=["resolution_type", "resolved_by"])

        response = client.post(
            reverse("posts:post_create", kwargs={"space_id": space.pk, "discussion_id": discussion.pk}),
            {"content": "Still posting"},
        )

        assert response.status_code == 200
        discussion.refresh_from_db()
        assert discussion.resolution_type == "close"


@pytest.mark.django_db
class TestPostPublishView:
    def test_unauthenticated_user_is_redirected(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )

        response = client.post(reverse("posts:post_publish", kwargs={"space_id": space.pk, "post_id": draft.pk}))

        assert response.status_code == 302

    def test_draft_publish_requires_current_post_permission(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )
        client.force_login(participant)
        Role.objects.filter(space=space, label="Member").update(can_post=False)

        response = client.post(reverse("posts:post_publish", kwargs={"space_id": space.pk, "post_id": draft.pk}))

        assert response.status_code == 403

    def test_facilitator_can_publish_another_users_draft_by_default(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )
        client.force_login(creator)

        response = client.post(reverse("posts:post_publish", kwargs={"space_id": space.pk, "post_id": draft.pk}))

        assert response.status_code == 200
        draft.refresh_from_db()
        assert draft.is_draft is False


@pytest.mark.django_db
class TestPostEditView:
    def test_draft_edit_requires_current_create_draft_permission(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )
        client.force_login(participant)
        Role.objects.filter(space=space, label="Member").update(can_create_draft=False)

        response = client.post(
            reverse("posts:post_edit", kwargs={"space_id": space.pk, "post_id": draft.pk}),
            {"content": "Updated draft"},
        )

        assert response.status_code == 403

    def test_discussion_detail_hides_publish_action_when_user_cannot_publish_draft(
        self, client, open_space_with_users
    ) -> None:
        space, _, participant, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion,
            author=participant,
            content="Draft body",
            is_draft=True,
        )
        client.force_login(participant)
        member_role = Role.objects.get(space=space, label="Member")
        member_role.can_post = False
        member_role.save(update_fields=["can_post"])
        participant_record = space.participants.get(user=participant)
        space_services.update_participant_role(participant=participant_record, role=member_role)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk},
            )
        )

        assert response.status_code == 200
        assert str(draft.pk).encode() in response.content
        assert b'data-role="publish-draft-action"' not in response.content
        assert b'name="publish"' not in response.content

    def test_closed_space_detail_shows_post_and_save_draft_for_facilitator(
        self,
        client,
        open_space_with_users,
    ) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"Save draft" in response.content
        assert b">Post</button>" in response.content

    def test_post_edit_form_hides_upload_url_when_user_cannot_upload_images(
        self,
        client,
        open_space_with_users,
    ) -> None:
        space, _, participant, _ = open_space_with_users
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Original")
        Role.objects.filter(space=space, label="Member").update(can_post=False, can_create_draft=False)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk},
            )
        )

        assert response.status_code == 200
        assert str(post.pk).encode() in response.content
        assert reverse("posts:image_upload", kwargs={"space_id": space.pk}).encode() not in response.content

    def test_facilitator_can_edit_another_users_post_by_default(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Original")
        client.force_login(creator)

        response = client.post(
            reverse("posts:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Edited by facilitator"},
        )

        assert response.status_code == 200
        post.refresh_from_db()
        assert post.content == "Edited by facilitator"

    def test_non_author_with_edit_others_permission_can_edit_post(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Original")
        client.force_login(creator)
        facilitator_role = Role.objects.get(space=space, label="Facilitator")
        facilitator_role.can_edit_others_post = True
        facilitator_role.save(update_fields=["can_edit_others_post"])

        response = client.post(
            reverse("posts:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Edited by facilitator"},
        )

        assert response.status_code == 200
        post.refresh_from_db()
        assert post.content == "Edited by facilitator"


@pytest.mark.django_db
class TestPostPermissionViews:
    def test_member_cannot_promote_post(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Hello")

        response = client.post(reverse("posts:post_promote", kwargs={"space_id": space.pk, "post_id": post.pk}))

        assert response.status_code == 403

    def test_post_revisions_requires_view_history(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)
        Role.objects.filter(space=space, label="Member").update(can_view_history=False)
        post = post_services.create_post(discussion=space.root_discussion, author=participant, content="Hello")

        response = client.get(reverse("posts:post_revisions", kwargs={"space_id": space.pk, "post_id": post.pk}))

        assert response.status_code == 403

    def test_image_upload_requires_upload_permission(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)
        Role.objects.filter(space=space, label="Member").update(can_post=False, can_create_draft=False)

        response = client.post(reverse("posts:image_upload", kwargs={"space_id": space.pk}))

        assert response.status_code == 403
