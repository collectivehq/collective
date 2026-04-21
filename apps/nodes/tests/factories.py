from __future__ import annotations

import factory

from apps.nodes.models import Node, PostRevision
from apps.spaces.tests.factories import SpaceFactory


class NodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Node

    space = factory.SubFactory(SpaceFactory)
    label = factory.Sequence(lambda n: f"Node {n}")
    node_type = Node.NodeType.DISCUSSION

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        parent = kwargs.pop("parent", None)
        if parent is not None:
            return parent.add_child(**kwargs)
        return Node.add_root(**kwargs)


class PostRevisionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PostRevision

    post = factory.SubFactory(NodeFactory)
    content = factory.Faker("paragraph")
