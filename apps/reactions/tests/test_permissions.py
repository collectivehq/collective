from __future__ import annotations

import pytest

from apps.posts.tests.factories import PostFactory
from apps.reactions.permissions import can_react


@pytest.mark.django_db
class TestCanReact:
    def test_participant_can_react(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.reaction_types = ["like", "dislike"]
        space.save()
        post = PostFactory(space=space)

        assert can_react(participant_user, post) is True

    def test_outsider_cannot_react(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        space.reaction_types = ["like", "dislike"]
        space.save()
        post = PostFactory(space=space)

        assert can_react(outsider, post) is False

    def test_disabled_reaction_types(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.reaction_types = []
        space.save()
        post = PostFactory(space=space)

        assert can_react(participant_user, post) is False

    def test_facilitator_can_react_in_closed_space(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space)

        assert can_react(creator, post) is True

    def test_member_cannot_react_in_closed_space(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        post = PostFactory(space=space)

        assert can_react(participant_user, post) is False
