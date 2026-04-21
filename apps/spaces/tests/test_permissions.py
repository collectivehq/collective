from __future__ import annotations

import pytest
from django.utils import timezone

from apps.nodes import services as node_services
from apps.nodes.models import Node
from apps.nodes.tests.factories import NodeFactory
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.spaces.permissions import (
    can_close_space,
    can_edit_post,
    can_moderate,
    can_opine,
    can_post_to_discussion,
    can_react,
    can_reorganise,
    can_resolve_discussion,
    can_set_permissions,
    can_shape_tree,
    can_view_drafts,
    can_view_post,
    can_view_space,
    get_post_edit_denial_reason,
)
from apps.users.tests.factories import UserFactory


@pytest.fixture
def open_space_with_users():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    participant_user = UserFactory()
    space_services.join_space(space=space, user=participant_user)
    outsider = UserFactory()
    return space, creator, participant_user, outsider


@pytest.mark.django_db
class TestCanPostToDiscussion:
    def test_facilitator_can_post(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        node = NodeFactory(space=space)
        assert can_post_to_discussion(creator, node) is True

    def test_participant_can_post(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        node = NodeFactory(space=space)
        assert can_post_to_discussion(participant, node) is True

    def test_outsider_cannot_post(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        node = NodeFactory(space=space)
        assert can_post_to_discussion(outsider, node) is False

    def test_cannot_post_to_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space_services.close_space(space=space)
        node = NodeFactory(space=space)
        assert can_post_to_discussion(creator, node) is False


@pytest.mark.django_db
class TestCanShapeTree:
    def test_facilitator_can_shape(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_shape_tree(creator, space) is True

    def test_participant_cannot_shape(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_shape_tree(participant, space) is False


@pytest.mark.django_db
class TestCanResolveDiscussion:
    def test_facilitator_can_resolve(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        node = NodeFactory(space=space)
        assert can_resolve_discussion(creator, node) is True

    def test_participant_cannot_resolve(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        node = NodeFactory(space=space)
        assert can_resolve_discussion(participant, node) is False


@pytest.mark.django_db
class TestCanCloseSpace:
    def test_facilitator_can_close(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_close_space(creator, space) is True

    def test_participant_cannot_close(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_close_space(participant, space) is False


@pytest.mark.django_db
class TestCanModerate:
    def test_facilitator_can_moderate(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_moderate(creator, space) is True

    def test_participant_cannot_moderate(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_moderate(participant, space) is False


@pytest.mark.django_db
class TestCanPostToDiscussionTimeBased:
    def test_cannot_post_space_not_started(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.starts_at = timezone.now() + timezone.timedelta(hours=1)
        space.save()
        node = NodeFactory(space=space)
        assert can_post_to_discussion(creator, node) is False

    def test_cannot_post_space_ended(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.ends_at = timezone.now() - timezone.timedelta(hours=1)
        space.save()
        node = NodeFactory(space=space)
        assert can_post_to_discussion(creator, node) is False


@pytest.mark.django_db
class TestCanSetPermissions:
    def test_facilitator_can_set_permissions(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_set_permissions(creator, space) is True

    def test_participant_cannot_set_permissions(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_set_permissions(participant, space) is False

    def test_outsider_cannot_set_permissions(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        assert can_set_permissions(outsider, space) is False


@pytest.mark.django_db
class TestCanViewDrafts:
    def test_facilitator_can_view_drafts(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_view_drafts(creator, space) is True

    def test_participant_cannot_view_drafts(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_view_drafts(participant, space) is False


@pytest.mark.django_db
class TestCanReorganise:
    def test_facilitator_can_reorganise(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_reorganise(creator, space) is True

    def test_participant_cannot_reorganise(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_reorganise(participant, space) is False

    def test_outsider_cannot_reorganise(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        assert can_reorganise(outsider, space) is False


@pytest.mark.django_db
class TestCanEditPost:
    def test_author_can_edit(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = None
        space.save()
        node = NodeFactory(space=space, node_type="post", author=participant_user)
        assert can_edit_post(participant_user, node, space) is True
        assert get_post_edit_denial_reason(participant_user, node, space) is None

    def test_non_author_cannot_edit(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = None
        space.save()
        node = NodeFactory(space=space, node_type="post", author=creator)
        assert can_edit_post(participant_user, node, space) is False
        assert get_post_edit_denial_reason(participant_user, node, space) == "Permission denied"

    def test_moderator_can_edit_other(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        node = NodeFactory(space=space, node_type="post", author=participant_user)
        assert can_edit_post(creator, node, space) is True
        assert get_post_edit_denial_reason(creator, node, space) is None

    def test_editing_disabled(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 0
        space.save()
        node = NodeFactory(space=space, node_type="post", author=participant_user)
        assert can_edit_post(participant_user, node, space) is False
        assert get_post_edit_denial_reason(participant_user, node, space) == "Editing is disabled"

    def test_edit_window_expired(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 5
        space.save()
        node = NodeFactory(
            space=space,
            node_type="post",
            author=participant_user,
        )
        # Backdate created_at after creation
        Node.objects.filter(pk=node.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=10))
        node.refresh_from_db()
        assert can_edit_post(participant_user, node, space) is False
        assert get_post_edit_denial_reason(participant_user, node, space) == "Edit window has expired"

    def test_moderator_bypasses_edit_window(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 5
        space.save()
        node = NodeFactory(
            space=space,
            node_type="post",
            author=participant_user,
        )
        Node.objects.filter(pk=node.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=10))
        node.refresh_from_db()
        # Creator is Facilitator (moderator) — should bypass edit window
        assert can_edit_post(creator, node, space) is True
        assert get_post_edit_denial_reason(creator, node, space) is None


@pytest.mark.django_db
class TestCanViewSpace:
    def test_participant_can_view(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_view_space(participant_user, space) is True

    def test_outsider_cannot_view(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        assert can_view_space(outsider, space) is False


@pytest.mark.django_db
class TestCanViewPost:
    def test_author_can_view_own_draft(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        draft = node_services.create_post(
            discussion=space.root_discussion, author=participant_user, content="Draft", is_draft=True
        )
        assert can_view_post(participant_user, draft) is True

    def test_facilitator_can_view_other_users_draft(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        draft = node_services.create_post(
            discussion=space.root_discussion, author=participant_user, content="Draft", is_draft=True
        )
        assert can_view_post(creator, draft) is True

    def test_participant_cannot_view_other_users_draft(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        draft = node_services.create_post(
            discussion=space.root_discussion, author=creator, content="Draft", is_draft=True
        )
        assert can_view_post(participant_user, draft) is False


@pytest.mark.django_db
class TestCanOpine:
    def test_participant_can_opine(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.opinion_types = ["agree", "disagree"]
        space.save()
        node = NodeFactory(space=space, node_type="discussion")
        assert can_opine(participant_user, node) is True

    def test_outsider_cannot_opine(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        space.opinion_types = ["agree", "disagree"]
        space.save()
        node = NodeFactory(space=space, node_type="discussion")
        assert can_opine(outsider, node) is False

    def test_disabled_opinion_types(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.opinion_types = []
        space.save()
        node = NodeFactory(space=space, node_type="discussion")
        assert can_opine(participant_user, node) is False


@pytest.mark.django_db
class TestCanReact:
    def test_participant_can_react(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.reaction_types = ["like", "dislike"]
        space.save()
        node = NodeFactory(space=space, node_type="post")
        assert can_react(participant_user, node) is True

    def test_outsider_cannot_react(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        space.reaction_types = ["like", "dislike"]
        space.save()
        node = NodeFactory(space=space, node_type="post")
        assert can_react(outsider, node) is False

    def test_disabled_reaction_types(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.reaction_types = []
        space.save()
        node = NodeFactory(space=space, node_type="post")
        assert can_react(participant_user, node) is False
