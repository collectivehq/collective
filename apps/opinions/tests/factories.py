from __future__ import annotations

import factory

from apps.opinions.models import Opinion, Reaction


class OpinionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Opinion

    opinion_type = Opinion.Type.AGREE


class ReactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reaction

    reaction_type = Reaction.Type.LIKE
