from __future__ import annotations

import pytest
from django.urls import reverse

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.posts.models import Link
from apps.spaces import services as space_services
from apps.spaces.models import Role


@pytest.mark.django_db
class TestDiscussionDetailView:
    def test_authenticated_participant_can_view_discussion(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200

    def test_unauthenticated_user_is_redirected(self, client, open_space_with_users) -> None:
        space, _, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 302

    def test_renders_subdiscussion_child_count(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        sub_discussion = DiscussionFactory(space=space, parent=discussion)
        nested = DiscussionFactory(space=space, parent=sub_discussion)
        post_services.create_post(discussion=sub_discussion, author=participant, content="Hello")
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert nested.label.encode() not in response.content
        assert b"2 children" in response.content

    def test_subdiscussion_child_count_excludes_hidden_drafts(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        discussion = space.root_discussion
        sub_discussion = DiscussionFactory(space=space, parent=discussion)
        post_services.create_post(discussion=sub_discussion, author=creator, content="Hidden draft", is_draft=True)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"0 children" in response.content
        assert b"1 children" not in response.content

    def test_link_preview_excludes_hidden_draft_content(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        discussion = space.root_discussion
        target = DiscussionFactory(space=space, parent=discussion)
        Link.objects.create(discussion=discussion, created_by=creator, target=target, sequence_index=0)
        post_services.create_post(discussion=target, author=creator, content="Secret draft preview", is_draft=True)
        post_services.create_post(discussion=target, author=creator, content="Visible preview", is_draft=False)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"Secret draft preview" not in response.content
        assert b"Visible preview" in response.content

    def test_role_post_highlight_color_is_rendered(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        Role.objects.filter(space=space, label="Member").update(post_highlight_color="#FACC15")
        discussion = space.root_discussion
        post_services.create_post(discussion=discussion, author=participant, content="Highlighted post")
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"#FACC15" in response.content

    def test_facilitator_visible_post_actions_are_rendered(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        discussion = space.root_discussion
        post = post_services.create_post(discussion=discussion, author=creator, content="Actionable post")
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert (
            reverse("posts:post_delete", kwargs={"space_id": space.pk, "post_id": post.pk}).encode() in response.content
        )
        assert (
            reverse("posts:discussion_item_move", kwargs={"space_id": space.pk, "item_id": post.pk}).encode()
            in response.content
        )
        assert (
            reverse("posts:post_promote", kwargs={"space_id": space.pk, "post_id": post.pk}).encode()
            in response.content
        )

    def test_facilitator_visible_link_actions_are_rendered(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        discussion = space.root_discussion
        target = DiscussionFactory(space=space, parent=discussion)
        link = Link.objects.create(discussion=discussion, created_by=creator, target=target, sequence_index=0)
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert (
            reverse("posts:link_delete", kwargs={"space_id": space.pk, "link_id": link.pk}).encode() in response.content
        )
        assert (
            reverse("posts:discussion_item_move", kwargs={"space_id": space.pk, "item_id": link.pk}).encode()
            in response.content
        )

    def test_closed_space_tree_shows_add_discussion_controls_for_facilitator(
        self,
        client,
        open_space_with_users,
    ) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.get(reverse("discussions:discussion_tree", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Add Discussion" in response.content

    def test_closed_space_discussion_create_succeeds_for_facilitator(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.post(
            reverse("discussions:discussion_create", kwargs={"space_id": space.pk}),
            {"parent_id": space.root_discussion.pk, "label": "Should fail"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Should fail" in response.content

    def test_archived_space_hides_inactive_discussion_actions(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.ARCHIVED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)
        discussion.resolution_type = "close"
        discussion.save(update_fields=["resolution_type"])
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"Resolve" not in response.content
        assert b"Edit title" not in response.content
        assert b"Reopen discussion" not in response.content
        assert b"Reorder children" not in response.content
        assert b"Subscribe" not in response.content
        assert b"ellipsis-vertical" not in response.content

    def test_discussion_detail_hides_upload_url_when_user_cannot_upload_images(
        self,
        client,
        open_space_with_users,
    ) -> None:
        space, _, participant, _ = open_space_with_users
        Role.objects.filter(space=space, label="Member").update(can_post=False, can_create_draft=False)
        client.force_login(participant)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk},
            )
        )

        assert response.status_code == 200
        assert reverse("posts:image_upload", kwargs={"space_id": space.pk}).encode() not in response.content


@pytest.mark.django_db
class TestDiscussionTreeView:
    def test_tree_shows_root_discussion(self, client, open_space_with_users) -> None:
        space, _, participant, _ = open_space_with_users
        client.force_login(participant)

        response = client.get(reverse("discussions:discussion_tree", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert (
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": space.root_discussion.pk},
            ).encode()
            in response.content
        )


@pytest.mark.django_db
class TestSpaceDetailViewStateActions:
    def test_archived_space_hides_tree_rearrange_action(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.ARCHIVED
        space.save(update_fields=["lifecycle"])
        client.force_login(creator)

        response = client.get(reverse("spaces:detail", kwargs={"space_id": space.pk}))

        assert response.status_code == 200
        assert b"Rearrange tree" not in response.content


@pytest.mark.django_db
class TestDiscussionMovePositionsView:
    def test_move_positions_excludes_hidden_drafts(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        sorter_role = space_services.create_role(space=space, label="Sorter", created_by=creator)
        sorter_role = space_services.update_role(role=sorter_role, permissions={"can_reorganise": True})
        participant_record = space.participants.get(user=participant)
        space_services.update_participant_role(participant=participant_record, role=sorter_role)

        current_discussion = space.root_discussion
        target_discussion = DiscussionFactory(space=space, parent=current_discussion)
        movable_post = post_services.create_post(
            discussion=current_discussion,
            author=participant,
            content="Movable post",
        )
        post_services.create_post(
            discussion=target_discussion,
            author=creator,
            content="Top secret draft",
            is_draft=True,
        )
        client.force_login(participant)

        response = client.get(
            reverse("posts:discussion_item_move_positions", kwargs={"space_id": space.pk, "item_id": movable_post.pk}),
            {"discussion_id": target_discussion.pk},
        )

        assert response.status_code == 200
        assert b"Top secret draft" not in response.content
