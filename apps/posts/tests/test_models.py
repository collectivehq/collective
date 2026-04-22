from __future__ import annotations

import pytest

from apps.posts.tests.factories import PostFactory


@pytest.mark.django_db
def test_post_content_and_latest_revision() -> None:
    post = PostFactory(content="Initial body")

    assert post.latest_revision is not None
    assert post.content == "Initial body"
    assert post.is_post is True
    assert post.is_link is False
