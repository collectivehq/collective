from __future__ import annotations

import pytest
from apps.spaces import services as space_services
from apps.spaces.models import Space, SpaceParticipant
from apps.users.models import User
from apps.users.tests.factories import UserFactory


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def space(user: User) -> Space:
    s = space_services.create_space(title="Test Space", created_by=user)
    space_services.open_space(space=s)
    return Space.objects.get(pk=s.pk)


@pytest.fixture
def participant(space: Space, user: User) -> SpaceParticipant | None:
    return space_services.get_participant(space=space, user=user)
