from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.nodes.models import Node
from apps.nodes.tests.factories import NodeFactory
from apps.opinions.models import Opinion, Reaction
from apps.spaces.tests.factories import SpaceParticipantFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestOpinion:
    def test_create_opinion(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        opinion = Opinion.objects.create(participant=participant, node=node, opinion_type=Opinion.Type.AGREE)
        assert opinion.pk is not None
        assert opinion.opinion_type == "agree"

    def test_str(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        opinion = Opinion.objects.create(participant=participant, node=node, opinion_type=Opinion.Type.DISAGREE)
        assert "disagree" in str(opinion)

    def test_unique_participant_node(self):
        participant = SpaceParticipantFactory()
        node = NodeFactory(space=participant.space)
        Opinion.objects.create(participant=participant, node=node, opinion_type=Opinion.Type.AGREE)
        with pytest.raises(IntegrityError):
            Opinion.objects.create(participant=participant, node=node, opinion_type=Opinion.Type.DISAGREE)


@pytest.mark.django_db
class TestReaction:
    def test_create_reaction(self):
        participant = SpaceParticipantFactory()
        discussion = NodeFactory(space=participant.space)
        post = NodeFactory(
            parent=discussion,
            space=participant.space,
            node_type=Node.NodeType.POST,
            author=UserFactory(),
            content="Test",
        )
        reaction = Reaction.objects.create(participant=participant, post=post, reaction_type=Reaction.Type.LIKE)
        assert reaction.pk is not None
        assert reaction.reaction_type == "like"

    def test_unique_participant_post(self):
        participant = SpaceParticipantFactory()
        discussion = NodeFactory(space=participant.space)
        post = NodeFactory(
            parent=discussion,
            space=participant.space,
            node_type=Node.NodeType.POST,
            author=UserFactory(),
            content="Test",
        )
        Reaction.objects.create(participant=participant, post=post, reaction_type=Reaction.Type.LIKE)
        with pytest.raises(IntegrityError):
            Reaction.objects.create(participant=participant, post=post, reaction_type=Reaction.Type.DISLIKE)
