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

    def test_reorganiser_visible_batch_move_controls_are_rendered(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        discussion = space.root_discussion
        post = post_services.create_post(discussion=discussion, author=creator, content="Batch movable")
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"Select items" in response.content
        assert b'data-lucide="check-square"' in response.content
        assert b'x-show="selectingItems && selectedItems.length > 0"' in response.content
        assert reverse("posts:discussion_items_move", kwargs={"space_id": space.pk}).encode() in response.content
        assert str(post.pk).encode() in response.content

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
        assert b"Reorder items" not in response.content
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

    def test_delete_action_uses_standard_delete_warning(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        client.force_login(creator)

        response = client.get(
            reverse(
                "discussions:discussion_detail",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            )
        )

        assert response.status_code == 200
        assert b"> Delete" in response.content
        assert b"This is irreversible." not in response.content


@pytest.mark.django_db
class TestDiscussionDeleteView:
    def test_delete_discussion_soft_deletes_subtree_and_content(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        parent = DiscussionFactory(space=space, parent=space.root_discussion, label="Parent")
        child = DiscussionFactory(space=space, parent=parent, label="Child")
        post = post_services.create_post(discussion=parent, author=creator, content="Parent post")
        link = Link.objects.create(discussion=parent, created_by=creator, target=child, sequence_index=1)
        client.force_login(creator)

        response = client.post(
            reverse(
                "discussions:discussion_delete",
                kwargs={"space_id": space.pk, "discussion_id": parent.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        parent.refresh_from_db()
        child.refresh_from_db()
        post.refresh_from_db()
        link.refresh_from_db()
        assert parent.deleted_at is not None
        assert child.deleted_at is not None
        assert post.deleted_at is not None
        assert link.deleted_at is not None

    def test_delete_discussion_selects_parent_after_delete(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space, parent=space.root_discussion, label="Temporary")
        client.force_login(creator)

        response = client.post(
            reverse(
                "discussions:discussion_delete",
                kwargs={"space_id": space.pk, "discussion_id": discussion.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert str(space.root_discussion.pk).encode() in response["HX-Trigger"].encode()


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
        assert b"Rearrange discussions" not in response.content


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
            reverse("posts:discussion_items_move_positions", kwargs={"space_id": space.pk}),
            {"discussion_id": target_discussion.pk, "item_ids": [movable_post.pk]},
        )

        assert response.status_code == 200
        assert b"Top secret draft" not in response.content

    def test_batch_move_positions_excludes_hidden_drafts(self, client, open_space_with_users) -> None:
        space, creator, participant, _ = open_space_with_users
        sorter_role = space_services.create_role(space=space, label="Sorter", created_by=creator)
        sorter_role = space_services.update_role(role=sorter_role, permissions={"can_reorganise": True})
        participant_record = space.participants.get(user=participant)
        space_services.update_participant_role(participant=participant_record, role=sorter_role)

        current_discussion = space.root_discussion
        target_discussion = DiscussionFactory(space=space, parent=current_discussion)
        first = post_services.create_post(discussion=current_discussion, author=participant, content="First")
        second = post_services.create_post(discussion=current_discussion, author=participant, content="Second")
        post_services.create_post(
            discussion=target_discussion,
            author=creator,
            content="Top secret draft",
            is_draft=True,
        )
        client.force_login(participant)

        response = client.get(
            reverse("posts:discussion_items_move_positions", kwargs={"space_id": space.pk}),
            {"discussion_id": target_discussion.pk, "item_ids": [first.pk, second.pk]},
        )

        assert response.status_code == 200
        assert b"Top secret draft" not in response.content
        assert b"First" in response.content
        assert b"Second" in response.content
        assert b"2 selected items" not in response.content


@pytest.mark.django_db
class TestDiscussionItemMoveView:
    def test_reorganiser_can_move_single_item(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        source = space.root_discussion
        target = DiscussionFactory(space=space, parent=source)
        post = post_services.create_post(discussion=source, author=creator, content="Movable")
        existing = post_services.create_post(discussion=target, author=creator, content="Existing")
        client.force_login(creator)

        response = client.post(
            reverse("posts:discussion_item_move", kwargs={"space_id": space.pk, "item_id": post.pk}),
            {
                "target_discussion_id": target.pk,
                "position": 1,
                "ordered_target_ids": [existing.pk, post.pk],
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        post.refresh_from_db()
        assert post.discussion_id == target.pk
        assert [moved_post.pk for moved_post in target.posts.order_by("sequence_index")] == [existing.pk, post.pk]
        assert str(target.pk).encode() in response["HX-Trigger"].encode()


@pytest.mark.django_db
class TestDiscussionBatchMoveView:
    def test_reorganiser_can_move_selected_items(self, client, open_space_with_users) -> None:
        space, creator, _, _ = open_space_with_users
        source = space.root_discussion
        target = DiscussionFactory(space=space, parent=source)
        first = post_services.create_post(discussion=source, author=creator, content="First")
        second = post_services.create_post(discussion=source, author=creator, content="Second")
        existing = post_services.create_post(discussion=target, author=creator, content="Existing")
        trailing = post_services.create_post(discussion=target, author=creator, content="Trailing")
        client.force_login(creator)

        response = client.post(
            reverse("posts:discussion_items_move", kwargs={"space_id": space.pk}),
            {
                "item_ids": [second.pk, first.pk],
                "target_discussion_id": target.pk,
                "position": 1,
                "ordered_target_ids": [existing.pk, second.pk, trailing.pk, first.pk],
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.discussion_id == target.pk
        assert second.discussion_id == target.pk
        assert [post.pk for post in target.posts.order_by("sequence_index")] == [
            existing.pk,
            second.pk,
            trailing.pk,
            first.pk,
        ]
