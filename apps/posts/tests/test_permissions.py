from __future__ import annotations

import pytest
from django.utils import timezone

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts import services as post_services
from apps.posts.models import Post
from apps.posts.permissions import (
    can_create_draft,
    can_delete_post,
    can_edit_post,
    can_post_to_discussion,
    can_promote_post,
    can_upload_images,
    can_view_history,
    can_view_post,
    get_post_edit_denial_reason,
)
from apps.posts.tests.factories import PostFactory
from apps.spaces.models import Role


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

    def test_facilitator_can_edit_other_users_post_by_default(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        post = PostFactory(space=space, author=participant_user)
        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None

    def test_role_with_edit_others_permission_can_edit_other_users_post(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        facilitator_role = Role.objects.get(space=space, label="Facilitator")
        facilitator_role.can_edit_others_post = True
        facilitator_role.save(update_fields=["can_edit_others_post"])
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

    def test_facilitator_can_edit_other_users_post_when_window_expired(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 5
        space.save()
        post = PostFactory(space=space, author=participant_user)
        Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=10))
        post.refresh_from_db()
        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None

    def test_edit_others_permission_ignores_author_edit_window(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.edit_window_minutes = 0
        space.save()
        facilitator_role = Role.objects.get(space=space, label="Facilitator")
        facilitator_role.can_edit_others_post = True
        facilitator_role.save(update_fields=["can_edit_others_post"])
        post = PostFactory(space=space, author=participant_user)

        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None

    def test_facilitator_can_edit_post_in_closed_space(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space, author=participant_user)

        assert can_edit_post(creator, post, space) is True
        assert get_post_edit_denial_reason(creator, post, space) is None

    def test_member_cannot_edit_post_in_closed_space(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space, author=participant_user)

        assert can_edit_post(participant_user, post, space) is False
        assert get_post_edit_denial_reason(participant_user, post, space) == "This space is closed"

    def test_facilitator_cannot_edit_post_in_archived_space(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.ARCHIVED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space, author=participant_user)

        assert can_edit_post(creator, post, space) is False
        assert get_post_edit_denial_reason(creator, post, space) == "This space is archived"


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
class TestAdditionalPostPermissions:
    def test_member_can_create_draft(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_create_draft(participant_user, space) is True

    def test_facilitator_can_create_draft_in_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        assert can_create_draft(creator, space) is True

    def test_member_cannot_create_draft_in_closed_space(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        assert can_create_draft(participant_user, space) is False

    def test_member_can_upload_images(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_upload_images(participant_user, space) is True

    def test_member_can_view_history(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_view_history(participant_user, space) is True

    def test_member_cannot_promote_post(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_promote_post(participant_user, space) is False

    def test_author_can_delete_own_post(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        post = PostFactory(space=space, author=participant_user)
        assert can_delete_post(participant_user, post, space) is True

    def test_facilitator_can_delete_and_promote_in_closed_space(self, open_space_with_users):
        space, creator, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space, author=participant_user)

        assert can_delete_post(creator, post, space) is True
        assert can_promote_post(creator, space) is True

    def test_member_cannot_delete_or_promote_in_closed_space(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space, author=participant_user)

        assert can_delete_post(participant_user, post, space) is False
        assert can_promote_post(participant_user, space) is False

    def test_member_cannot_upload_images_in_closed_space(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])

        assert can_upload_images(participant_user, space) is False

    def test_member_without_post_or_draft_permissions_cannot_upload_images(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        Role.objects.filter(space=space, label="Member").update(can_post=False, can_create_draft=False)

        assert can_upload_images(participant_user, space) is False


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

    def test_member_cannot_post_to_closed_space(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)
        assert can_post_to_discussion(participant, discussion) is False

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
