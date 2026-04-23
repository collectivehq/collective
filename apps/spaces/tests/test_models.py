from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models

from apps.core.models import CRUDModel
from apps.spaces.constants import PERMISSION_LABELS
from apps.spaces.models import Role, Space, SpaceParticipant
from apps.spaces.tests.factories import RoleFactory, SpaceFactory, SpaceParticipantFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestSpace:
    def test_inherits_crud_model(self):
        assert issubclass(Space, CRUDModel)

    def test_create_space(self):
        space = SpaceFactory(title="My Space")
        assert space.pk is not None
        assert space.title == "My Space"
        assert space.lifecycle == Space.Lifecycle.DRAFT

    def test_str(self):
        space = SpaceFactory(title="Debate")
        assert str(space) == "Debate"

    def test_is_active_when_open(self):
        space = SpaceFactory(lifecycle=Space.Lifecycle.OPEN)
        assert space.is_active is True

    def test_is_not_active_when_draft(self):
        space = SpaceFactory(lifecycle=Space.Lifecycle.DRAFT)
        assert space.is_active is False

    def test_is_not_active_when_deleted(self):
        from django.utils import timezone

        space = SpaceFactory(lifecycle=Space.Lifecycle.OPEN, deleted_at=timezone.now())
        assert space.is_active is False

    def test_default_ordering(self):
        s1 = SpaceFactory()
        s2 = SpaceFactory()
        spaces = list(Space.objects.all())
        assert spaces[0] == s2  # most recent first
        assert spaces[1] == s1

    def test_default_role_must_belong_to_same_space(self):
        space = SpaceFactory()
        other_space = SpaceFactory()
        other_role = other_space.roles.get(label="Observer")
        space.default_role = other_role

        with pytest.raises(ValidationError, match="Default role must belong to this space"):
            space.full_clean()


@pytest.mark.django_db
class TestRole:
    def test_create_role(self):
        role = RoleFactory(label="Admin")
        assert role.pk is not None
        assert role.label == "Admin"
        assert role.created_by == role.space.created_by

    def test_str(self):
        space = SpaceFactory(title="Test")
        role = space.roles.get(label="Facilitator")
        assert str(role) == "Facilitator (Test)"

    def test_unique_label_per_space(self):
        space = SpaceFactory()
        with pytest.raises(IntegrityError):
            RoleFactory(space=space, label="Facilitator")

    def test_default_permissions(self):
        role = RoleFactory()
        assert role.post_highlight_color == ""
        assert role.can_post is True
        assert role.can_edit_others_post is False
        assert role.can_archive_space is False
        assert role.can_unarchive_space is False
        assert role.can_modify_closed_space is False
        assert role.can_view_drafts is False
        assert role.can_create_discussion is False
        assert role.can_moderate_content is False

    def test_permission_labels_matches_role_fields(self):
        permission_fields = {
            field.name
            for field in Role._meta.get_fields()
            if isinstance(field, models.BooleanField) and field.name.startswith("can_")
        }

        assert set(PERMISSION_LABELS) == permission_fields


@pytest.mark.django_db
class TestSpaceParticipant:
    def test_create_participant(self):
        participant = SpaceParticipantFactory()
        assert participant.pk is not None
        assert participant.created_at is not None

    def test_str(self):
        participant = SpaceParticipantFactory()
        result = str(participant)
        assert "in" in result

    def test_unique_user_per_space(self):
        user = UserFactory()
        space = SpaceFactory()
        role = RoleFactory(space=space)
        SpaceParticipant.objects.create(space=space, user=user, role=role, created_by=user)
        with pytest.raises(IntegrityError):
            SpaceParticipant.objects.create(space=space, user=user, role=role, created_by=user)

    def test_role_must_belong_to_same_space(self):
        user = UserFactory()
        space = SpaceFactory()
        other_role = RoleFactory()
        participant = SpaceParticipant(space=space, user=user, role=other_role, created_by=user)

        with pytest.raises(ValidationError, match="Role must belong to the participant's space"):
            participant.full_clean()
