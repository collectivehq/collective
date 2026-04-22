from __future__ import annotations

import factory

from apps.opinions.models import Opinion


class OpinionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Opinion

    opinion_type = Opinion.Type.AGREE
