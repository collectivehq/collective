from __future__ import annotations

import factory

from apps.spaces import services as space_services
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.users.tests.factories import UserFactory


class SpaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Space

    title = factory.Sequence(lambda n: f"Space {n}")
    description = factory.Faker("paragraph")
    created_by = factory.SubFactory(UserFactory)
    opinion_types = factory.LazyFunction(lambda: ["agree", "disagree"])
    reaction_types = factory.LazyFunction(lambda: ["like", "dislike"])

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        space = space_services.create_space(
            title=kwargs.pop("title"),
            description=kwargs.pop("description"),
            created_by=kwargs.pop("created_by"),
            template_slug=kwargs.pop("template_slug", ""),
            opinion_types=kwargs.pop("opinion_types", None),
            reaction_types=kwargs.pop("reaction_types", None),
            starts_at=kwargs.pop("starts_at", None),
            ends_at=kwargs.pop("ends_at", None),
        )

        update_fields: list[str] = []
        for field_name in ("lifecycle", "edit_window_minutes", "deleted_at", "updated_at"):
            if field_name in kwargs:
                setattr(space, field_name, kwargs.pop(field_name))
                update_fields.append(field_name)
        if update_fields:
            space.save(update_fields=update_fields)
        return space


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    space = factory.SubFactory(SpaceFactory)
    label = factory.Sequence(lambda n: f"Role {n}")
    can_post = True
    can_view_drafts = False
    can_opine = True
    can_react = True


class SpaceParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpaceParticipant

    space = factory.SubFactory(SpaceFactory)
    user = factory.SubFactory(UserFactory)
    role = factory.SubFactory(RoleFactory, space=factory.SelfAttribute("..space"))
