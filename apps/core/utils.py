from __future__ import annotations

from typing import cast

from django.http import HttpRequest

from apps.users.models import User


class _AuthenticatedHttpRequest(HttpRequest):
    user: User


type AuthenticatedHttpRequest = _AuthenticatedHttpRequest


def get_user(request: AuthenticatedHttpRequest | HttpRequest) -> User:
    return cast(User, request.user)
