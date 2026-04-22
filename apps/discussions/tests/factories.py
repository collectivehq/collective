from __future__ import annotations

import factory

from apps.discussions.models import Discussion
from apps.spaces.tests.factories import SpaceFactory


class DiscussionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Discussion

    space = factory.SubFactory(SpaceFactory)
    created_by = factory.SelfAttribute("space.created_by")
    label = factory.Sequence(lambda n: f"Discussion {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        parent = kwargs.pop("parent", None)
        space = kwargs["space"]
        if parent is None and space.root_discussion_id is not None:
            parent = space.root_discussion
        if parent is not None:
            return parent.add_child(**kwargs)
        return Discussion.add_root(**kwargs)
