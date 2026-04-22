from __future__ import annotations

from django.http import HttpRequest

from apps.core.utils import get_user
from apps.users.tests.factories import UserFactory


def test_get_user_returns_typed_authenticated_user(db) -> None:
    user = UserFactory()
    request = HttpRequest()
    request.user = user

    assert get_user(request) == user
