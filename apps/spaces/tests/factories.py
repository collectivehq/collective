from __future__ import annotations

import factory

from apps.spaces.models import Role, Space, SpaceParticipant
from apps.users.tests.factories import UserFactory


class SpaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Space

    title = factory.Sequence(lambda n: f"Space {n}")
    description = factory.Faker("paragraph")
    created_by = factory.SubFactory(UserFactory)
    opinion_types = factory.LazyFunction(lambda: ["agree", "disagree"])
    reaction_types = ["like", "dislike"]


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    space = factory.SubFactory(SpaceFactory)
    label = factory.Sequence(lambda n: f"Role {n}")
    can_post = True
    can_opine = True
    can_react = True


class SpaceParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpaceParticipant

    space = factory.SubFactory(SpaceFactory)
    user = factory.SubFactory(UserFactory)
    role = factory.SubFactory(RoleFactory, space=factory.SelfAttribute("..space"))
