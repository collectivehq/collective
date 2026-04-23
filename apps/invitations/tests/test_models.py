from __future__ import annotations

import pytest
from apps.core.models import AcceptableModel, BaseModel, RejectableModel
from apps.invitations.models import SpaceInvite
from apps.spaces.tests.factories import RoleFactory, SpaceFactory
from django.core.exceptions import ValidationError


@pytest.mark.django_db
class TestSpaceInvite:
    def test_inherits_base_model(self) -> None:
        assert issubclass(SpaceInvite, BaseModel)
        assert issubclass(SpaceInvite, AcceptableModel)
        assert issubclass(SpaceInvite, RejectableModel)

    def test_role_must_belong_to_same_space(self) -> None:
        space = SpaceFactory()
        other_role = RoleFactory()
        invite = SpaceInvite(space=space, role=other_role, created_by=space.created_by)

        with pytest.raises(ValidationError, match="Role must belong to the invite's space"):
            invite.full_clean()
