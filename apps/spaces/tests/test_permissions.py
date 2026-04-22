from __future__ import annotations

import pytest

from apps.spaces.permissions import (
    can_close_space,
    can_moderate,
    can_set_permissions,
    can_view_space,
)


@pytest.mark.django_db
class TestCanCloseSpace:
    def test_facilitator_can_close(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_close_space(creator, space) is True

    def test_participant_cannot_close(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_close_space(participant, space) is False


@pytest.mark.django_db
class TestCanModerate:
    def test_facilitator_can_moderate(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_moderate(creator, space) is True

    def test_participant_cannot_moderate(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_moderate(participant, space) is False


@pytest.mark.django_db
class TestCanSetPermissions:
    def test_facilitator_can_set_permissions(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_set_permissions(creator, space) is True

    def test_participant_cannot_set_permissions(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_set_permissions(participant, space) is False

    def test_outsider_cannot_set_permissions(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        assert can_set_permissions(outsider, space) is False


@pytest.mark.django_db
class TestCanViewSpace:
    def test_participant_can_view(self, open_space_with_users):
        space, _, participant_user, _ = open_space_with_users
        assert can_view_space(participant_user, space) is True

    def test_outsider_cannot_view(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        assert can_view_space(outsider, space) is False
