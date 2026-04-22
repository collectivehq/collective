from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.spaces import services as space_services
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.spaces.tests.factories import SpaceFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestCreateSpace:
    def test_creates_space_with_roles_and_root(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)

        assert space.title == "Test"
        assert space.created_by == user
        assert space.root_discussion is not None
        assert space.default_role is not None
        assert space.default_role.label == "Member"

        roles = Role.objects.filter(space=space)
        assert roles.count() == 3
        labels = set(roles.values_list("label", flat=True))
        assert labels == {"Facilitator", "Member", "Observer"}
        assert roles.get(label="Facilitator").can_view_drafts is True
        assert roles.get(label="Member").can_view_drafts is False
        assert roles.get(label="Observer").can_view_drafts is False

    def test_creates_facilitator_participant(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        participant = SpaceParticipant.objects.get(space=space, user=user)
        assert participant.role.label == "Facilitator"
        assert participant.created_by == user

    def test_creates_root_node(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        root = space.root_discussion
        assert root is not None
        assert root.label == "Test"
        assert root.depth == 1

    def test_default_opinion_types(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        assert space.opinion_types == ["agree", "disagree"]

    def test_custom_opinion_types(self):
        user = UserFactory()
        space = space_services.create_space(
            title="Test", created_by=user, opinion_types=["agree", "abstain", "disagree"]
        )
        assert space.opinion_types == ["agree", "abstain", "disagree"]

    def test_creates_space_with_information(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user, information="<p>Welcome</p>")

        assert space.information == "<p>Welcome</p>"


@pytest.mark.django_db
class TestLifecycle:
    def test_open_space(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        assert space.lifecycle == Space.Lifecycle.DRAFT
        space = space_services.open_space(space=space)
        assert space.lifecycle == Space.Lifecycle.OPEN


@pytest.mark.django_db
class TestTouchSpace:
    def test_updates_timestamp_on_instance_and_database(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        original_updated_at = space.updated_at

        space_services.touch_space(space=space)
        space.refresh_from_db()

        assert space.updated_at is not None
        assert original_updated_at is not None
        assert space.updated_at > original_updated_at


@pytest.mark.django_db
class TestJoinLeave:
    def test_join_space(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        participant = space_services.join_space(space=space, user=joiner)
        assert participant.user == joiner
        assert participant.role.label == "Member"
        assert participant.created_by == joiner

    def test_join_with_custom_role(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        observer_role = Role.objects.get(space=space, label="Observer")
        participant = space_services.join_space(space=space, user=joiner, role=observer_role)
        assert participant.role.label == "Observer"

    def test_leave_space(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        space_services.join_space(space=space, user=joiner)
        space_services.leave_space(space=space, user=joiner)
        assert not SpaceParticipant.objects.filter(space=space, user=joiner).exists()

    def test_cannot_join_closed_space(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        space.lifecycle = Space.Lifecycle.CLOSED
        space.save(update_fields=["lifecycle"])
        with pytest.raises(ValueError, match="not active"):
            space_services.join_space(space=space, user=joiner)

    def test_leave_not_participant_silent(self):
        user = UserFactory()
        outsider = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.leave_space(space=space, user=outsider)

    def test_join_draft_space_fails(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        with pytest.raises(ValueError, match="not active"):
            space_services.join_space(space=space, user=joiner)

    def test_join_future_space_fails(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(
            title="Test",
            created_by=user,
            starts_at=timezone.now() + datetime.timedelta(hours=1),
        )
        space_services.open_space(space=space)

        with pytest.raises(ValueError, match="not active"):
            space_services.join_space(space=space, user=joiner)

    def test_update_participant_role(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        participant = space_services.join_space(space=space, user=joiner)
        observer = Role.objects.get(space=space, label="Observer")
        updated = space_services.update_participant_role(participant=participant, role=observer)
        assert updated.role.label == "Observer"


@pytest.mark.django_db
class TestUpdateRole:
    def test_update_participant_role(self):
        user = UserFactory()
        joiner = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        participant = space_services.join_space(space=space, user=joiner)
        facilitator_role = Role.objects.get(space=space, label="Facilitator")
        updated = space_services.update_participant_role(participant=participant, role=facilitator_role)
        assert updated.role.label == "Facilitator"


@pytest.mark.django_db
class TestCreateRole:
    def test_creates_role(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        role = space_services.create_role(space=space, label="Reviewer", created_by=user)
        assert role.label == "Reviewer"
        assert role.space == space
        assert role.created_by == user

    def test_empty_label_raises(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        with pytest.raises(ValueError, match="required"):
            space_services.create_role(space=space, label="", created_by=user)

    def test_duplicate_label_raises(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        with pytest.raises(ValueError, match="already exists"):
            space_services.create_role(space=space, label="Facilitator", created_by=user)


@pytest.mark.django_db
class TestUpdateRoleService:
    def test_rename_role(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        role = space_services.create_role(space=space, label="Reviewer", created_by=user)
        updated = space_services.update_role(role=role, label="Editor")
        assert updated.label == "Editor"

    def test_duplicate_rename_raises(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        role = space_services.create_role(space=space, label="Reviewer", created_by=user)
        with pytest.raises(ValueError, match="already exists"):
            space_services.update_role(role=role, label="Facilitator")

    def test_update_permissions(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        role = space_services.create_role(space=space, label="Reviewer", created_by=user)
        updated = space_services.update_role(
            role=role,
            permissions={"can_post": True, "can_resolve": True, "can_view_drafts": True},
        )
        assert updated.can_post is True
        assert updated.can_view_drafts is True
        assert updated.can_resolve is True

    def test_cannot_remove_last_admin_permission(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        facilitator_role = Role.objects.get(space=space, label="Facilitator")
        with pytest.raises(ValueError, match="permission management"):
            space_services.update_role(role=facilitator_role, permissions={"can_set_permissions": False})


@pytest.mark.django_db
class TestDeleteRole:
    def test_delete_role(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        role = space_services.create_role(space=space, label="Temp", created_by=user)
        label = space_services.delete_role(role=role)
        assert label == "Temp"
        assert not Role.objects.filter(pk=role.pk).exists()

    def test_cannot_delete_role_with_participants(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        space_services.open_space(space=space)
        joiner = UserFactory()
        space_services.join_space(space=space, user=joiner)
        participant_role = Role.objects.get(space=space, label="Member")
        with pytest.raises(ValueError, match="participants assigned"):
            space_services.delete_role(role=participant_role)

    def test_cannot_delete_default_role(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        default_role = space.default_role
        with pytest.raises(ValueError, match="default role"):
            space_services.delete_role(role=default_role)


@pytest.mark.django_db
class TestSetDefaultRole:
    def test_set_default_role(self):
        user = UserFactory()
        space = space_services.create_space(title="Test", created_by=user)
        observer_role = Role.objects.get(space=space, label="Observer")
        space_services.set_default_role(space=space, role=observer_role)
        space.refresh_from_db()
        assert space.default_role == observer_role


@pytest.mark.django_db
class TestSpaceFactory:
    def test_creates_root_roles_and_facilitator_participant(self):
        space = SpaceFactory()

        assert space.root_discussion is not None
        assert space.default_role is not None
        assert Role.objects.filter(space=space).count() == 3
        assert SpaceParticipant.objects.filter(space=space, user=space.created_by, role__label="Facilitator").exists()
