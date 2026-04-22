from __future__ import annotations

import pytest
from django.http import Http404, HttpRequest

from apps.spaces import services as space_services
from apps.spaces.models import Space
from apps.spaces.request_context import get_active_space_request_context, get_space_request_context
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_get_space_request_context_returns_participant_for_joined_user() -> None:
    creator = UserFactory()
    space = space_services.create_space(title="Test", created_by=creator)
    space_services.open_space(space=space)
    joiner = UserFactory()
    participant = space_services.join_space(space=space, user=joiner)

    request = HttpRequest()
    request.user = joiner

    context = get_space_request_context(request, str(space.pk))

    assert context.space == space
    assert context.user == joiner
    assert context.participant == participant


@pytest.mark.django_db
def test_get_active_space_request_context_rejects_inactive_space() -> None:
    creator = UserFactory()
    space = space_services.create_space(title="Closed", created_by=creator)
    space.lifecycle = Space.Lifecycle.CLOSED
    space.save(update_fields=["lifecycle"])

    request = HttpRequest()
    request.user = creator

    with pytest.raises(Http404):
        get_active_space_request_context(request, str(space.pk))
