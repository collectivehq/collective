from __future__ import annotations

import pytest

from apps.discussions.tests.factories import DiscussionFactory
from apps.opinions.permissions import can_opine


@pytest.mark.django_db
class TestCanOpine:
    def test_participant_can_opine(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.opinion_types = ["agree", "disagree"]
        space.save()
        discussion = DiscussionFactory(space=space)

        assert can_opine(participant_user, discussion) is True

    def test_outsider_cannot_opine(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        space.opinion_types = ["agree", "disagree"]
        space.save()
        discussion = DiscussionFactory(space=space)

        assert can_opine(outsider, discussion) is False

    def test_disabled_opinion_types(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.opinion_types = []
        space.save()
        discussion = DiscussionFactory(space=space)

        assert can_opine(participant_user, discussion) is False

    def test_closed_space_disables_opining(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        space.lifecycle = space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        discussion = DiscussionFactory(space=space)

        assert can_opine(participant_user, discussion) is False
