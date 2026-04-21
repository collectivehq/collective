from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.nodes.models import Node
from apps.spaces import services as space_services
from apps.spaces.markdown_import import MarkdownImportError, import_space_from_markdown, parse_space_markdown
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


def _build_markdown_bytes() -> bytes:
    return b"""# Structure

- Q1
  - 1a
    - 1a-i
      - 1a-i-alpha
  - 1b
- Q2

# Content

## Q1
**Lorem ipsum**

### 1a
Lalala

#### 1a-i
Bababa

##### 1a-i-alpha
- Bullet one
- Bullet two

## Q2
Dolor sit amet
"""


@pytest.mark.django_db
class TestParseSpaceMarkdown:
    def test_parses_structure_and_content(self):
        parsed = parse_space_markdown(markdown_bytes=_build_markdown_bytes())

        assert [node.label for node in parsed] == ["Q1", "Q2"]
        assert [child.label for child in parsed[0].children] == ["1a", "1b"]
        assert parsed[0].children[0].children[0].label == "1a-i"
        assert parsed[0].children[0].children[0].children[0].label == "1a-i-alpha"
        assert "<strong>Lorem ipsum</strong>" in parsed[0].content_html
        assert "<li>Bullet one</li>" in parsed[0].children[0].children[0].children[0].content_html

    def test_rejects_unknown_content_headings(self):
        markdown_bytes = b"""# Structure

- Q1

# Content

## Missing
Oops
"""

        with pytest.raises(MarkdownImportError, match="unknown structure items"):
            parse_space_markdown(markdown_bytes=markdown_bytes)


@pytest.mark.django_db
class TestImportSpaceFromMarkdown:
    def test_populates_discussions_and_posts(self):
        user = UserFactory()
        space = space_services.create_space(title="Imported", created_by=user)
        space_services.open_space(space=space)

        import_space_from_markdown(space=space, author=user, markdown_bytes=_build_markdown_bytes())

        q1 = Node.objects.get(space=space, label="Q1", deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION)
        q2 = Node.objects.get(space=space, label="Q2", deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION)
        one_a = Node.objects.get(space=space, label="1a", deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION)
        one_a_i = Node.objects.get(
            space=space, label="1a-i", deleted_at__isnull=True, node_type=Node.NodeType.DISCUSSION
        )
        one_a_i_alpha = Node.objects.get(
            space=space,
            label="1a-i-alpha",
            deleted_at__isnull=True,
            node_type=Node.NodeType.DISCUSSION,
        )

        assert q1.get_parent().pk == space.root_discussion.pk
        assert q2.get_parent().pk == space.root_discussion.pk
        assert one_a.get_parent().pk == q1.pk
        assert one_a_i.get_parent().pk == one_a.pk
        assert one_a_i_alpha.get_parent().pk == one_a_i.pk
        assert Node.objects.filter(
            space=space,
            node_type=Node.NodeType.POST,
            content__contains="<strong>Lorem ipsum</strong>",
        ).exists()
        assert Node.objects.filter(
            space=space, node_type=Node.NodeType.POST, content__contains="<li>Bullet one</li>"
        ).exists()


@pytest.mark.django_db
class TestSpaceCreateMarkdownImportView:
    def test_create_space_from_markdown(self):
        user = UserFactory()
        client = Client()
        client.force_login(user)

        uploaded = SimpleUploadedFile(
            "structure.md",
            _build_markdown_bytes(),
            content_type="text/markdown",
        )

        response = client.post(
            reverse("spaces:create"),
            {
                "title": "Imported Markdown Space",
                "description": "Desc",
                "information": "",
                "source_markdown": uploaded,
            },
        )

        assert response.status_code == 302
        space = Space.objects.get(title="Imported Markdown Space")
        assert Node.objects.filter(space=space, label="1a-i-alpha", deleted_at__isnull=True).exists()
        assert Node.objects.filter(
            space=space,
            node_type=Node.NodeType.POST,
            content__contains="<li>Bullet one</li>",
        ).exists()
