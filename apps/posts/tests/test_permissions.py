from __future__ import annotations

import pytest
from django.utils import timezone

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.posts.models import Post
from apps.posts.permissions import can_edit_post, can_post_to_discussion, can_view_post, get_post_edit_denial_reason
from apps.posts.tests.factories import PostFactory


@pytest.mark.django_db
class TestCanEditPost:
    def test_author_can_edit(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = None
        space.save()
        post = PostFactory(space=space, author=participant_user)
        assert can_edit_post(participant_user, post, space) is True
        assert get_post_edit_denial_reason(participant_user, post, space) is None

    def test_non_author_cannot_edit(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = None
        space.save()
        post = PostFactory(space=space, author=creator)
        assert can_edit_post(participant_user, post, space) is False
        assert get_post_edit_denial_reason(participant_user, post, space) == "Permission denied"

    def test_moderator_can_edit_other(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        post = PostFactory(space=space, author=participant_user)
        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None

    def test_editing_disabled(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 0
        space.save()
        post = PostFactory(space=space, author=participant_user)
        assert can_edit_post(participant_user, post, space) is False
        assert get_post_edit_denial_reason(participant_user, post, space) == "Editing is disabled"

    def test_edit_window_expired(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 5
        space.save()
        post = PostFactory(space=space, author=participant_user)
        Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=10))
        post.refresh_from_db()
        assert can_edit_post(participant_user, post, space) is False
        assert get_post_edit_denial_reason(participant_user, post, space) == "Edit window has expired"

    def test_moderator_bypasses_edit_window(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 5
        space.save()
        post = PostFactory(space=space, author=participant_user)
        Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=10))
        post.refresh_from_db()
        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None


@pytest.mark.django_db
class TestCanViewPost:
    def test_author_can_view_own_draft(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion, author=participant_user, content="Draft", is_draft=True
        )
        assert can_view_post(participant_user, draft) is True

    def test_facilitator_can_view_other_users_draft(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion, author=participant_user, content="Draft", is_draft=True
        )
        assert can_view_post(creator, draft) is True

    def test_participant_cannot_view_other_users_draft(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        draft = post_services.create_post(
            discussion=space.root_discussion, author=creator, content="Draft", is_draft=True
        )
        assert can_view_post(participant_user, draft) is False


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

    def test_cannot_post_to_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is False

    def test_cannot_post_before_space_starts(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.starts_at = timezone.now() + timezone.timedelta(hours=1)
        space.save()
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is False

    def test_cannot_post_after_space_ends(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.ends_at = timezone.now() - timezone.timedelta(hours=1)
        space.save()
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(creator, discussion) is False
