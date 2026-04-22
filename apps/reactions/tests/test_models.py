from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.discussions.tests.factories import DiscussionFactory
from apps.posts.tests.factories import PostFactory
from apps.reactions.models import Reaction
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestReaction:
    def test_create_reaction(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        post = PostFactory(space=discussion.space, discussion=discussion, author=UserFactory(), content="Test")
        reaction = Reaction.objects.create(created_by=user, post=post, reaction_type=Reaction.Type.LIKE)
        assert reaction.pk is not None
        assert reaction.reaction_type == "like"

    def test_unique_user_post(self):
        user = UserFactory()
        discussion = DiscussionFactory()
        post = PostFactory(space=discussion.space, discussion=discussion, author=UserFactory(), content="Test")
        Reaction.objects.create(created_by=user, post=post, reaction_type=Reaction.Type.LIKE)
        with pytest.raises(IntegrityError):
            Reaction.objects.create(created_by=user, post=post, reaction_type=Reaction.Type.DISLIKE)
