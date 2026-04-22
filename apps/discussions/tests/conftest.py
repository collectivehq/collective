from __future__ import annotations

import pytest

from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.users.tests.factories import UserFactory


@pytest.fixture
def open_space_with_users():
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    space = Space.objects.get(pk=space.pk)
    participant_user = UserFactory()
    space_services.join_space(space=space, user=participant_user)
    outsider = UserFactory()
    return space, creator, participant_user, outsider
