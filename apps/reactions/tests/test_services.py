from __future__ import annotations

import pytest

from apps.posts import services as post_services
from apps.reactions import services as reaction_services
from apps.reactions.models import Reaction


@pytest.mark.django_db
class TestToggleReaction:
    def test_add_reaction(self, space_with_participant):
        _, participant, node = space_with_participant
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        reaction = reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="like")
        assert reaction is not None
        assert reaction.reaction_type == "like"

    def test_toggle_same_removes(self, space_with_participant):
        _, participant, node = space_with_participant
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="like")
        result = reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="like")
        assert result is None
        assert not Reaction.objects.filter(created_by=participant.user, post=post).exists()

    def test_dislike_not_allowed_in_like_config(self, space_with_participant):
        space, participant, node = space_with_participant
        space.reaction_types = ["like"]
        space.save()
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        with pytest.raises(ValueError, match="Dislike"):
            reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="dislike")

    def test_reactions_disabled_raises(self, space_with_participant):
        space, participant, node = space_with_participant
        space.reaction_types = []
        space.save()
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        with pytest.raises(ValueError, match="disabled"):
            reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="like")


@pytest.mark.django_db
class TestToggleReactionChangeType:
    def test_change_from_like_to_dislike(self, space_with_participant):
        _, participant, node = space_with_participant
        post = post_services.create_post(discussion=node, author=participant.user, content="Test")
        reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="like")
        result = reaction_services.toggle_reaction(user=participant.user, post=post, reaction_type="dislike")
        assert result is not None
        assert result.reaction_type == "dislike"
        assert Reaction.objects.filter(created_by=participant.user, post=post).count() == 1
