from __future__ import annotations

import pytest
from django.utils import timezone

from apps.discussions.permissions import (
    can_create_discussion,
    can_delete_discussion,
    can_rename_discussion,
    can_reopen_discussion,
    can_reorganise,
    can_resolve_discussion,
    can_restructure,
    can_view_drafts,
)
from apps.discussions.tests.factories import DiscussionFactory
from apps.posts.permissions import can_post_to_discussion


@pytest.mark.django_db
class TestCanPostToDiscussion:
    def test_facilitator_can_post(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is True

    def test_participant_can_post(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(participant, discussion) is True

    def test_outsider_cannot_post(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(outsider, discussion) is False

    def test_facilitator_can_post_to_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is True

    def test_participant_cannot_post_to_closed_space(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(participant, discussion) is False


@pytest.mark.django_db
class TestCanResolveDiscussion:
    def test_facilitator_can_resolve(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_resolve_discussion(creator, discussion) is True

    def test_participant_cannot_resolve(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_resolve_discussion(participant, discussion) is False

    def test_facilitator_can_resolve_closed_space_discussion(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)

        assert can_resolve_discussion(creator, discussion) is True


@pytest.mark.django_db
class TestDiscussionSpacePermissions:
    def test_facilitator_can_create_discussion(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_create_discussion(creator, space) is True

    def test_participant_cannot_create_discussion(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_create_discussion(participant, space) is False

    def test_facilitator_can_create_discussion_in_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        assert can_create_discussion(creator, space) is True

    def test_facilitator_can_rename_discussion(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_rename_discussion(creator, space) is True

    def test_facilitator_can_manage_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        assert can_rename_discussion(creator, space) is True
        assert can_delete_discussion(creator, space) is True
        assert can_reorganise(creator, space) is True
        assert can_restructure(creator, space) is True

    def test_member_cannot_delete_discussion(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_delete_discussion(participant, space) is False

    def test_facilitator_can_reorganise(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_reorganise(creator, space) is True

    def test_participant_cannot_reorganise(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_reorganise(participant, space) is False

    def test_facilitator_can_view_drafts(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_view_drafts(creator, space) is True

    def test_participant_cannot_view_drafts(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_view_drafts(participant, space) is False

    def test_facilitator_can_reopen_discussion(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        discussion = DiscussionFactory(space=space)
        assert can_reopen_discussion(creator, discussion) is True

    def test_facilitator_can_reopen_discussion_in_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)

        assert can_reopen_discussion(creator, discussion) is True

    def test_member_cannot_restructure(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_restructure(participant, space) is False


@pytest.mark.django_db
class TestCanPostToDiscussionTimeBased:
    def test_cannot_post_space_not_started(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.starts_at = timezone.now() + timezone.timedelta(hours=1)
        space.save()
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is False

    def test_cannot_post_space_ended(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.ends_at = timezone.now() - timezone.timedelta(hours=1)
        space.save()
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is False
