from __future__ import annotations

import pytest

from apps.spaces import services as space_services
from apps.spaces.permissions import (
    can_archive_space,
    can_close_space,
    can_manage_participants,
    can_moderate_content,
    can_modify_closed_space,
    can_set_permissions,
    can_unarchive_space,
    can_view_space,
)


@pytest.mark.django_db
class TestLifecyclePermissions:
    def test_facilitator_can_close(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_close_space(creator, space) is True

    def test_participant_cannot_close(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_close_space(participant, space) is False

    def test_facilitator_can_archive_and_unarchive(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_archive_space(creator, space) is True
        assert can_unarchive_space(creator, space) is True

    def test_moderator_can_modify_closed_space_by_default(self, open_space_with_users):
        space, _, _, outsider = open_space_with_users
        moderator_role = space.roles.get(label="Moderator")
        space_services.join_space(space=space, user=outsider, role=moderator_role)
        assert can_modify_closed_space(outsider, space) is True


@pytest.mark.django_db
class TestModerationPermissions:
    def test_facilitator_can_moderate_content(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_moderate_content(creator, space) is True

    def test_participant_cannot_moderate_content(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_moderate_content(participant, space) is False

    def test_facilitator_can_manage_participants(self, open_space_with_users):
        space, creator, _, _ = open_space_with_users
        assert can_manage_participants(creator, space) is True

    def test_participant_cannot_manage_participants(self, open_space_with_users):
        space, _, participant, _ = open_space_with_users
        assert can_manage_participants(participant, space) is False


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
