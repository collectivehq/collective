from __future__ import annotations

import pytest

from apps.nodes.models import Node
from apps.nodes.tests.factories import NodeFactory, PostRevisionFactory


@pytest.mark.django_db
class TestNode:
    def test_create_root_node(self):
        node = NodeFactory(label="Root")
        assert node.pk is not None
        assert node.label == "Root"
        assert node.depth == 1

    def test_create_child_node(self):
        parent = NodeFactory(label="Parent")
        child = NodeFactory(label="Child", parent=parent, space=parent.space)
        assert child.depth == 2
        assert child.get_parent().pk == parent.pk

    def test_str_with_label(self):
        node = NodeFactory(label="Topic")
        assert str(node) == "Topic"

    def test_str_without_label(self):
        node = NodeFactory(label="")
        assert str(node).startswith("Discussion ")

    def test_default_values(self):
        node = NodeFactory()
        assert node.child_count == 0
        assert node.node_type == Node.NodeType.DISCUSSION
        assert node.permission_mode == Node.PermissionMode.INHERITED
        assert node.deleted_at is None

    def test_post_type_node(self):
        parent = NodeFactory()
        post = NodeFactory(
            parent=parent,
            space=parent.space,
            node_type=Node.NodeType.POST,
            content="Hello",
        )
        assert post.is_post
        assert not post.is_discussion

    def test_is_discussion(self):
        node = NodeFactory()
        assert node.is_discussion
        assert not node.is_post
        assert not node.is_link


@pytest.mark.django_db
class TestPostRevision:
    def test_create_revision(self):
        rev = PostRevisionFactory(content="Original text")
        assert rev.pk is not None
        assert rev.content == "Original text"

    def test_str(self):
        rev = PostRevisionFactory()
        assert "Revision" in str(rev)
