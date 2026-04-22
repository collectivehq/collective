from __future__ import annotations

import pytest

from apps.discussions.tests.factories import DiscussionFactory


@pytest.mark.django_db
def test_discussion_flags_and_string() -> None:
    discussion = DiscussionFactory(label="Topic")

    assert discussion.is_discussion is True
    assert discussion.is_post is False
    assert discussion.is_link is False
    assert str(discussion) == "Topic"
