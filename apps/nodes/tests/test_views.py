from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.nodes import services as node_services
from apps.nodes.models import Node
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def space_with_host():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    c = Client()
    c.force_login(creator)
    return c, creator, space


@pytest.mark.django_db
class TestDiscussionDetailView:
    def test_view_discussion(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Child")
        response = c.get(reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": child.pk}))
        assert response.status_code == 200

    def test_requires_login(self, space_with_host):
        _, _, space = space_with_host
        root = space.root_discussion
        anon = Client()
        response = anon.get(reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": root.pk}))
        assert response.status_code == 302

    def test_resolved_discussion_renders_reopen_dialog(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        node_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=creator)

        response = c.get(reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": root.pk}))

        assert response.status_code == 200
        assert f"reopenDiscussionDialog-{root.pk}".encode() in response.content
        assert b"Reopen discussion" in response.content


@pytest.mark.django_db
class TestDiscussionCreateView:
    def test_facilitator_can_create_discussion(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:discussion_create", kwargs={"space_id": space.pk}),
            {"parent_id": str(root.pk), "label": "New Discussion"},
        )
        assert response.status_code == 200

    def test_participant_cannot_create_discussion(self, space_with_host):
        _, _, space = space_with_host
        root = space.root_discussion
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        c = Client()
        c.force_login(joiner)
        response = c.post(
            reverse("nodes:discussion_create", kwargs={"space_id": space.pk}),
            {"parent_id": str(root.pk), "label": "Denied"},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestPostCreateView:
    def test_create_post(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:post_create", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"content": "Hello World"},
        )
        assert response.status_code == 200

    def test_save_post_as_draft(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:post_create", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"content": "Draft post", "save_draft": "true"},
        )

        assert response.status_code == 200
        draft = Node.objects.get(space=space, deleted_at__isnull=True, node_type=Node.NodeType.POST)
        assert draft.is_draft is True

    def test_empty_content_rejected(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:post_create", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"content": ""},
        )
        assert response.status_code == 400


@pytest.fixture
def space_with_host_and_participant():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    joiner = UserFactory()
    space_services.join_space(space=space, user=joiner)
    facilitator_client = Client()
    facilitator_client.force_login(creator)
    part_client = Client()
    part_client.force_login(joiner)
    return facilitator_client, creator, part_client, joiner, space


@pytest.mark.django_db
class TestPostEditView:
    def test_author_can_edit(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Original")
        response = c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Updated"},
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.content == "Updated"

    def test_moderator_can_edit_other(self, space_with_host_and_participant):
        facilitator_c, _, part_c, joiner, space = space_with_host_and_participant
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=joiner, content="Original")
        response = facilitator_c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Edited by host"},
        )
        assert response.status_code == 200

    def test_non_author_non_moderator_denied(self, space_with_host_and_participant):
        _, creator, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Facilitator post")
        response = part_c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Hacked"},
        )
        assert response.status_code == 403

    def test_empty_content_rejected(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Original")
        response = c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": ""},
        )
        assert response.status_code == 400

    def test_publish_draft(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        draft = node_services.create_post(discussion=root, author=creator, content="Original draft", is_draft=True)

        response = c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": draft.pk}),
            {"content": "Published post", "publish": "true"},
        )

        assert response.status_code == 200
        draft.refresh_from_db()
        assert draft.is_draft is False
        assert draft.content == "Published post"

    def test_hidden_draft_forbidden_to_regular_participant(self, space_with_host_and_participant):
        _, creator, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        draft = node_services.create_post(discussion=root, author=creator, content="Hidden draft", is_draft=True)

        response = part_c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": draft.pk}),
            {"content": "Hacked"},
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestPostDeleteView:
    def test_author_can_delete(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Delete me")
        response = c.post(
            reverse("nodes:post_delete", kwargs={"space_id": space.pk, "post_id": post.pk}),
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.deleted_at is not None

    def test_moderator_can_delete_other(self, space_with_host_and_participant):
        facilitator_c, _, _, joiner, space = space_with_host_and_participant
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=joiner, content="Delete me")
        response = facilitator_c.post(
            reverse("nodes:post_delete", kwargs={"space_id": space.pk, "post_id": post.pk}),
        )
        assert response.status_code == 200

    def test_non_author_non_moderator_denied(self, space_with_host_and_participant):
        _, creator, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Protected")
        response = part_c.post(
            reverse("nodes:post_delete", kwargs={"space_id": space.pk, "post_id": post.pk}),
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestLinkDeleteView:
    def test_moderator_can_delete_link(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Promote me")
        _new_disc, link = node_services.promote_post(post=post)
        response = c.post(
            reverse("nodes:link_delete", kwargs={"space_id": space.pk, "link_id": link.pk}),
        )
        assert response.status_code == 200
        link.refresh_from_db()
        assert link.deleted_at is not None

    def test_participant_cannot_delete_link(self, space_with_host_and_participant):
        facilitator_c, creator, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Promote me")
        _new_disc, link = node_services.promote_post(post=post)
        response = part_c.post(
            reverse("nodes:link_delete", kwargs={"space_id": space.pk, "link_id": link.pk}),
        )
        assert response.status_code == 403
        link.refresh_from_db()
        assert link.deleted_at is None

    def test_requires_login(self, space_with_host):
        _, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Promote me")
        _new_disc, link = node_services.promote_post(post=post)
        anon = Client()
        response = anon.post(
            reverse("nodes:link_delete", kwargs={"space_id": space.pk, "link_id": link.pk}),
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestDiscussionMoveView:
    def test_facilitator_can_move(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child1 = node_services.create_child_discussion(parent=root, space=space, label="Child 1")
        child2 = node_services.create_child_discussion(parent=root, space=space, label="Child 2")
        response = c.post(
            reverse("nodes:discussion_move", kwargs={"space_id": space.pk, "discussion_id": child1.pk}),
            {"new_parent_id": str(child2.pk)},
        )
        assert response.status_code == 200
        child1.refresh_from_db()
        assert child1.get_parent().pk == child2.pk

    def test_participant_denied(self, space_with_host_and_participant):
        _, _, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Child")
        response = part_c.post(
            reverse("nodes:discussion_move", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"new_parent_id": str(root.pk)},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestDiscussionMergeView:
    def test_facilitator_can_merge(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        source = node_services.create_child_discussion(parent=root, space=space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=space, label="Target")
        node_services.create_post(discussion=source, author=creator, content="Move me")
        response = c.post(
            reverse("nodes:discussion_merge", kwargs={"space_id": space.pk, "discussion_id": source.pk}),
            {"target_id": str(target.pk)},
        )
        assert response.status_code == 200
        source.refresh_from_db()
        assert source.deleted_at is not None

    def test_participant_denied(self, space_with_host_and_participant):
        _, _, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        source = node_services.create_child_discussion(parent=root, space=space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=space, label="Target")
        response = part_c.post(
            reverse("nodes:discussion_merge", kwargs={"space_id": space.pk, "discussion_id": source.pk}),
            {"target_id": str(target.pk)},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestDiscussionSplitView:
    def test_facilitator_can_split(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Splittable")
        p1 = node_services.create_post(discussion=child, author=creator, content="Post 1")
        node_services.create_post(discussion=child, author=creator, content="Post 2")
        response = c.post(
            reverse("nodes:discussion_split", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"child_ids": [str(p1.pk)]},
        )
        assert response.status_code == 200
        assert Node.objects.filter(space=space, deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION).count() > 2

    def test_no_children_returns_400(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Child")
        response = c.post(
            reverse("nodes:discussion_split", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
        )
        assert response.status_code == 400

    def test_participant_denied(self, space_with_host_and_participant):
        _, _, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Child")
        response = part_c.post(
            reverse("nodes:discussion_split", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"child_ids": ["fake"]},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestDiscussionResolveView:
    def test_facilitator_can_resolve(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:discussion_resolve", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"resolution": "accept"},
        )
        assert response.status_code == 200
        root.refresh_from_db()
        assert root.resolution_type == "accept"


@pytest.mark.django_db
class TestPostCreateResolution:
    def test_create_post_with_resolution(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:post_create", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"content": "Resolved", "resolution": "accept"},
        )
        assert response.status_code == 200

    def test_non_resolver_resolution_stripped(self, space_with_host_and_participant):
        _, _, part_c, joiner, space = space_with_host_and_participant
        root = space.root_discussion
        response = part_c.post(
            reverse("nodes:post_create", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"content": "Attempt resolve", "resolution": "accept"},
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestDiscussionEditView:
    def test_facilitator_can_edit(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Old")
        response = c.post(
            reverse("nodes:discussion_edit", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"label": "New"},
        )
        assert response.status_code == 200
        child.refresh_from_db()
        assert child.label == "New"

    def test_participant_denied(self, space_with_host_and_participant):
        _, _, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Discussion")
        response = part_c.post(
            reverse("nodes:discussion_edit", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"label": "Hacked"},
        )
        assert response.status_code == 403

    def test_empty_label_rejected(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Discussion")
        response = c.post(
            reverse("nodes:discussion_edit", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"label": ""},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestDiscussionDeleteView:
    def test_facilitator_can_delete(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Delete me")
        response = c.post(
            reverse("nodes:discussion_delete", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
        )
        assert response.status_code == 200
        child.refresh_from_db()
        assert child.deleted_at is not None

    def test_cannot_delete_root(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        response = c.post(
            reverse("nodes:discussion_delete", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
        )
        assert response.status_code == 403

    def test_participant_denied(self, space_with_host_and_participant):
        _, _, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="Discussion")
        response = part_c.post(
            reverse("nodes:discussion_delete", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestDiscussionReopenView:
    def test_resolver_can_reopen(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        node_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=creator)
        response = c.post(
            reverse("nodes:discussion_reopen", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
        )
        assert response.status_code == 200
        root.refresh_from_db()
        assert root.resolution_type == ""


@pytest.mark.django_db
class TestInactiveSpaceMutations:
    def test_discussion_create_on_closed_space(self, space_with_host):
        c, creator, space = space_with_host
        space_services.close_space(space=space)
        root = space.root_discussion
        response = c.post(
            reverse("nodes:discussion_create", kwargs={"space_id": space.pk}),
            {"parent_id": str(root.pk), "label": "Denied"},
        )
        assert response.status_code == 404

    def test_discussion_move_on_closed_space(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=space, label="A")
        space_services.close_space(space=space)
        response = c.post(
            reverse("nodes:discussion_move", kwargs={"space_id": space.pk, "discussion_id": child.pk}),
            {"new_parent_id": str(root.pk)},
        )
        assert response.status_code == 404

    def test_discussion_merge_on_closed_space(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        source = node_services.create_child_discussion(parent=root, space=space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=space, label="Target")
        space_services.close_space(space=space)
        response = c.post(
            reverse("nodes:discussion_merge", kwargs={"space_id": space.pk, "discussion_id": source.pk}),
            {"target_id": str(target.pk)},
        )
        assert response.status_code == 404

    def test_post_edit_on_closed_space(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Original")
        space_services.close_space(space=space)
        response = c.post(
            reverse("nodes:post_edit", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"content": "Edited"},
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestPostRevisionsView:
    def test_view_revisions(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        post = node_services.create_post(discussion=root, author=creator, content="Original")
        node_services.update_post(post=post, content="Updated")
        response = c.get(
            reverse("nodes:post_revisions", kwargs={"space_id": space.pk, "post_id": post.pk}),
        )
        assert response.status_code == 200
        assert b"Original" in response.content

    def test_regular_participant_cannot_access_other_users_draft(self, space_with_host_and_participant):
        _, creator, part_c, _, space = space_with_host_and_participant
        root = space.root_discussion
        draft = node_services.create_post(discussion=root, author=creator, content="Hidden draft", is_draft=True)

        response = part_c.get(
            reverse("nodes:post_revisions", kwargs={"space_id": space.pk, "post_id": draft.pk}),
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestDraftVisibility:
    def test_author_sees_publish_action_and_footer_draft_badge(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        node_services.create_post(discussion=root, author=creator, content="Draft content", is_draft=True)

        response = c.get(reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": root.pk}))

        assert response.status_code == 200
        assert b'data-role="publish-draft-action"' in response.content
        assert b'data-role="draft-badge"' in response.content

    def test_regular_participant_does_not_see_other_users_draft(self, space_with_host_and_participant):
        facilitator_c, creator, part_c, joiner, space = space_with_host_and_participant
        root = space.root_discussion
        node_services.create_post(discussion=root, author=creator, content="Hidden draft", is_draft=True)

        response = part_c.get(
            reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": root.pk})
        )

        assert response.status_code == 200
        assert b"Hidden draft" not in response.content

    def test_facilitator_sees_participant_draft(self, space_with_host_and_participant):
        facilitator_c, creator, part_c, joiner, space = space_with_host_and_participant
        root = space.root_discussion
        node_services.create_post(discussion=root, author=joiner, content="Participant draft", is_draft=True)

        response = facilitator_c.get(
            reverse("nodes:discussion_detail", kwargs={"space_id": space.pk, "discussion_id": root.pk})
        )

        assert response.status_code == 200
        assert b"Participant draft" in response.content
        assert b"Draft" in response.content


@pytest.mark.django_db
class TestPostMoveView:
    def test_facilitator_can_move_post(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        target = node_services.create_child_discussion(parent=root, space=space, label="Target")
        post = node_services.create_post(discussion=root, author=creator, content="Move me")
        response = c.post(
            reverse("nodes:post_move", kwargs={"space_id": space.pk, "post_id": post.pk}),
            {"target_discussion_id": str(target.pk)},
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.get_parent().pk == target.pk


@pytest.mark.django_db
class TestDiscussionReorderView:
    def test_facilitator_can_reorder(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        a = node_services.create_child_discussion(parent=root, space=space, label="A")
        b = node_services.create_child_discussion(parent=root, space=space, label="B")
        response = c.post(
            reverse("nodes:tree_reorder", kwargs={"space_id": space.pk}),
            {"node_ids": [str(b.pk), str(a.pk)]},
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestChildrenReorderView:
    def test_facilitator_can_reorder_children(self, space_with_host):
        c, creator, space = space_with_host
        root = space.root_discussion
        p0 = node_services.create_post(discussion=root, author=creator, content="First")
        p1 = node_services.create_post(discussion=root, author=creator, content="Second")
        response = c.post(
            reverse("nodes:discussion_children_reorder", kwargs={"space_id": space.pk, "discussion_id": root.pk}),
            {"node_ids": [str(p1.pk), str(p0.pk)]},
        )
        assert response.status_code == 200
