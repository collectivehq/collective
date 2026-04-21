from __future__ import annotations

from typing import cast

from django.http import HttpRequest

from apps.users.models import User


def get_user(request: HttpRequest) -> User:
    return cast(User, request.user)
