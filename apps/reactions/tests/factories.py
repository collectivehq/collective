from __future__ import annotations

import factory

from apps.posts.tests.factories import PostFactory
from apps.reactions.models import Reaction
from apps.users.tests.factories import UserFactory


class ReactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reaction

    created_by = factory.SubFactory(UserFactory)
    post = factory.SubFactory(PostFactory)
    reaction_type = Reaction.Type.LIKE
