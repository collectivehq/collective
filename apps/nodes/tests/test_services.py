from __future__ import annotations

import pytest
from django.utils import timezone

from apps.nodes import services as node_services
from apps.nodes.models import Node, PostRevision
from apps.opinions.models import Opinion, Reaction
from apps.spaces import services as space_services
from apps.subscriptions.models import Subscription
from apps.users.tests.factories import UserFactory


@pytest.fixture
def open_space():
    user = UserFactory()
    space = space_services.create_space(title="Test", created_by=user)
    space_services.open_space(space=space)
    return space


@pytest.mark.django_db
class TestCreateChildDiscussion:
    def test_creates_child(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Child")
        assert child.label == "Child"
        assert child.depth == 2
        assert child.node_type == Node.NodeType.DISCUSSION
        root.refresh_from_db()
        assert root.child_count == 1

    def test_nested_children(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="L2")
        grandchild = node_services.create_child_discussion(parent=child, space=open_space, label="L3")
        assert grandchild.depth == 3


@pytest.mark.django_db
class TestCreatePost:
    def test_creates_post(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        post = node_services.create_post(discussion=root, author=user, content="Hello")
        assert post.content == "Hello"
        assert post.node_type == Node.NodeType.POST
        assert post.sequence_index == 0
        root.refresh_from_db()
        assert root.child_count == 1

    def test_sequence_increments(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        p0 = node_services.create_post(discussion=root, author=user, content="First")
        p1 = node_services.create_post(discussion=root, author=user, content="Second")
        assert p0.sequence_index == 0
        assert p1.sequence_index == 1

    def test_closed_space_raises(self, open_space):
        root = open_space.root_discussion
        space_services.close_space(space=open_space)
        user = UserFactory()
        with pytest.raises(ValueError, match="locked"):
            node_services.create_post(discussion=root, author=user, content="Fail")

    def test_space_not_started_raises(self, open_space):
        open_space.starts_at = timezone.now() + timezone.timedelta(hours=1)
        open_space.save()
        root = open_space.root_discussion
        user = UserFactory()
        with pytest.raises(ValueError, match="locked"):
            node_services.create_post(discussion=root, author=user, content="Fail")

    def test_space_ended_raises(self, open_space):
        open_space.ends_at = timezone.now() - timezone.timedelta(hours=1)
        open_space.save()
        root = open_space.root_discussion
        user = UserFactory()
        with pytest.raises(ValueError, match="locked"):
            node_services.create_post(discussion=root, author=user, content="Fail")

    def test_post_with_reopens_discussion(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        post = node_services.create_post(discussion=root, author=user, content="Reopen", reopens_discussion=True)
        assert post.reopens_discussion is True


@pytest.mark.django_db
class TestResolveDiscussion:
    def test_resolve(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        node_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=user)
        root.refresh_from_db()
        assert root.resolution_type == "accept"
        assert root.resolved_by == user
        assert root.resolved_at is not None

    def test_reopen(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        node_services.resolve_discussion(discussion=root, resolution_type="accept", resolved_by=user)
        node_services.reopen_discussion(discussion=root)
        root.refresh_from_db()
        assert root.resolution_type == ""
        assert root.resolved_by is None
        assert root.resolved_at is None


@pytest.mark.django_db
class TestEditPost:
    def test_edit_creates_revision(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        post = node_services.create_post(discussion=root, author=user, content="Original")
        node_services.update_post(post=post, content="Updated")
        assert post.content == "Updated"
        assert PostRevision.objects.filter(post=post).count() == 1
        rev = PostRevision.objects.get(post=post)
        assert rev.content == "Original"


@pytest.mark.django_db
class TestSoftDeleteNode:
    def test_soft_deletes_node_and_descendants(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Child")
        grandchild = node_services.create_child_discussion(parent=child, space=open_space, label="Grandchild")
        node_services.soft_delete_node(node=child)
        child.refresh_from_db()
        grandchild.refresh_from_db()
        assert child.deleted_at is not None
        assert grandchild.deleted_at is not None

    def test_soft_delete_decrements_parent_child_count(self, open_space):
        root = open_space.root_discussion
        node_services.create_child_discussion(parent=root, space=open_space, label="Child")
        root.refresh_from_db()
        assert root.child_count == 1
        child = root.get_children().first()
        node_services.soft_delete_node(node=child)
        root.refresh_from_db()
        assert root.child_count == 0

    def test_soft_delete_leaf_node(self, open_space):
        root = open_space.root_discussion
        leaf = node_services.create_child_discussion(parent=root, space=open_space, label="Leaf")
        node_services.soft_delete_node(node=leaf)
        leaf.refresh_from_db()
        assert leaf.deleted_at is not None

    def test_soft_delete_post(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        post = node_services.create_post(discussion=root, author=user, content="Delete me")
        node_services.soft_delete_node(node=post)
        post.refresh_from_db()
        assert post.deleted_at is not None
        root.refresh_from_db()
        assert root.child_count == 0


@pytest.mark.django_db
class TestUpdateDiscussion:
    def test_update_label(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Old")
        node_services.update_discussion(discussion=child, label="New")
        child.refresh_from_db()
        assert child.label == "New"


@pytest.mark.django_db
class TestMovePost:
    def test_move_post_to_different_discussion(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        source = node_services.create_child_discussion(parent=root, space=open_space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=open_space, label="Target")
        post = node_services.create_post(discussion=source, author=user, content="Move me")
        node_services.move_post(post=post, target_discussion=target)
        post.refresh_from_db()
        assert post.get_parent().pk == target.pk
        source.refresh_from_db()
        target.refresh_from_db()
        assert source.child_count == 0
        assert target.child_count == 1


@pytest.mark.django_db
class TestReorderChildren:
    def test_reorder_updates_sequence_index(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        p0 = node_services.create_post(discussion=root, author=user, content="First")
        p1 = node_services.create_post(discussion=root, author=user, content="Second")
        node_services.reorder_children(node_ids=[str(p1.pk), str(p0.pk)])
        p0.refresh_from_db()
        p1.refresh_from_db()
        assert p1.sequence_index == 0
        assert p0.sequence_index == 1


@pytest.mark.django_db
class TestMoveDiscussion:
    def test_move_discussion(self, open_space):
        root = open_space.root_discussion
        child_a = node_services.create_child_discussion(parent=root, space=open_space, label="A")
        child_b = node_services.create_child_discussion(parent=root, space=open_space, label="B")
        grandchild = node_services.create_child_discussion(parent=child_a, space=open_space, label="GA")

        node_services.move_discussion(discussion=grandchild, new_parent=child_b)

        grandchild.refresh_from_db()
        assert grandchild.get_parent().pk == child_b.pk
        child_a.refresh_from_db()
        assert child_a.child_count == 0
        child_b.refresh_from_db()
        assert child_b.child_count == 1

    def test_move_into_self_raises(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="A")
        with pytest.raises(ValueError):
            node_services.move_discussion(discussion=child, new_parent=child)

    def test_move_into_descendant_raises(self, open_space):
        root = open_space.root_discussion
        child = node_services.create_child_discussion(parent=root, space=open_space, label="A")
        grandchild = node_services.create_child_discussion(parent=child, space=open_space, label="B")
        with pytest.raises(ValueError):
            node_services.move_discussion(discussion=child, new_parent=grandchild)


@pytest.mark.django_db
class TestMergeDiscussions:
    def test_merge_children(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        source = node_services.create_child_discussion(parent=root, space=open_space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=open_space, label="Target")

        node_services.create_post(discussion=source, author=user, content="S1")
        node_services.create_post(discussion=target, author=user, content="T1")

        result = node_services.merge_discussions(source=source, target=target)
        assert result.pk == target.pk
        target.refresh_from_db()
        assert target.child_count == 2
        source.refresh_from_db()
        assert source.deleted_at is not None

    def test_merge_reparents_sub_discussions(self, open_space):
        root = open_space.root_discussion
        source = node_services.create_child_discussion(parent=root, space=open_space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=open_space, label="Target")
        child = node_services.create_child_discussion(parent=source, space=open_space, label="Child")

        node_services.merge_discussions(source=source, target=target)
        child.refresh_from_db()
        assert child.get_parent().pk == target.pk
        target.refresh_from_db()
        assert target.child_count == 1

    def test_merge_decrements_source_parent_child_count(self, open_space):
        root = open_space.root_discussion
        source = node_services.create_child_discussion(parent=root, space=open_space, label="Source")
        target = node_services.create_child_discussion(parent=root, space=open_space, label="Target")
        node_services.merge_discussions(source=source, target=target)
        root.refresh_from_db()
        assert root.child_count == 1


@pytest.mark.django_db
class TestSplitDiscussion:
    def test_split_creates_new_discussion(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Original")

        node_services.create_post(discussion=child, author=user, content="Stay")
        p1 = node_services.create_post(discussion=child, author=user, content="Move")

        new_disc = node_services.split_discussion(discussion=child, child_ids=[str(p1.pk)])
        assert "split" in new_disc.label
        assert new_disc.get_children().filter(deleted_at__isnull=True).count() == 1

    def test_cannot_split_root(self, open_space):
        root = open_space.root_discussion
        with pytest.raises(ValueError, match="root"):
            node_services.split_discussion(discussion=root, child_ids=[])


@pytest.mark.django_db
class TestPromotePost:
    def test_promote_creates_discussion_and_link(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        post = node_services.create_post(discussion=root, author=user, content="Promote me")
        new_disc, link = node_services.promote_post(post=post)
        assert new_disc.node_type == Node.NodeType.DISCUSSION
        assert link.node_type == Node.NodeType.LINK
        assert link.target_id == new_disc.pk
        post.refresh_from_db()
        assert post.get_parent().pk == new_disc.pk


@pytest.mark.django_db
class TestSoftDeleteCascade:
    def test_deletes_subscriptions(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        participant = space_services.join_space(space=open_space, user=user)
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Sub")
        Subscription.objects.create(participant=participant, node=child)
        assert Subscription.objects.filter(node=child).count() == 1
        node_services.soft_delete_node(node=child)
        assert Subscription.objects.filter(node=child).count() == 0

    def test_deletes_opinions(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        participant = space_services.join_space(space=open_space, user=user)
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Sub")
        Opinion.objects.create(participant=participant, node=child, opinion_type="agree")
        assert Opinion.objects.filter(node=child).count() == 1
        node_services.soft_delete_node(node=child)
        assert Opinion.objects.filter(node=child).count() == 0

    def test_deletes_reactions_on_posts(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        participant = space_services.join_space(space=open_space, user=user)
        post = node_services.create_post(discussion=root, author=user, content="React to me")
        Reaction.objects.create(participant=participant, post=post, reaction_type="like")
        assert Reaction.objects.filter(post=post).count() == 1
        node_services.soft_delete_node(node=post)
        assert Reaction.objects.filter(post=post).count() == 0

    def test_cascade_deletes_descendant_subscriptions(self, open_space):
        root = open_space.root_discussion
        user = UserFactory()
        participant = space_services.join_space(space=open_space, user=user)
        child = node_services.create_child_discussion(parent=root, space=open_space, label="Child")
        grandchild = node_services.create_child_discussion(parent=child, space=open_space, label="GC")
        Subscription.objects.create(participant=participant, node=grandchild)
        node_services.soft_delete_node(node=child)
        assert Subscription.objects.filter(node=grandchild).count() == 0
