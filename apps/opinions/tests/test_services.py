from __future__ import annotations

import pytest

from apps.nodes import services as node_services
from apps.nodes.tests.factories import NodeFactory
from apps.opinions import services as opinion_services
from apps.opinions.models import Opinion, Reaction
from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def space_with_participant():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)

    joiner = UserFactory()
    participant = space_services.join_space(space=space, user=joiner)
    node = NodeFactory(space=space)
    return space, participant, node


@pytest.mark.django_db
class TestCastOpinion:
    def test_toggle_opinion(self, space_with_participant):
        space, participant, node = space_with_participant
        opinion = opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        assert opinion.opinion_type == "agree"

    def test_update_opinion(self, space_with_participant):
        space, participant, node = space_with_participant
        opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        opinion = opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="disagree")
        assert opinion.opinion_type == "disagree"
        assert Opinion.objects.filter(participant=participant, node=node).count() == 1

    def test_invalid_type_raises(self, space_with_participant):
        space, participant, node = space_with_participant
        with pytest.raises(ValueError, match="not enabled"):
            opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="abstain")


@pytest.mark.django_db
class TestGetOpinionCounts:
    def test_counts(self, space_with_participant):
        space, participant, node = space_with_participant
        opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")

        joiner2 = UserFactory()
        p2 = space_services.join_space(space=space, user=joiner2)
        opinion_services.toggle_opinion(participant=p2, node=node, opinion_type="disagree")

        counts = opinion_services.get_opinion_counts(node)
        assert counts["agree"] == 1
        assert counts["disagree"] == 1


@pytest.mark.django_db
class TestGetOpinionCountsBatch:
    def test_batch_counts(self, space_with_participant):
        space, participant, node = space_with_participant
        node2 = NodeFactory(space=space)
        opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        opinion_services.toggle_opinion(participant=participant, node=node2, opinion_type="disagree")
        counts = opinion_services.get_opinion_counts_batch([node.pk, node2.pk])
        assert counts[node.pk]["agree"] == 1
        assert counts[node2.pk]["disagree"] == 1

    def test_batch_empty_list(self, space_with_participant):
        counts = opinion_services.get_opinion_counts_batch([])
        assert counts == {}


@pytest.mark.django_db
class TestToggleReaction:
    def test_add_reaction(self, space_with_participant):
        space, participant, node = space_with_participant
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        reaction = opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="like")
        assert reaction is not None
        assert reaction.reaction_type == "like"

    def test_toggle_same_removes(self, space_with_participant):
        space, participant, node = space_with_participant
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="like")
        result = opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="like")
        assert result is None
        assert not Reaction.objects.filter(participant=participant, post=post).exists()

    def test_dislike_not_allowed_in_like_config(self, space_with_participant):
        space, participant, node = space_with_participant
        space.reaction_types = ["like"]
        space.save()
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        with pytest.raises(ValueError, match="Dislike"):
            opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="dislike")

    def test_reactions_disabled_raises(self, space_with_participant):
        space, participant, node = space_with_participant
        space.reaction_types = []
        space.save()
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        with pytest.raises(ValueError, match="disabled"):
            opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="like")


@pytest.mark.django_db
class TestToggleOpinionRemoval:
    def test_toggle_same_opinion_removes(self, space_with_participant):
        space, participant, node = space_with_participant
        opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        result = opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        assert result is None
        assert not Opinion.objects.filter(participant=participant, node=node).exists()


@pytest.mark.django_db
class TestGetUserOpinion:
    def test_returns_type_when_exists(self, space_with_participant):
        space, participant, node = space_with_participant
        opinion_services.toggle_opinion(participant=participant, node=node, opinion_type="agree")
        result = opinion_services.get_participant_opinion_type(participant=participant, node=node)
        assert result == "agree"

    def test_returns_none_when_no_opinion(self, space_with_participant):
        space, participant, node = space_with_participant
        result = opinion_services.get_participant_opinion_type(participant=participant, node=node)
        assert result is None


@pytest.mark.django_db
class TestToggleReactionChangeType:
    def test_change_from_like_to_dislike(self, space_with_participant):
        space, participant, node = space_with_participant
        post = node_services.create_post(discussion=node, author=participant.user, content="Test")
        opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="like")
        result = opinion_services.toggle_reaction(participant=participant, post=post, reaction_type="dislike")
        assert result is not None
        assert result.reaction_type == "dislike"
        assert Reaction.objects.filter(participant=participant, post=post).count() == 1
